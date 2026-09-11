import os
import sys
import json
import platform
import importlib
import multiprocessing
import re
import inspect
import discord
from discord import app_commands
from discord.ext import commands

dcrbVersion = "6.0.0"

class StartupFakeResponse:
    async def send_message(self, content=None, *, ephemeral=False, **kwargs):
        print(f"[開機指令輸出] {content}")

    async def defer(self, *, thinking=False):
        pass

class StartupFakeFollowup:
    async def send(self, **kwargs):
        print("[開機指令輸出] 指令執行完畢。")

class StartupFakeInteraction:
    def __init__(self):
        self.response = StartupFakeResponse()
        self.followup = StartupFakeFollowup()

class BotRunner(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.loadedModules = []

    async def setup_hook(self):
        print("[資訊] 開始執行初始化設定...")
        configFilePath = self.detectEnvironmentConfig()
        await self.loadModulesFromJson(configFilePath)
        
        self.tree.on_error = self.onAppCommandError
        syncedCmds = await self.tree.sync()
        print(f"[資訊] 成功同步 {len(syncedCmds)} 個應用程式指令")
        
        await self.executeStartupConfig()

    def detectEnvironmentConfig(self) -> str:
        currentOs = platform.system()
        print(f"[資訊] 偵測到執行環境作業系統: {currentOs}")
        if currentOs == "Linux":
            hasDisplay = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
            if hasDisplay:
                configPath = "modules_linux_desktop.json"
            else:
                configPath = "modules_linux_tty.json"
        else:
            configPath = "modules.json"
        
        print(f"[資訊] 選擇設定檔: {configPath}")
        return configPath

    async def loadModulesFromJson(self, configPath: str):
        if not os.path.exists(configPath):
            print(f"[警告] 找不到指定的設定檔 {configPath}，觸發 Failback 機制")
            fallbackPath = "modules.json"
            if os.path.exists(fallbackPath) and fallbackPath != configPath:
                print(f"[資訊] 使用預設備援設定檔: {fallbackPath}")
                configPath = fallbackPath
            else:
                print("[錯誤] 無法取得有效的模組設定檔，放棄載入模組")
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
        if not os.path.exists("config.txt"):
            return
        with open("config.txt", "r", encoding="utf-8") as fileObj:
            contentStr = fileObj.read().strip()
        if not contentStr.startswith("--"):
            return
            
        controlCogObj = self.get_cog("ControlCog")
        if not controlCogObj:
            return
            
        cmdDict = {}
        cogCmds = getattr(controlCogObj, "get_app_commands", None)
        if callable(cogCmds):
            cmdDict = {cmdObj.name: cmdObj for cmdObj in cogCmds()}
        elif hasattr(controlCogObj, "__cog_app_commands__"):
            cmdDict = {cmdObj.name: cmdObj for cmdObj in controlCogObj.__cog_app_commands__}

        for segStr in [s.strip() for s in contentStr.split("--") if s.strip()]:
            matchObj = re.match(r"^(\w+)(?:\((.*?)\))?$", segStr)
            if not matchObj:
                continue

            cmdName = matchObj.group(1).lower()
            paramStr = matchObj.group(2)
            paramsDict = {}
            if paramStr:
                for p in paramStr.split(","):
                    if "=" in p:
                        k, v = p.split("=", 1)
                        paramsDict[k.strip()] = v.strip()

            if cmdName in cmdDict:
                targetCmd = cmdDict[cmdName]
                sigObj = inspect.signature(targetCmd.callback)
                kwargsDict = {}

                for paramName, paramVal in paramsDict.items():
                    if paramName in sigObj.parameters:
                        annoType = sigObj.parameters[paramName].annotation
                        if annoType is float:
                            kwargsDict[paramName] = float(paramVal)
                        elif annoType is int:
                            kwargsDict[paramName] = int(paramVal)
                        else:
                            kwargsDict[paramName] = paramVal

                fakeInterObj = StartupFakeInteraction()
                await targetCmd.callback(controlCogObj, fakeInterObj, **kwargsDict)

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            commandName = interaction.data.get("name", "unknown")
            userName = interaction.user.name
            print(f"[指令] 收到來自使用者 {userName} 的指令: /{commandName}")

    async def onAppCommandError(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        commandName = interaction.command.name if interaction.command else "未知"
        print(f"[錯誤] 指令 /{commandName} 執行失敗: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("指令執行過程發生錯誤。", ephemeral=True)

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
    botToken = readTokenFromFile("BOT_TOKEN.txt")
    if botToken:
        print("[資訊] Bot 正式啟動連線...")
        botInstance.run(botToken)
    else:
        print("[錯誤] Bot Token 為空，終止啟動")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
