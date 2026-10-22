"""Google Forms based command audit logging.

Only invocation metadata is sent. Command parameters and command results are
deliberately excluded from audit records.
"""

import json
import os
import re
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import aiohttp


AUDIT_CONFIG_PATH = "dcrbs_audit_config.json"
ENTRY_ID_PATTERN = re.compile(r"^[0-9]+$")
FORM_PATH_PATTERN = re.compile(r"^/forms/d/(e/)?([^/]+)/(?:viewform|formResponse|edit)$")
_pendingTasks = set()


def normalizeFormSettings(formUrl, entryId):
    """Validate a Google Forms URL and return its formResponse URL and entry ID."""
    parsedUrl = urlsplit((formUrl or "").strip())
    if parsedUrl.scheme != "https" or parsedUrl.hostname != "docs.google.com":
        raise ValueError("請提供 Google 表單的 https://docs.google.com/forms/... 網址。")
    if parsedUrl.username or parsedUrl.password or parsedUrl.port:
        raise ValueError("表單網址格式不正確。")
    match = FORM_PATH_PATTERN.fullmatch(parsedUrl.path.rstrip("/"))
    if not match:
        raise ValueError("網址須是表單的 viewform、formResponse 或 edit 網址。")
    formVariant, formId = match.groups()
    if not formId or any(char in formId for char in "?#"):
        raise ValueError("表單網址格式不正確。")

    normalizedEntryId = (entryId or "").strip()
    if normalizedEntryId.startswith("entry."):
        normalizedEntryId = normalizedEntryId[len("entry."):]
    if not ENTRY_ID_PATTERN.fullmatch(normalizedEntryId):
        raise ValueError("欄位 ID 須是 Google 表單預填網址中的數字 entry ID。")

    responsePath = f"/forms/d/{formVariant or ''}{formId}/formResponse"
    responseUrl = urlunsplit(("https", "docs.google.com", responsePath, "", ""))
    return responseUrl, normalizedEntryId


def configureAuditForm(formUrl, entryId):
    responseUrl, normalizedEntryId = normalizeFormSettings(formUrl, entryId)
    configData = {"version": 1, "form_response_url": responseUrl, "entry_id": normalizedEntryId}
    tempPath = AUDIT_CONFIG_PATH + ".tmp"
    try:
        with open(tempPath, "w", encoding="utf-8") as fileObj:
            json.dump(configData, fileObj, ensure_ascii=False, indent=2)
            fileObj.write("\n")
            fileObj.flush()
            os.fsync(fileObj.fileno())
        os.replace(tempPath, AUDIT_CONFIG_PATH)
    except Exception:
        try:
            os.remove(tempPath)
        except OSError:
            pass
        raise
    return configData


def _readConfig():
    try:
        with open(AUDIT_CONFIG_PATH, "r", encoding="utf-8") as fileObj:
            configData = json.load(fileObj)
        formUrl = configData.get("form_response_url", "")
        entryId = str(configData.get("entry_id", ""))
        if not ENTRY_ID_PATTERN.fullmatch(entryId):
            return None
        parsedUrl = urlsplit(formUrl)
        if (
            parsedUrl.scheme != "https"
            or parsedUrl.hostname != "docs.google.com"
            or not parsedUrl.path.endswith("/formResponse")
        ):
            return None
        return formUrl, entryId
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _metadata(interaction, commandName, source, timestamp=None):
    userObj = getattr(interaction, "user", None)
    userId = getattr(userObj, "id", None)
    guildId = getattr(interaction, "guild_id", None)
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "timestamp_utc": timestamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "command": str(commandName)[:100],
        "user_id": str(userId) if userId is not None else "unknown",
        "guild_id": str(guildId) if guildId is not None else "dm",
        "source": str(source)[:32],
    }


async def recordCommand(interaction, commandName, source="slash", timestamp=None):
    """Submit one metadata-only record; failures never interrupt Bot commands."""
    configData = _readConfig()
    if configData is None:
        return False
    formUrl, entryId = configData
    recordText = json.dumps(
        _metadata(interaction, commandName, source, timestamp),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                formUrl,
                data={f"entry.{entryId}": recordText},
                allow_redirects=True,
            ) as response:
                if response.status >= 400:
                    print(f"[稽核] Google 表單回覆 HTTP {response.status}，本次指令未成功記錄。")
                    return False
        return True
    except Exception as errObj:
        print(f"[稽核] 無法送出 Google 表單紀錄：{type(errObj).__name__}")
        return False


def scheduleCommandRecord(interaction, commandName, source="slash", timestamp=None):
    """Queue an audit POST so a slow form submission does not delay the command."""
    task = asyncio.create_task(recordCommand(interaction, commandName, source, timestamp))
    _pendingTasks.add(task)
    task.add_done_callback(_pendingTasks.discard)
    return task


async def flushPendingRecords():
    """Wait for queued records during orderly shutdown, up to the request timeout."""
    pendingTasks = tuple(_pendingTasks)
    if pendingTasks:
        await asyncio.gather(*pendingTasks, return_exceptions=True)
