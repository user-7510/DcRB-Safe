"""Guild-scoped, role-based access control for application commands."""

import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


ACCESS_CONFIG_PATH = "dcrbs_access_control.json"
OWNER_PASSWORD_PATH = "dcrbs_owner_password.hash"
LEGACY_OWNER_PASSWORD_PATH = "owner_password.txt"
OWNER_SESSION_SECONDS = 600
OWNER_PASSWORD_MIN_LENGTH = 12
OWNER_PASSWORD_MAX_LENGTH = 128
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
MANAGEMENT_COMMAND_NAMES = {"admin_setup", "access_scope", "access_logout"}
FIXED_LEVEL_ONE_COMMANDS = {
    "cmd",
    "powershell",
    "startup",
    "shell_startup",
    "reg_startup",
    "reg_startup_remove",
    "audit_config",
}

DEFAULT_COMMAND_LEVELS = {
    "stop": 1,
    "panic_stop": 1,
    "resume": 1,
    "reject": 1,
    "token": 1,
    "shutdown": 1,
    "startup": 1,
    "shell_startup": 1,
    "powershell": 1,
    "cmd": 1,
    "reg_startup": 1,
    "reg_startup_remove": 1,
    "audit_config": 1,
    "key": 2,
    "keyboard": 2,
    "key_wait": 2,
    "web": 3,
    "blackade": 3,
    "unblackade": 3,
    "txt": 3,
    "msg": 3,
    "close": 3,
    "close_loop": 3,
    "close_stop": 3,
    "monitor_off": 3,
    "monitor_on": 3,
    "screenshot": 3,
    "screenshot_notify": 3,
    "device": 3,
    "volume": 3,
    "task_list": 3,
    "cmdlist": 3,
    "help": 3,
}


def _defaultConfig():
    return {
        "version": 1,
        "command_levels": dict(DEFAULT_COMMAND_LEVELS),
        "guilds": {},
    }


def _deriveOwnerPassword(password, salt):
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )


def _encodeOwnerPassword(password):
    salt = secrets.token_bytes(16)
    passwordHash = _deriveOwnerPassword(password, salt)
    return {
        "algorithm": "scrypt",
        "n": SCRYPT_N,
        "r": SCRYPT_R,
        "p": SCRYPT_P,
        "salt": salt.hex(),
        "hash": passwordHash.hex(),
    }


def _readOwnerPasswordHash():
    with open(OWNER_PASSWORD_PATH, "r", encoding="utf-8") as fileObj:
        stored = json.load(fileObj)
    if (
        not isinstance(stored, dict)
        or stored.get("algorithm") != "scrypt"
        or stored.get("n") != SCRYPT_N
        or stored.get("r") != SCRYPT_R
        or stored.get("p") != SCRYPT_P
    ):
        raise ValueError("最高管理者密碼雜湊檔格式不正確。")
    try:
        salt = bytes.fromhex(stored["salt"])
        passwordHash = bytes.fromhex(stored["hash"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("最高管理者密碼雜湊檔格式不正確。")
    if len(salt) != 16 or len(passwordHash) != SCRYPT_DKLEN:
        raise ValueError("最高管理者密碼雜湊檔格式不正確。")
    return salt, passwordHash


def _writeOwnerPasswordHash(password):
    stored = _encodeOwnerPassword(password)
    tempPath = OWNER_PASSWORD_PATH + ".tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fileDescriptor = os.open(tempPath, flags, 0o600)
    try:
        with os.fdopen(fileDescriptor, "w", encoding="utf-8") as fileObj:
            fileDescriptor = None
            json.dump(stored, fileObj, ensure_ascii=False)
            fileObj.write("\n")
            fileObj.flush()
            os.fsync(fileObj.fileno())
        try:
            os.chmod(tempPath, 0o600)
        except OSError:
            pass
        os.replace(tempPath, OWNER_PASSWORD_PATH)
        try:
            os.chmod(OWNER_PASSWORD_PATH, 0o600)
        except OSError:
            pass
    except Exception:
        if fileDescriptor is not None:
            os.close(fileDescriptor)
        try:
            os.remove(tempPath)
        except OSError:
            pass
        raise


def _ensureInteractiveTerminal():
    try:
        if sys.stdin.isatty() and sys.stdout.isatty():
            return
    except (AttributeError, OSError):
        pass

    if os.name == "nt":
        try:
            import ctypes

            if ctypes.windll.kernel32.AllocConsole():
                sys.stdin = open("CONIN$", "r", encoding="utf-8")
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                return
        except Exception:
            pass
    raise RuntimeError(
        "首次設定最高管理者密碼需要互動式終端；請在終端執行 python dcrbs.py。"
    )


def _promptNewOwnerPassword():
    _ensureInteractiveTerminal()
    print("[權限] 首次啟動，請設定最高管理者密碼（至少 12 個字元）。")
    while True:
        password = getpass.getpass("設定最高管理者密碼：")
        if not OWNER_PASSWORD_MIN_LENGTH <= len(password) <= OWNER_PASSWORD_MAX_LENGTH:
            print("密碼長度須為 12 至 128 個字元，請重新輸入。")
            continue
        confirmation = getpass.getpass("再次輸入密碼確認：")
        if not hmac.compare_digest(password, confirmation):
            print("兩次輸入不一致，請重新設定。")
            continue
        return password


def initializeOwnerPassword():
    """Ensure a local scrypt password hash exists before the bot connects."""
    if os.path.exists(OWNER_PASSWORD_PATH):
        # Do not replace an unreadable or malformed hash silently.
        _readOwnerPasswordHash()
        if os.path.exists(LEGACY_OWNER_PASSWORD_PATH):
            os.remove(LEGACY_OWNER_PASSWORD_PATH)
        return

    if os.path.exists(LEGACY_OWNER_PASSWORD_PATH):
        with open(LEGACY_OWNER_PASSWORD_PATH, "r", encoding="utf-8") as fileObj:
            legacyPassword = fileObj.read().strip()
        if legacyPassword:
            _writeOwnerPasswordHash(legacyPassword)
            os.remove(LEGACY_OWNER_PASSWORD_PATH)
            print("[權限] 已將舊版本機密碼轉為 scrypt 雜湊並移除明文檔。")
            return
        os.remove(LEGACY_OWNER_PASSWORD_PATH)

    password = _promptNewOwnerPassword()
    _writeOwnerPasswordHash(password)
    print(f"[權限] 最高管理者密碼雜湊已儲存至 {OWNER_PASSWORD_PATH}。")


class AccessManager:
    def __init__(self):
        self.config = _defaultConfig()
        self.ownerSessions = {}
        self.loadConfig()

    def loadConfig(self):
        if not os.path.exists(ACCESS_CONFIG_PATH):
            return
        try:
            fixedLevelsChanged = False
            with open(ACCESS_CONFIG_PATH, "r", encoding="utf-8") as fileObj:
                loaded = json.load(fileObj)
            if not isinstance(loaded, dict):
                return
            loadedLevels = loaded.get("command_levels", {})
            if isinstance(loadedLevels, dict):
                for name, level in loadedLevels.items():
                    if str(level) in ("1", "2", "3"):
                        self.config["command_levels"][str(name)] = int(level)
            # Sensitive execution and startup configuration always require
            # the highest administrator tier, even if an older config says otherwise.
            for commandName in FIXED_LEVEL_ONE_COMMANDS:
                if self.config["command_levels"].get(commandName) != 1:
                    self.config["command_levels"][commandName] = 1
                    fixedLevelsChanged = True
            if isinstance(loaded.get("guilds"), dict):
                self.config["guilds"] = loaded["guilds"]
            if fixedLevelsChanged:
                self.saveConfig()
        except Exception as errObj:
            print(f"[權限] 無法讀取 {ACCESS_CONFIG_PATH}: {errObj}")

    def saveConfig(self):
        tempPath = ACCESS_CONFIG_PATH + ".tmp"
        try:
            with open(tempPath, "w", encoding="utf-8") as fileObj:
                json.dump(self.config, fileObj, ensure_ascii=False, indent=2)
            os.replace(tempPath, ACCESS_CONFIG_PATH)
            return True
        except Exception as errObj:
            print(f"[權限] 無法儲存 {ACCESS_CONFIG_PATH}: {errObj}")
            try:
                if os.path.exists(tempPath):
                    os.remove(tempPath)
            except OSError:
                pass
            return False

    def verifyOwnerPassword(self, submittedPassword):
        try:
            salt, expectedHash = _readOwnerPasswordHash()
            actualHash = _deriveOwnerPassword(submittedPassword, salt)
            return hmac.compare_digest(expectedHash, actualHash)
        except Exception as errObj:
            print(f"[權限] 無法驗證 {OWNER_PASSWORD_PATH}: {errObj}")
            return False

    def createOwnerSession(self, guildId, userId):
        self.ownerSessions[(int(guildId), int(userId))] = time.monotonic() + OWNER_SESSION_SECONDS

    def hasOwnerSession(self, guildId, userId):
        key = (int(guildId), int(userId))
        expiry = self.ownerSessions.get(key, 0)
        if expiry <= time.monotonic():
            self.ownerSessions.pop(key, None)
            return False
        return True

    def clearOwnerSession(self, guildId, userId):
        self.ownerSessions.pop((int(guildId), int(userId)), None)

    def _getGuildScope(self, guildId, create=False):
        guildKey = str(guildId)
        guildMap = self.config["guilds"]
        if create:
            return guildMap.setdefault(guildKey, {"users": {"1": [], "2": [], "3": []}, "roles": {"2": [], "3": []}})
        return guildMap.get(guildKey, {})

    def updateScope(self, guildId, level, scopeType, targetId, add):
        if level not in (1, 2, 3):
            raise ValueError("權限層級必須是 1、2 或 3。")
        if scopeType not in ("user", "role"):
            raise ValueError("範圍類型必須是 user 或 role。")
        if level == 1 and scopeType == "role":
            raise ValueError("最高管理者層級只接受使用者 ID，不接受角色。")

        try:
            normalizedId = str(int(targetId))
        except (TypeError, ValueError):
            raise ValueError("ID 必須是正整數。")
        if int(normalizedId) <= 0:
            raise ValueError("ID 必須是正整數。")

        guildScope = self._getGuildScope(guildId, create=True)
        scopeMap = guildScope.setdefault(scopeType + "s", {})
        idList = scopeMap.setdefault(str(level), [])
        idList[:] = [str(item) for item in idList]
        if add and normalizedId not in idList:
            idList.append(normalizedId)
        elif not add and normalizedId in idList:
            idList.remove(normalizedId)
        return self.saveConfig()

    def listScope(self, guildId, level, scopeType):
        guildScope = self._getGuildScope(guildId)
        scopeMap = guildScope.get(scopeType + "s", {})
        if level is None:
            levels = (1, 2, 3) if scopeType == "user" else (2, 3)
        else:
            levels = (level,)
        return {
            targetLevel: [str(item) for item in scopeMap.get(str(targetLevel), [])]
            for targetLevel in levels
        }

    def isLevelOneUserAnywhere(self, userId):
        userId = str(userId)
        for guildScope in self.config.get("guilds", {}).values():
            userScopes = guildScope.get("users", {}) if isinstance(guildScope, dict) else {}
            levelOneUsers = userScopes.get("1", []) if isinstance(userScopes, dict) else []
            if userId in [str(item) for item in levelOneUsers]:
                return True
        return False

    async def checkCommandAccess(self, interaction, commandName=None):
        user = getattr(interaction, "user", None)
        if user is None or getattr(user, "bot", False):
            raise app_commands.CheckFailure("不支援機器人觸發。")

        commandObj = getattr(interaction, "command", None)
        commandName = commandName or getattr(commandObj, "name", None) or getattr(interaction, "_permission_command_name", None)
        if not commandName:
            raise app_commands.CheckFailure("無法判斷指令權限。")

        # These management commands authorize each operation with a short owner session.
        if commandName in MANAGEMENT_COMMAND_NAMES:
            return True

        userId = str(getattr(user, "id", ""))
        guildId = getattr(interaction, "guild_id", None)
        requiredLevel = int(self.config["command_levels"].get(commandName, 1))
        if guildId is None:
            if self.isLevelOneUserAnywhere(userId):
                return True
            raise app_commands.CheckFailure("私訊中僅已設定的層級 1 最高管理員可使用指令。")

        guildScope = self._getGuildScope(guildId)
        assignedLevels = []
        userScopes = guildScope.get("users", {})
        roleScopes = guildScope.get("roles", {})

        for level in (1, 2, 3):
            if userId in [str(item) for item in userScopes.get(str(level), [])]:
                assignedLevels.append(level)

        roleIds = {str(getattr(roleObj, "id", "")) for roleObj in getattr(user, "roles", [])}
        for level in (2, 3):
            configuredRoles = {str(item) for item in roleScopes.get(str(level), [])}
            if roleIds.intersection(configuredRoles):
                assignedLevels.append(level)

        if not assignedLevels or min(assignedLevels) > requiredLevel:
            raise app_commands.CheckFailure("你沒有使用此指令的權限。")
        return True


accessManager = AccessManager()


class OwnerLoginModal(discord.ui.Modal, title="最高管理者登入"):
    passwordInput = discord.ui.TextInput(
        label="最高管理者密碼",
        required=True,
        min_length=1,
        max_length=128,
    )

    def __init__(self, manager, guildId, userId):
        super().__init__(timeout=120)
        self.manager = manager
        self.guildId = int(guildId)
        self.userId = int(userId)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild_id != self.guildId or interaction.user.id != self.userId:
            return await interaction.response.send_message("登入視窗已失效，請重新執行 `/admin_setup`。", ephemeral=True)
        if not self.manager.verifyOwnerPassword(self.passwordInput.value):
            return await interaction.response.send_message("密碼錯誤。", ephemeral=True)
        self.manager.createOwnerSession(self.guildId, interaction.user.id)
        await interaction.response.send_message(
            "已登入權限管理；管理工作階段有效 10 分鐘。",
            ephemeral=True,
        )


class AccessControlCog(commands.Cog):
    def __init__(self, botObj, manager):
        self.bot = botObj
        self.manager = manager

    @app_commands.command(name="admin_setup", description="以最高管理者密碼登入並設定權限白名單")
    async def adminSetupCommand(self, interaction: discord.Interaction):
        if interaction.user.bot:
            return await interaction.response.send_message("不支援機器人登入。", ephemeral=True)
        if interaction.guild_id is None:
            return await interaction.response.send_message("請在伺服器中使用此指令。", ephemeral=True)
        await interaction.response.send_modal(OwnerLoginModal(self.manager, interaction.guild_id, interaction.user.id))

    async def requireOwnerSession(self, interaction):
        if interaction.user.bot:
            await interaction.response.send_message("不支援機器人觸發。", ephemeral=True)
            return False
        if interaction.guild_id is None:
            await interaction.response.send_message("請在伺服器中使用此指令。", ephemeral=True)
            return False
        if not self.manager.hasOwnerSession(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("請先執行 `/admin_setup` 登入。", ephemeral=True)
            return False
        return True

    @app_commands.command(name="access_scope", description="調整本伺服器的權限使用者與角色")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="加入", value="add"),
            app_commands.Choice(name="移除", value="remove"),
            app_commands.Choice(name="列出", value="list"),
        ],
        level=[
            app_commands.Choice(name="1 最高管理者", value=1),
            app_commands.Choice(name="2 管理員", value=2),
            app_commands.Choice(name="3 操作員", value=3),
        ],
        scope=[
            app_commands.Choice(name="使用者 ID", value="user"),
            app_commands.Choice(name="角色 ID", value="role"),
        ],
    )
    async def accessScopeCommand(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        level: app_commands.Choice[int],
        scope: app_commands.Choice[str],
        target_id: Optional[str] = None,
    ):
        if not await self.requireOwnerSession(interaction):
            return

        levelValue = level.value
        scopeValue = scope.value
        if action.value == "list":
            entries = self.manager.listScope(interaction.guild_id, levelValue, scopeValue)
            lines = [f"層級 {targetLevel}: {', '.join(ids) if ids else '（空）'}" for targetLevel, ids in entries.items()]
            return await interaction.response.send_message("\n".join(lines), ephemeral=True)

        if not target_id:
            return await interaction.response.send_message("加入或移除時必須提供 target_id。", ephemeral=True)

        try:
            targetNumericId = int(target_id)
        except ValueError:
            return await interaction.response.send_message("target_id 必須是數字 ID。", ephemeral=True)
        guildObj = interaction.guild
        if scopeValue == "role" and (guildObj is None or guildObj.get_role(targetNumericId) is None):
            return await interaction.response.send_message("找不到此伺服器中的角色 ID。", ephemeral=True)

        try:
            saved = self.manager.updateScope(
                interaction.guild_id,
                levelValue,
                scopeValue,
                targetNumericId,
                add=action.value == "add",
            )
        except ValueError as errObj:
            return await interaction.response.send_message(str(errObj), ephemeral=True)

        if not saved:
            return await interaction.response.send_message("無法儲存權限設定，請檢查程式目錄寫入權限。", ephemeral=True)
        verb = "已加入" if action.value == "add" else "已移除"
        await interaction.response.send_message(
            f"{verb}層級 {levelValue} 的 {scopeValue} ID：{int(target_id)}。",
            ephemeral=True,
        )

    @app_commands.command(name="access_logout", description="結束本伺服器的權限管理登入")
    async def accessLogoutCommand(self, interaction: discord.Interaction):
        if interaction.guild_id is not None:
            self.manager.clearOwnerSession(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message("已登出權限管理。", ephemeral=True)


async def setup(botObj: commands.Bot):
    await botObj.add_cog(AccessControlCog(botObj, accessManager))
    if not os.path.exists(ACCESS_CONFIG_PATH):
        accessManager.saveConfig()
    if not os.path.exists(OWNER_PASSWORD_PATH):
        raise RuntimeError("最高管理者密碼尚未初始化，請先使用 python dcrbs.py 啟動程式。")


def applyAccessChecks(botObj: commands.Bot):
    for commandObj in botObj.tree.get_commands():
        if commandObj.name in MANAGEMENT_COMMAND_NAMES:
            continue
        if not any(getattr(check, "_dcrbs_access_check", False) for check in commandObj.checks):
            async def commandAccessCheck(interaction, commandName=commandObj.name):
                return await accessManager.checkCommandAccess(interaction, commandName)
            commandAccessCheck._dcrbs_access_check = True
            commandObj.checks.append(commandAccessCheck)
