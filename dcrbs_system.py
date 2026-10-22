import os
import sys
import asyncio
import uuid
import socket
import platform
import subprocess
import json
import sysconfig
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from dcrbs_version import __version__ as dcrbsVersion

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


def getDcrbsPywPath():
    candidates = []
    invokedPath = Path(sys.argv[0]).expanduser()
    if invokedPath.name.lower() == "dcrbs.pyw":
        candidates.append(invokedPath)
    candidates.append(Path(__file__).resolve().with_name("dcrbs.pyw"))
    candidates.append(Path(sysconfig.get_path("scripts")) / "dcrbs.pyw")
    try:
        candidates.append(Path(sysconfig.get_path("scripts", scheme="nt_user")) / "dcrbs.pyw")
    except (KeyError, ValueError):
        pass
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    raise FileNotFoundError(
        "找不到 dcrbs.pyw；請確認安裝目錄包含 Windows 啟動包裝器。"
    )


def getPythonwPath():
    interpreterPath = Path(sys.executable).resolve()
    if interpreterPath.name.lower() == "pythonw.exe":
        return str(interpreterPath)
    pythonwPath = interpreterPath.with_name("pythonw.exe")
    if not pythonwPath.is_file():
        raise FileNotFoundError(f"找不到 Python 視窗版執行檔：{pythonwPath}")
    return str(pythonwPath)


def getDcrbsStartupCommand():
    """Return the interpreter and wrapper used by both Windows autostart options."""
    return getPythonwPath(), getDcrbsPywPath()


def escapePowerShellString(value):
    return str(value).replace("'", "''")

class SystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shellProcesses = {}
        self.remoteOperationsPaused = False

    def trackShellProcess(self, processObj):
        self.shellProcesses[processObj.pid] = processObj
        self.shellProcesses = {
            processId: trackedProcess
            for processId, trackedProcess in self.shellProcesses.items()
            if trackedProcess.poll() is None
        }

    async def stopRemoteOperations(self, hard=False):
        self.remoteOperationsPaused = True
        if not hard:
            return
        processIds = [
            processId for processId, processObj in self.shellProcesses.items()
            if processObj.poll() is None
        ]

        def terminateProcessTrees():
            for processId in processIds:
                try:
                    resultObj = subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(processId)],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    if resultObj.returncode != 0:
                        errorText = resultObj.stderr.decode(errors="replace").strip()
                        print(
                            f"[遠端控制] taskkill 無法停止 shell 程序 {processId}："
                            f"{errorText or resultObj.returncode}"
                        )
                except Exception as errObj:
                    print(f"[遠端控制] 無法停止 shell 程序 {processId}：{errObj}")

        await asyncio.to_thread(terminateProcessTrees)
        for processId in processIds:
            self.shellProcesses.pop(processId, None)

    def resumeRemoteOperations(self):
        self.remoteOperationsPaused = False

    @app_commands.command(name="device", description="回傳裝置基本資訊")
    async def deviceCommand(self, interaction: discord.Interaction):
        macRaw = uuid.getnode()
        macAddr = ":".join(f"{(macRaw >> bitShift) & 0xff:02x}" for bitShift in range(40, -1, -8))
        hostName = platform.node() or socket.gethostname()
        msgText = (f"**裝置名稱**：{hostName}\n"
                   f"**IPv4 位址**：{getHostIp()}\n"
                   f"**MAC 位址**：{macAddr}\n"
                   f"**系統型號**：{platform.system()} {platform.release()} ({platform.machine()})\n"
                   f"**dcrbs 版本**：{dcrbsVersion}\n")
        await interaction.response.send_message(msgText)

    @app_commands.command(name="shutdown", description="遠端關機")
    async def shutdownCommand(self, interaction: discord.Interaction):
        os.system("shutdown /s /f /t 0")
        await interaction.response.send_message("系統強制關機中...")

    @app_commands.command(name="cmd", description="執行 CMD 指令")
    async def cmdCommand(self, interaction: discord.Interaction, commands: str):
        if self.remoteOperationsPaused:
            return await interaction.response.send_message("遠端控制暫停中，未執行指令。", ephemeral=True)
        processObj = subprocess.Popen(['cmd', '/k', " & ".join(commands.splitlines())])
        self.trackShellProcess(processObj)
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
        if interaction.guild_id is None:
            return await interaction.response.send_message(
                "`/startup` 需在 Discord 伺服器中設定，因為開機指令會綁定該伺服器。",
                ephemeral=True,
            )
        configData = {
            "guild_id": interaction.guild_id,
            "content": content
        }
        try:
            with open("dcrbs_startup.json", "w", encoding="utf-8") as fileObj:
                json.dump(configData, fileObj, ensure_ascii=False, indent=4)
            await interaction.response.send_message("已成功寫入開機自動執行組態 (JSON)。")
        except Exception as errObj:
            await interaction.response.send_message(f"寫入失敗：{errObj}")

    @app_commands.command(name="shell_startup", description="建立開機自啟動捷徑")
    async def shellStartupCommand(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            pythonwPath, pywPath = getDcrbsStartupCommand()
            runtimeDir = os.getcwd()
            startupDir = subprocess.check_output(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Startup')"], text=True).strip()
            if not startupDir:
                raise RuntimeError("無法取得目前使用者的啟動資料夾路徑。")
            shortcutPath = os.path.join(startupDir, "dcrbs.lnk")
            psCmd = (
                "$shell = New-Object -ComObject WScript.Shell; "
                f"$s = $shell.CreateShortcut('{escapePowerShellString(shortcutPath)}'); "
                f"$s.TargetPath = '{escapePowerShellString(pythonwPath)}'; "
                f"$s.Arguments = '{escapePowerShellString(subprocess.list2cmdline([pywPath]))}'; "
                f"$s.WorkingDirectory = '{escapePowerShellString(runtimeDir)}'; "
                "$s.Save()"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", psCmd], check=True, capture_output=True)
            await interaction.followup.send(f"已建立捷徑，以 pythonw.exe 啟動：{pywPath}")
        except Exception as errObj:
            await interaction.followup.send(f"失敗：{errObj}")

    @app_commands.command(name="reg_startup", description="設定登錄檔開機自啟")
    async def regStartupCommand(self, interaction: discord.Interaction):
        import winreg
        await interaction.response.defer(thinking=True)
        try:
            pythonwPath, pywPath = getDcrbsStartupCommand()
            commandLine = subprocess.list2cmdline([pythonwPath, pywPath])
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as winKey:
                winreg.SetValueEx(winKey, "dcrbs", 0, winreg.REG_SZ, commandLine)
                try:
                    winreg.DeleteValue(winKey, "WindowsExplorer")
                except FileNotFoundError:
                    pass
            await interaction.followup.send(
                "登錄檔自動啟動已設定為 pythonw.exe 執行 dcrbs.pyw。"
                "啟動輸出會寫入執行資料夾的 dcrbs_startup.log。"
            )
        except Exception as errObj:
            await interaction.followup.send(f"失敗：{errObj}")

    @app_commands.command(name="reg_startup_remove", description="取消登錄檔開機自啟")
    async def regStartupRemoveCommand(self, interaction: discord.Interaction):
        import winreg
        await interaction.response.defer(thinking=True)
        try:
            removedValues = []
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_WRITE,
            ) as winKey:
                for valueName in ("dcrbs", "WindowsExplorer"):
                    try:
                        winreg.DeleteValue(winKey, valueName)
                        removedValues.append(valueName)
                    except FileNotFoundError:
                        pass
            if removedValues:
                await interaction.followup.send("已取消 dcrbs 登錄檔自動啟動。")
            else:
                await interaction.followup.send("找不到 dcrbs 登錄檔自動啟動項目，可能已停用。")
        except FileNotFoundError:
            await interaction.followup.send("找不到登錄檔自動啟動項目，可能已停用。")
        except Exception as errObj:
            await interaction.followup.send(f"取消失敗：{errObj}")

    @app_commands.command(name="powershell", description="執行 PowerShell 指令")
    async def powershellCommand(self, interaction: discord.Interaction, commands: str):
        await interaction.response.defer(thinking=True)
        if self.remoteOperationsPaused:
            return await interaction.followup.send("遠端控制暫停中，未執行指令。", ephemeral=True)
        processObj = subprocess.Popen(['powershell', '-NoExit', '-Command', "; ".join(commands.splitlines())], creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.trackShellProcess(processObj)
        await interaction.followup.send("已執行 PowerShell 指令。")

    @app_commands.command(name="task_list", description="前台程式列表")
    async def taskListCommand(self, interaction: discord.Interaction):
        import pygetwindow as gw
        visibleList = [t for t in gw.getAllTitles() if t]
        resText = "前台程式列表：\n" + "\n".join(visibleList) if visibleList else "目前無前台程式。"
        await interaction.response.send_message(resText[:1996] + "..." if len(resText) > 2000 else resText)

    @app_commands.command(name="cmdlist", description="指令列表")
    async def cmdlistCommand(self, interaction: discord.Interaction):
        try:
            with open("dcrbs_usage.csv","r")as f:await interaction.response.send_message(f.read())
        except Exception:
            await interaction.response.send_message(
                "cmd device shutdown volume startup shell_startup reg_startup "
                "reg_startup_remove powershell "
                "task_list cmdlist admin_setup access_scope access_logout"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(SystemCog(bot))
