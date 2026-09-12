import re
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
                cmdDict = {}
                for cogName in self.bot.cogs:
                    cogObj = self.bot.get_cog(cogName)
                    cogCmds = getattr(cogObj, "get_app_commands", None)
                    if callable(cogCmds):
                        cmdDict.update({cmdObj.name: (cmdObj, cogObj) for cmdObj in cogCmds()})
                    elif hasattr(cogObj, "__cog_app_commands__"):
                        cmdDict.update({cmdObj.name: (cmdObj, cogObj) for cmdObj in cogObj.__cog_app_commands__})

                for segStr in [s.strip() for s in contentStr.strip().split("--") if s.strip()]:
                    matchObj = re.match(r"^(\w+)(?:\((.*?)\))?$", segStr)
                    if not matchObj:
                        continue

                    cmdName = matchObj.group(1).lower()
                    paramStr = matchObj.group(2)
                    
                    if cmdName in cmdDict:
                        targetCmd, targetCog = cmdDict[cmdName]
                        sigObj = inspect.signature(targetCmd.callback)
                        
                        data_params = [p for p in sigObj.parameters.values() if p.name not in ('self', 'interaction')]
                        all_params_str = ", ".join([f"{p.name}" + (f"={p.default}" if p.default != inspect.Parameter.empty else "") for p in data_params])
                        required_params = [p for p in data_params if p.default == inspect.Parameter.empty and p.name != "image"]

                        if not paramStr:
                            if required_params:
                                example_args = ", ".join(f"{p.name}=值" for p in required_params)
                                help_msg = f"【提示】指令 `--{cmdName}` 需要參數。\n**語法**：`--{cmdName}({all_params_str})`\n**範例**：`--{cmdName}({example_args})`"
                                await msgObj.channel.send(help_msg)
                                continue
                            paramsDict = {}
                        else:
                            paramsDict = {}
                            for p in paramStr.split(","):
                                if "=" in p:
                                    k, v = p.split("=", 1)
                                    paramsDict[k.strip()] = v.strip()

                        kwargsDict = {}
                        for paramName, paramVal in paramsDict.items():
                            if paramName in sigObj.parameters:
                                annoType = sigObj.parameters[paramName].annotation
                                if annoType is float:
                                    try: kwargsDict[paramName] = float(paramVal)
                                    except ValueError: pass
                                elif annoType is int:
                                    try: kwargsDict[paramName] = int(paramVal)
                                    except ValueError: pass
                                else:
                                    kwargsDict[paramName] = paramVal

                        if cmdName == "screenshot_notify" and msgObj.attachments:
                            kwargsDict["image"] = msgObj.attachments[0]

                        fakeInterObj = FakeInteraction(msgObj)
                        await targetCmd.callback(targetCog, fakeInterObj, **kwargsDict)

            except Exception as errObj:
                await msgObj.channel.send(f"執行失敗：{errObj}")
            return

        await self.bot.process_commands(msgObj)

async def setup(botObj: commands.Bot):
    await botObj.add_cog(EventCog(botObj))
