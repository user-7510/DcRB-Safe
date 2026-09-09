import os
import sys
import socket
import platform
import subprocess
import psutil
import discord
from discord import app_commands
from discord.ext import commands

def getHostIp():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as socketObj:
            socketObj.connect(("8.8.8.8", 80))
            return socketObj.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "IP_UNKNOWN"

class LinuxCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="device", description="回傳 Linux 裝置資訊")
    async def deviceCommand(self, interaction: discord.Interaction):
        hostName = platform.node() or socket.gethostname()
        displayEnv = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        envType = f"GUI 桌面版 ({displayEnv})" if displayEnv else "純 TTY / 終端機模式"
        
        msgText = (f"**裝置名稱**：{hostName}\n"
                   f"**IPv4 位址**：{getHostIp()}\n"
                   f"**核心版本**：{platform.system()} {platform.release()}\n"
                   f"**執行環境**：{envType}\n")
        await interaction.response.send_message(msgText)

    @app_commands.command(name="cmd", description="執行 Bash 指令")
    async def cmdCommand(self, interaction: discord.Interaction, commands: str):
        await interaction.response.defer(thinking=True)
        try:
            processResult = subprocess.run(
                ["bash", "-c", commands],
                capture_output=True,
                text=True,
                timeout=30
            )
            outputStr = processResult.stdout or processResult.stderr or "指令執行完成，無輸出內容。"
            if len(outputStr) > 1900:
                outputStr = outputStr[:1900] + "\n... (輸出內容過長已截斷)"
            await interaction.followup.send(f"```bash\n{outputStr}\n```")
        except Exception as errObj:
            await interaction.followup.send(f"執行失敗：{errObj}")

    @app_commands.command(name="shutdown", description="關閉 Linux 系統")
    async def shutdownCommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("系統即將關機...")
        subprocess.run(["sudo", "shutdown", "-h", "now"])

    @app_commands.command(name="task_list", description="列出 Linux 執行中進程")
    async def taskListCommand(self, interaction: discord.Interaction):
        processList = []
        for procObj in psutil.process_iter(['pid', 'name', 'username']):
            try:
                processList.append(f"PID: {procObj.info['pid']} | Name: {procObj.info['name']}")
            except Exception:
                pass
        
        resText = "進程列表：\n" + "\n".join(processList[:30])
        await interaction.response.send_message(f"```text\n{resText}\n```")

async def setup(bot: commands.Bot):
    await bot.add_cog(LinuxCog(bot))
