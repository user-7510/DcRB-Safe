import discord
from discord.ext import commands
from command_dispatch import dispatchTextCommands

class FakeResponse:
    def __init__(self, msgObj: discord.Message):
        self.msgObj = msgObj

    async def send_message(self, content=None, *, ephemeral=False, **kwargs):
        await self.msgObj.channel.send(content=content, **kwargs)

    async def defer(self, *, thinking=False, ephemeral=False):
        pass

class FakeFollowup:
    def __init__(self, msgObj: discord.Message):
        self.msgObj = msgObj

    async def send(self, **kwargs):
        kwargs.pop("ephemeral", None)
        await self.msgObj.channel.send(**kwargs)

class FakeInteraction:
    def __init__(self, msgObj: discord.Message):
        self.msgObj = msgObj
        self.response = FakeResponse(msgObj)
        self.followup = FakeFollowup(msgObj)
        self.user = msgObj.author
        self.guild = msgObj.guild
        self.guild_id = msgObj.guild.id if msgObj.guild else None
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
            fakeInterObj = FakeInteraction(msgObj)
            attachment = msgObj.attachments[0] if msgObj.attachments else None
            await dispatchTextCommands(
                self.bot,
                contentStr,
                fakeInterObj,
                attachment=attachment,
            )
            return

        await self.bot.process_commands(msgObj)

async def setup(botObj: commands.Bot):
    await botObj.add_cog(EventCog(botObj))
