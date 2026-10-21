import time
import os
import asyncio
import inspect
import discord
from discord import app_commands
from discord.ext import commands


stopUntilTimestamp = None
PANIC_STOP_LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panic_stop.lock")
stopLocked = os.path.exists(PANIC_STOP_LOCK_PATH)
MANAGEMENT_COMMAND_NAMES = {"admin_setup", "access_scope", "access_logout"}
STOP_CONTROL_COMMAND_NAMES = {"resume", "panic_stop"}


def persistPanicStopLock():
    tempPath = PANIC_STOP_LOCK_PATH + ".tmp"
    try:
        with open(tempPath, "w", encoding="utf-8") as fileObj:
            fileObj.write("locked\n")
            fileObj.flush()
            os.fsync(fileObj.fileno())
        os.replace(tempPath, PANIC_STOP_LOCK_PATH)
        return True
    except Exception as errObj:
        print(f"[遠端控制] 無法保存 panic stop 鎖定狀態：{errObj}")
        try:
            if os.path.exists(tempPath):
                os.remove(tempPath)
        except OSError:
            pass
        return False


def clearPanicStopLock():
    try:
        if os.path.exists(PANIC_STOP_LOCK_PATH):
            os.remove(PANIC_STOP_LOCK_PATH)
        return True
    except OSError as errObj:
        print(f"[遠端控制] 無法清除 panic stop 鎖定狀態：{errObj}")
        return False


async def runRemoteControlHooks(botObj, hookName, **kwargs):
    for cogObj in botObj.cogs.values():
        hook = getattr(cogObj, hookName, None)
        if not callable(hook):
            continue
        try:
            result = hook(**kwargs)
            if inspect.isawaitable(result):
                await result
        except Exception as errObj:
            print(f"[遠端控制] {type(cogObj).__name__}.{hookName} 失敗：{errObj}")


async def generalCheck(interaction: discord.Interaction) -> bool:
    if interaction.user.bot:
        raise app_commands.CheckFailure("不支援機器人觸發。")
    commandObj = getattr(interaction, "command", None)
    commandName = getattr(commandObj, "name", None) or getattr(interaction, "_permission_command_name", None)
    if commandName in MANAGEMENT_COMMAND_NAMES:
        return True
    if commandName in STOP_CONTROL_COMMAND_NAMES:
        return True
    global stopUntilTimestamp, stopLocked
    if stopLocked or (stopUntilTimestamp and time.time() < stopUntilTimestamp):
        raise app_commands.CheckFailure("遠端控制暫停中。")
    return True


class AuthCog(commands.Cog):
    def __init__(self, botObj):
        self.bot = botObj
        self.resumeTask = None
        self.controlLock = asyncio.Lock()

    def cancelResumeTask(self):
        if self.resumeTask and not self.resumeTask.done():
            self.resumeTask.cancel()
        self.resumeTask = None

    async def resumeAfterDelay(self, deadline):
        global stopUntilTimestamp, stopLocked
        try:
            await asyncio.sleep(max(0, deadline - time.time()))
            async with self.controlLock:
                if not stopLocked and stopUntilTimestamp == deadline:
                    stopUntilTimestamp = None
                    await runRemoteControlHooks(self.bot, "resumeRemoteOperations")
                    print("[遠端控制] 暫停時間已到，已恢復一般操作。")
        except asyncio.CancelledError:
            return
        finally:
            if self.resumeTask is asyncio.current_task():
                self.resumeTask = None

    @app_commands.command(name="stop", description="暫停遠端控制")
    async def stopCommand(self, interaction: discord.Interaction, duration: float):
        global stopUntilTimestamp, stopLocked
        if not 0 < duration <= 86400:
            return await interaction.response.send_message(
                "暫停時間必須大於 0 且不超過 86400 秒。", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.controlLock:
            stopLocked = False
            deadline = time.time() + duration
            stopUntilTimestamp = deadline
            self.cancelResumeTask()
            await runRemoteControlHooks(self.bot, "stopRemoteOperations", hard=False)
            self.resumeTask = asyncio.create_task(self.resumeAfterDelay(deadline))
        await interaction.followup.send(
            f"已暫停新指令 {duration:g} 秒；循環操作已停止，shell 程序會繼續執行。",
            ephemeral=True,
        )

    @app_commands.command(name="panic_stop", description="強制停止遠端操作與 Bot 啟動的 shell 程序")
    async def panicStopCommand(self, interaction: discord.Interaction):
        global stopUntilTimestamp, stopLocked
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.controlLock:
            stopLocked = True
            stopUntilTimestamp = None
            self.cancelResumeTask()
            persisted = persistPanicStopLock()
            await runRemoteControlHooks(self.bot, "stopRemoteOperations", hard=True)
        resultText = "已強制停止 Bot 管理的遠端操作與追蹤中的 shell 程序；請使用 `/resume` 恢復接收指令。"
        if not persisted:
            resultText += "\n本機鎖定標記無法保存，若 Bot 重啟，硬鎖可能解除。"
        await interaction.followup.send(resultText, ephemeral=True)

    @app_commands.command(name="resume", description="恢復遠端控制")
    async def resumeCommand(self, interaction: discord.Interaction):
        global stopUntilTimestamp, stopLocked
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.controlLock:
            lockCleared = clearPanicStopLock()
            if lockCleared:
                stopUntilTimestamp = None
                stopLocked = False
                self.cancelResumeTask()
                await runRemoteControlHooks(self.bot, "resumeRemoteOperations")
        if not lockCleared:
            return await interaction.followup.send(
                "無法清除本機硬鎖標記，因此控制仍保持暫停。請檢查程式目錄寫入權限。",
                ephemeral=True,
            )
        await interaction.followup.send(
            "已恢復接收遠端指令；先前停止的循環操作不會自動重啟。",
            ephemeral=True,
        )

    @app_commands.command(name="reject", description="關閉程式")
    async def rejectCommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("已關閉程式。")
        os._exit(0)

    @app_commands.command(name="token", description="寫入 Token")
    async def tokenCommand(self, interaction: discord.Interaction, token: str):
        try:
            with open("BOT_TOKEN.txt", "w", encoding="utf-8") as fileObj:
                fileObj.write(token.strip())
            await interaction.response.send_message("更新成功。")
        except Exception as errObj:
            await interaction.response.send_message(f"失敗：{errObj}")

    @app_commands.command(name="audit_config", description="設定 Google 表單指令稽核目的地")
    @app_commands.describe(
        form_url="Google 表單的 viewform 或 edit 網址",
        entry_id="稽核長答題的預填欄位 ID，例如 123456789",
    )
    async def auditConfigCommand(
        self,
        interaction: discord.Interaction,
        form_url: str,
        entry_id: str,
    ):
        try:
            import auditLog

            auditLog.configureAuditForm(form_url, entry_id)
            await interaction.response.send_message(
                "Google 表單稽核已設定；後續指令會記錄時間、指令名稱、使用者 ID、伺服器 ID 與來源，不會記錄參數或輸出。",
                ephemeral=True,
            )
        except ValueError as errObj:
            await interaction.response.send_message(str(errObj), ephemeral=True)
        except Exception as errObj:
            print(f"[稽核] 無法寫入稽核設定：{type(errObj).__name__}")
            await interaction.response.send_message("無法寫入稽核設定檔，請檢查程式目錄權限。", ephemeral=True)

    @app_commands.command(name="help", description="幫助與回饋")
    async def helpCommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("請使用 /cmdlist 檢視指令表。")


async def setup(botObj: commands.Bot):
    await botObj.add_cog(AuthCog(botObj))


def applyGeneralChecks(botObj: commands.Bot):
    for cmdObj in botObj.tree.get_commands():
        if cmdObj.name in MANAGEMENT_COMMAND_NAMES:
            continue
        if generalCheck not in cmdObj.checks:
            cmdObj.checks.append(generalCheck)
