import time
import os
import discord
from discord import app_commands
from discord.ext import commands

stopUntilTimestamp = None

def getAuthSecret() -> str:
    secretPath = "auth_secret.txt"
    if not os.path.exists(secretPath):
        with open(secretPath, "w", encoding="utf-8") as fileObj:
            fileObj.write("defaultPassword")
    with open(secretPath, "r", encoding="utf-8") as fileObj:
        return fileObj.read().strip()

async def generalCheck(interaction: discord.Interaction) -> bool:
    if interaction.user.bot:
        raise app_commands.CheckFailure("不支援機器人觸發。")
    global stopUntilTimestamp
    if stopUntilTimestamp and time.time() < stopUntilTimestamp:
        raise app_commands.CheckFailure("遠端控制暫停中。")
    return True

class AuthCog(commands.Cog):
    def __init__(self, botObj):
        self.bot = botObj

    @app_commands.command(name="stop", description="暫停遠端控制")
    async def stopCommand(self, interaction: discord.Interaction, duration: float, keywords: str):
        global stopUntilTimestamp
        if keywords != getAuthSecret():
            return await interaction.response.send_message("驗證失敗；未執行。", ephemeral=True)
        stopUntilTimestamp = time.time() + duration
        await interaction.response.send_message(f"已暫停控制 {duration} 秒。")

    @app_commands.command(name="reject", description="關閉程式")
    async def rejectCommand(self, interaction: discord.Interaction, names: str):
        if names == getAuthSecret():
            await interaction.response.send_message("已關閉程式。")
            os._exit(0)
        await interaction.response.send_message("密碼錯誤。")

    @app_commands.command(name="token", description="寫入 Token")
    async def tokenCommand(self, interaction: discord.Interaction, token: str, password: str):
        if password != getAuthSecret():
            return await interaction.response.send_message("密碼錯誤。", ephemeral=True)
        try:
            with open("BOT_TOKEN.txt", "w", encoding="utf-8") as fileObj:
                fileObj.write(token.strip())
            await interaction.response.send_message("更新成功。")
        except Exception as errObj:
            await interaction.response.send_message(f"失敗：{errObj}")

    @app_commands.command(name="help", description="幫助與回饋")
    async def helpCommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("請使用 /cmdlist 檢視指令表。")

async def setup(botObj: commands.Bot):
    await botObj.add_cog(AuthCog(botObj))
    for cmdObj in botObj.tree.get_commands():
        cmdObj.checks.append(generalCheck)
