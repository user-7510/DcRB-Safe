import os
import sys
import json
import platform
import importlib
import multiprocessing
import discord
from discord import app_commands
from discord.ext import commands
from command_dispatch import dispatchTextCommands

dcrbVersion = "6.0.0"

class BotRunner(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.loadedModules = []

    async def setup_hook(self):
        print("[資訊] 開始執行初始化設定...")
        configFilePath = self.detectEnvironmentConfig()
        await self.loadModulesFromJson(configFilePath)
        if "accessControl" not in self.loadedModules:
            raise RuntimeError("權限模組載入失敗，為避免未受控指令執行，停止啟動。")
        if "authModule" in self.loadedModules:
            import authModule
            authModule.applyGeneralChecks(self)
        if "accessControl" in self.loadedModules:
            import accessControl
            accessControl.applyAccessChecks(self)
        
        self.tree.on_error = self.onAppCommandError
        syncedCmds = await self.tree.sync()
        print(f"[資訊] 成功同步 {len(syncedCmds)} 個應用程式指令")
        self.loop.create_task(self.executeStartupConfig())

    def detectEnvironmentConfig(self) -> str:
        currentOs = platform.system()
        print(f"[資訊] 偵測到執行環境作業系統: {currentOs}")
        if currentOs == "Linux":
            configPath = "modules_linux.json"
        else:
            configPath = "modules.json"
        
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
        if not os.path.exists("config.json"):
            return
            
        try:
            with open("config.json", "r", encoding="utf-8") as fileObj:
                configData = json.load(fileObj)
        except Exception as e:
            print(f"[錯誤] 無法讀取 config.json: {e}")
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

            async def defer(self, *, thinking=False):
                pass

        class StartupRealFollowup:
            async def send(self, **kwargs):
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
        )

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            commandName = interaction.data.get("name", "unknown")
            userName = interaction.user.name
            print(f"[指令] 收到來自使用者 {userName} 的指令: /{commandName}")

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

def readTokenFromFile(tokenFilePath: str = "BOT_TOKEN.txt") -> str:
    if os.path.exists(tokenFilePath):
        print(f"[資訊] 讀取 Token 檔案: {tokenFilePath}")
        with open(tokenFilePath, "r", encoding="utf-8") as tokenFile:
            return tokenFile.read().strip()
    print(f"[警告] 找不到 Token 檔案: {tokenFilePath}")
    return ""

botInstance = BotRunner(command_prefix="!", intents=discord.Intents.all())

def main():
    os.chdir(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)))
    print(f"[資訊] 工作目錄設定為: {os.getcwd()}")
    try:
        import accessControl
        accessControl.initializeOwnerPassword()
    except Exception as errObj:
        print(f"[錯誤] 最高管理者密碼初始化失敗：{errObj}")
        return
    botToken = readTokenFromFile("BOT_TOKEN.txt")
    if botToken:
        print("[資訊] Bot 正式啟動連線...")
        botInstance.run(botToken)
    else:
        print("[錯誤] Bot Token 為空，終止啟動")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
