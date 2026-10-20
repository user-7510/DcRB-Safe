import time
import os
import discord
from discord import app_commands
from discord.ext import commands


stopUntilTimestamp = None
MANAGEMENT_COMMAND_NAMES = {"admin_setup", "access_scope", "access_logout"}


async def generalCheck(interaction: discord.Interaction) -> bool:
    if interaction.user.bot:
        raise app_commands.CheckFailure("不支援機器人觸發。")
    commandObj = getattr(interaction, "command", None)
    commandName = getattr(commandObj, "name", None) or getattr(interaction, "_permission_command_name", None)
    if commandName in MANAGEMENT_COMMAND_NAMES:
        return True
    global stopUntilTimestamp
    if stopUntilTimestamp and time.time() < stopUntilTimestamp:
        raise app_commands.CheckFailure("遠端控制暫停中。")
    return True


class AuthCog(commands.Cog):
    def __init__(self, botObj):
        self.bot = botObj

    @app_commands.command(name="stop", description="暫停遠端控制")
    async def stopCommand(self, interaction: discord.Interaction, duration: float):
        global stopUntilTimestamp
        stopUntilTimestamp = time.time() + duration
        await interaction.response.send_message(f"已暫停控制 {duration} 秒。")

    @app_commands.command(name="reject", description="關閉程式")
    async def rejectCommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("已關閉程式。")
        os._exit(0)

    @app_commands.command(name="token", description="寫入 Token")
    async def tokenCommand(self, interaction: discord.Interaction, token: str):
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


def applyGeneralChecks(botObj: commands.Bot):
    for cmdObj in botObj.tree.get_commands():
        if cmdObj.name in MANAGEMENT_COMMAND_NAMES:
            continue
        if generalCheck not in cmdObj.checks:
            cmdObj.checks.append(generalCheck)
