import os
import sys
import json
import platform
import importlib
import multiprocessing
import discord
from discord import app_commands
from discord.ext import commands
from dcrbs_command_dispatch import dispatchTextCommands
from dcrbs_version import __version__
from dcrbs_runtime.paths import ensureRuntimeFiles, resolveRuntimeDirectory

dcrbsVersion = __version__

class BotRunner(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.loadedModules = []
        self._shutdownCleanupDone = False

    async def close(self):
        if not self._shutdownCleanupDone:
            self._shutdownCleanupDone = True
            try:
                if "dcrbs_auth" in self.loadedModules:
                    import dcrbs_auth
                    await dcrbs_auth.runRemoteControlHooks(
                        self, "stopRemoteOperations", hard=True
                    )
            finally:
                await super().close()
            if "dcrbs_audit_log" in sys.modules:
                await sys.modules["dcrbs_audit_log"].flushPendingRecords()
            return
        await super().close()

    async def setup_hook(self):
        print("[資訊] 開始執行初始化設定...")
        if not self.intents.message_content:
            print("[警告] Message Content Intent 未啟用，Discord 不會提供文字指令內容。")
        configFilePath = self.detectEnvironmentConfig()
        await self.loadModulesFromJson(configFilePath)
        if "dcrbs_access_control" not in self.loadedModules:
            raise RuntimeError("權限模組載入失敗，為避免未受控指令執行，停止啟動。")
        if "dcrbs_auth" in self.loadedModules:
            import dcrbs_auth
            dcrbs_auth.applyGeneralChecks(self)
            if dcrbs_auth.stopLocked:
                await dcrbs_auth.runRemoteControlHooks(
                    self, "stopRemoteOperations", hard=False
                )
        if "dcrbs_access_control" in self.loadedModules:
            import dcrbs_access_control
            dcrbs_access_control.applyAccessChecks(self)
        
        self.tree.on_error = self.onAppCommandError
        syncedCmds = await self.tree.sync()
        print(f"[資訊] 成功同步 {len(syncedCmds)} 個應用程式指令")
        self.loop.create_task(self.executeStartupConfig())

    def detectEnvironmentConfig(self) -> str:
        currentOs = platform.system()
        print(f"[資訊] 偵測到執行環境作業系統: {currentOs}")
        if currentOs == "Linux":
            configPath = "dcrbs_modules_linux.json"
        else:
            configPath = "dcrbs_modules.json"
        
        print(f"[資訊] 選擇設定檔: {configPath}")
        return configPath

    async def loadModulesFromJson(self, configPath: str):
        if not os.path.exists(configPath):
            print(f"[錯誤] 找不到設定檔 {configPath}，放棄載入模組")
            return
        
        print(f"[資訊] 正在讀取模組設定檔: {configPath}")
        with open(configPath, "r", encoding="utf-8") as configFile:
            configData = json.load(configFile)
        
        moduleList = configData.get("enabledModules", [])
        if not isinstance(moduleList, list):
            print("[警告] enabledModules 格式不正確，改用空模組清單。")
            moduleList = []
        if "dcrbs_events" not in moduleList:
            print("[資訊] 將必要的文字指令模組 dcrbs_events 加入載入清單。")
            moduleList.append("dcrbs_events")
        print(f"[資訊] 預計載入模組列表: {moduleList}")

        for moduleName in moduleList:
            try:
                print(f"[模組] 正在讀入模組: {moduleName}")
                moduleObj = importlib.import_module(moduleName)
                if hasattr(moduleObj, "setup"):
                    await moduleObj.setup(self)
                self.loadedModules.append(moduleName)
                print(f"[模組] 模組 {moduleName} 載入成功")
            except Exception as errObj:
                print(f"[錯誤] 載入模組 {moduleName} 失敗: {errObj}")

    async def executeStartupConfig(self):
        await self.wait_until_ready()
        if "dcrbs_auth" in self.loadedModules:
            import dcrbs_auth
            if dcrbs_auth.stopLocked:
                print("[遠端控制] panic stop 硬鎖啟用中，略過開機指令。")
                return
        if not os.path.exists("dcrbs_startup.json"):
            return
            
        try:
            with open("dcrbs_startup.json", "r", encoding="utf-8") as fileObj:
                configData = json.load(fileObj)
        except Exception as e:
            print(f"[錯誤] 無法讀取 dcrbs_startup.json: {e}")
            return
            
        contentStr = configData.get("content", "").strip()
        guildId = configData.get("guild_id")
        
        if not contentStr.startswith("--") or not guildId:
            return
            
        guildObj = self.get_guild(guildId)
        if not guildObj:
            print(f"[警告] 找不到伺服器 ID: {guildId}，開機指令取消執行。")
            return
            
        channelObj = guildObj.system_channel
        if not channelObj or not channelObj.permissions_for(guildObj.me).send_messages:
            for channel in guildObj.text_channels:
                if channel.permissions_for(guildObj.me).send_messages:
                    channelObj = channel
                    break

        class StartupRealResponse:
            async def send_message(self, content=None, *, ephemeral=False, **kwargs):
                if channelObj:
                    await channelObj.send(content=content, **kwargs)
                else:
                    print(f"[開機指令輸出] {content}")

            async def defer(self, *, thinking=False, ephemeral=False):
                pass

        class StartupRealFollowup:
            async def send(self, **kwargs):
                kwargs.pop("ephemeral", None)
                if channelObj:
                    await channelObj.send(**kwargs)
                else:
                    print("[開機指令輸出] 指令執行完畢。")

        class StartupRealInteraction:
            def __init__(self):
                self.response = StartupRealResponse()
                self.followup = StartupRealFollowup()
                self.guild = guildObj
                self.guild_id = guildId
                self.channel = channelObj
                self.user = guildObj.me
                self.client = guildObj._state._get_client() if hasattr(guildObj, '_state') else None

        fakeInterObj = StartupRealInteraction()
        await dispatchTextCommands(
            self,
            contentStr,
            fakeInterObj,
            promptLabel="開機指令提示",
            errorLabel="開機指令錯誤",
            runChecks=False,
            auditSource="startup",
        )

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            commandName = interaction.data.get("name", "unknown")
            userName = interaction.user.name
            print(f"[指令] 收到來自使用者 {userName} 的指令: /{commandName}")
            try:
                import dcrbs_audit_log

                dcrbs_audit_log.scheduleCommandRecord(
                    interaction,
                    commandName,
                    source="slash",
                    timestamp=interaction.created_at,
                )
            except Exception as errObj:
                print(f"[稽核] 無法排入指令紀錄：{type(errObj).__name__}")

    async def onAppCommandError(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        commandName = interaction.command.name if interaction.command else "未知"
        originalError = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        if isinstance(originalError, discord.NotFound) and originalError.code == 10062:
            print(f"[警告] 指令 /{commandName} 的互動已逾時，請重新執行指令。")
            return

        print(f"[錯誤] 指令 /{commandName} 執行失敗: {error}")
        if interaction.is_expired():
            print(f"[警告] 指令 /{commandName} 的互動已逾時，無法傳送錯誤訊息。")
            return

        try:
            if interaction.response.is_done():
                await interaction.followup.send("指令執行過程發生錯誤。", ephemeral=True)
            else:
                await interaction.response.send_message("指令執行過程發生錯誤。", ephemeral=True)
        except discord.NotFound as responseError:
            if responseError.code == 10062:
                print(f"[警告] 指令 /{commandName} 的互動已逾時，無法傳送錯誤訊息。")
            else:
                print(f"[錯誤] 無法回覆指令 /{commandName} 的錯誤: {responseError}")
        except discord.HTTPException as responseError:
            print(f"[錯誤] 無法回覆指令 /{commandName} 的錯誤: {responseError}")

def readTokenFromFile(tokenFilePath: str = "dcrbs_token.txt") -> str:
    if os.path.exists(tokenFilePath):
        print(f"[資訊] 讀取 Token 檔案: {tokenFilePath}")
        with open(tokenFilePath, "r", encoding="utf-8") as tokenFile:
            return tokenFile.read().strip()
    print(f"[警告] 找不到 Token 檔案: {tokenFilePath}")
    return ""

botInstance = BotRunner(command_prefix="!", intents=discord.Intents.all())

def main(runtime_dir=None):
    if runtime_dir is None and getattr(sys, "frozen", False):
        runtime_dir = os.path.dirname(sys.executable)
    try:
        runtime_dir = resolveRuntimeDirectory(runtime_dir)
        os.chdir(runtime_dir)
        ensureRuntimeFiles(runtime_dir)
    except (OSError, ValueError) as errObj:
        print(f"[錯誤] 無法設定 dcrbs 執行資料夾：{errObj}")
        return
    print(f"[資訊] 工作目錄設定為: {os.getcwd()}")
    try:
        import dcrbs_access_control
        dcrbs_access_control.initializeOwnerPassword()
    except Exception as errObj:
        print(f"[錯誤] 最高管理者密碼初始化失敗：{errObj}")
        return
    botToken = readTokenFromFile("dcrbs_token.txt")
    if botToken:
        print("[資訊] Bot 正式啟動連線...")
        botInstance.run(botToken)
    else:
        print("[錯誤] Bot Token 為空，終止啟動")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
