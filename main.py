import os
import sys
import json
import platform
import importlib
import multiprocessing
import discord
from discord.ext import commands

dcrbVersion = "6.0.0"

class BotRunner(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.loadedModules = []

    async def setup_hook(self):
        configFilePath = self.detectEnvironmentConfig()
        await self.loadModulesFromJson(configFilePath)
        await self.tree.sync()

    def detectEnvironmentConfig(self) -> str:
        currentOs = platform.system()
        if currentOs == "Linux":
            hasDisplay = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
            if hasDisplay:
                return "modules_linux_desktop.json"
            return "modules_linux_tty.json"
        return "modules.json"

    async def loadModulesFromJson(self, configPath: str):
        if not os.path.exists(configPath):
            return
        
        with open(configPath, "r", encoding="utf-8") as configFile:
            configData = json.load(configFile)
        
        for moduleName in configData.get("enabledModules", []):
            try:
                moduleObj = importlib.import_module(moduleName)
                if hasattr(moduleObj, "setup"):
                    await moduleObj.setup(self)
                self.loadedModules.append(moduleName)
            except Exception as errObj:
                print(f"載入模組 {moduleName} 失敗: {errObj}")

def readTokenFromFile(tokenFilePath: str = "BOT_TOKEN.txt") -> str:
    if os.path.exists(tokenFilePath):
        with open(tokenFilePath, "r", encoding="utf-8") as tokenFile:
            return tokenFile.read().strip()
    return ""

botInstance = BotRunner(command_prefix="!", intents=discord.Intents.all())

def main():
    os.chdir(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)))
    botToken = readTokenFromFile("BOT_TOKEN.txt")
    if botToken:
        botInstance.run(botToken)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
