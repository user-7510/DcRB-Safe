import discord
from discord.ext import commands
from dcrbs_command_dispatch import dispatchTextCommands

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
            commandPreview = contentStr.strip().splitlines()[0][:100]
            print(f"[文字指令] 收到 {commandPreview}（使用者 ID：{msgObj.author.id}）")
            try:
                fakeInterObj = FakeInteraction(msgObj)
                attachment = msgObj.attachments[0] if msgObj.attachments else None
                await dispatchTextCommands(
                    self.bot,
                    contentStr,
                    fakeInterObj,
                    attachment=attachment,
                )
            except Exception as errObj:
                print(f"[文字指令] 分派失敗：{type(errObj).__name__}: {errObj}")
                try:
                    await msgObj.channel.send("文字指令處理失敗，請管理員查看 Bot 主控台紀錄。")
                except Exception as replyErr:
                    print(f"[文字指令] 無法傳送錯誤回覆：{type(replyErr).__name__}: {replyErr}")
            return

        await self.bot.process_commands(msgObj)

async def setup(botObj: commands.Bot):
    await botObj.add_cog(EventCog(botObj))
