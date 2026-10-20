"""Shared parsing and dispatch for ``--command(...)`` messages."""

import inspect
import re


class CommandNameCollision(ValueError):
    pass


def getCommandRegistry(botObj):
    commandMap = {}
    for cogName in botObj.cogs:
        cogObj = botObj.get_cog(cogName)
        cogCommands = getattr(cogObj, "get_app_commands", None)
        if callable(cogCommands):
            commandList = cogCommands()
        else:
            commandList = getattr(cogObj, "__cog_app_commands__", [])

        for commandObj in commandList:
            existing = commandMap.get(commandObj.name)
            if existing and existing[0] is not commandObj:
                raise CommandNameCollision(
                    f"斜線指令名稱衝突：/{commandObj.name} "
                    f"同時出現在 {type(existing[1]).__name__} 與 {type(cogObj).__name__}"
                )
            commandMap[commandObj.name] = (commandObj, cogObj)
    return commandMap


def parseArguments(paramText):
    if not paramText:
        return {}
    values = {}
    for item in paramText.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def convertArgument(value, annotation):
    if annotation is float:
        return float(value)
    if annotation is int:
        return int(value)
    return value


async def dispatchTextCommands(
    botObj,
    content,
    interaction,
    *,
    attachment=None,
    promptLabel="提示",
    errorLabel="指令錯誤",
    runChecks=True,
):
    try:
        commandMap = getCommandRegistry(botObj)
    except CommandNameCollision as errObj:
        await interaction.response.send_message(str(errObj))
        return

    for segment in (part.strip() for part in content.strip().split("--") if part.strip()):
        match = re.fullmatch(r"(\w+)(?:\((.*?)\))?", segment)
        if not match:
            continue

        commandName = match.group(1).lower()
        if commandName in {"admin_setup", "access_scope", "access_logout"}:
            await interaction.response.send_message("權限管理指令只能透過斜線指令使用。")
            continue
        commandEntry = commandMap.get(commandName)
        if not commandEntry:
            continue

        commandObj, cogObj = commandEntry
        signature = inspect.signature(commandObj.callback)
        dataParams = [
            param for param in signature.parameters.values()
            if param.name not in ("self", "interaction")
        ]
        params = parseArguments(match.group(2))
        if commandName == "screenshot_notify" and attachment is not None:
            params["image"] = attachment

        requiredParams = [
            param for param in dataParams
            if param.default == inspect.Parameter.empty and param.name not in params
        ]
        if requiredParams:
            allParams = ", ".join(
                f"{param.name}" + (
                    f"={param.default}" if param.default != inspect.Parameter.empty else ""
                )
                for param in dataParams
            )
            example = ", ".join(f"{param.name}=值" for param in requiredParams)
            helpText = (
                f"【{promptLabel}】指令 `--{commandName}` 缺少參數。\n"
                f"**語法**：`--{commandName}({allParams})`\n"
                f"**範例**：`--{commandName}({example})`"
            )
            await interaction.response.send_message(helpText)
            continue

        kwargs = {}
        try:
            for paramName, paramValue in params.items():
                param = signature.parameters.get(paramName)
                if param is not None:
                    kwargs[paramName] = (
                        paramValue if paramName == "image" and attachment is not None
                        else convertArgument(paramValue, param.annotation)
                    )

            if runChecks:
                for check in getattr(commandObj, "checks", []):
                    checkResult = check(interaction)
                    if inspect.isawaitable(checkResult):
                        checkResult = await checkResult
                    if not checkResult:
                        raise PermissionError(f"指令 /{commandName} 的檢查未通過")

            await commandObj.callback(cogObj, interaction, **kwargs)
        except Exception as errObj:
            await interaction.response.send_message(f"【{errorLabel}】執行 `--{commandName}` 失敗：{errObj}")
