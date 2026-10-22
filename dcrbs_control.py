import io
import os
import time
import asyncio
import threading
import subprocess
import ctypes
import multiprocessing
import mss
import mss.tools
import pyautogui
import psutil
import discord
from discord import app_commands
from discord.ext import commands

pyautogui.FAILSAFE = False

def displayImageProcess(imgBytes: bytes):
    import tkinter as tk
    from PIL import Image, ImageTk
    rootNode = tk.Tk()
    rootNode.withdraw()
    winNode = tk.Toplevel(rootNode)
    winNode.title("圖片通知")
    winNode.attributes('-topmost', True)
    photoObj = ImageTk.PhotoImage(Image.open(io.BytesIO(imgBytes)))
    labelObj = tk.Label(winNode, image=photoObj)
    labelObj.image = photoObj
    labelObj.pack()
    winNode.after(10000, rootNode.destroy)
    rootNode.mainloop()

class ControlCog(commands.Cog):
    def __init__(self, botObj):
        self.bot = botObj
        self.blackListSet = set()
        self.monitorOffEvent = threading.Event()
        self.closeLoopEvent = threading.Event()
        self.blackListLock = threading.Lock()
        self.blackListMonitorEnabled = threading.Event()
        self.blackListMonitorEnabled.set()
        self.blackListMonitorWake = threading.Event()
        self.remoteOperationLock = threading.Lock()
        self.remoteOperationsPaused = False
        self.inputStopEvents = set()
        self.startBlacklistMonitor()

    def startInputTask(self, taskFunc):
        stopEvent = threading.Event()
        with self.remoteOperationLock:
            if self.remoteOperationsPaused:
                return False
            self.inputStopEvents.add(stopEvent)

        def runTask():
            try:
                taskFunc(stopEvent)
            except Exception as errObj:
                print(f"[控制] 背景輸入工作失敗：{type(errObj).__name__}: {errObj}")
            finally:
                with self.remoteOperationLock:
                    self.inputStopEvents.discard(stopEvent)

        threading.Thread(target=runTask, daemon=True).start()
        return True

    def stopRemoteOperations(self, hard=False):
        with self.remoteOperationLock:
            self.remoteOperationsPaused = True
            self.closeLoopEvent.set()
            self.monitorOffEvent.set()
            self.blackListMonitorEnabled.clear()
            self.blackListMonitorWake.set()
            stopEvents = list(self.inputStopEvents)
        for stopEvent in stopEvents:
            stopEvent.set()

    def resumeRemoteOperations(self):
        with self.remoteOperationLock:
            self.remoteOperationsPaused = False
            self.blackListMonitorEnabled.set()
            self.blackListMonitorWake.set()

    def startBlacklistMonitor(self):
        def monitorLoopTask():
            while True:
                if not self.blackListMonitorEnabled.is_set():
                    self.blackListMonitorWake.wait(0.5)
                    self.blackListMonitorWake.clear()
                    continue
                with self.blackListLock:
                    blackListSnapshot = tuple(self.blackListSet)
                if blackListSnapshot:
                    for procObj in psutil.process_iter(['name']):
                        if not self.blackListMonitorEnabled.is_set():
                            break
                        procName = (procObj.info.get('name') or '').lower()
                        if any(keyword in procName for keyword in blackListSnapshot):
                            try:
                                procObj.kill()
                            except Exception:
                                pass
                self.blackListMonitorWake.wait(5)
                self.blackListMonitorWake.clear()
        threading.Thread(target=monitorLoopTask, daemon=True).start()

    @app_commands.command(name="txt", description="傳送文字到電腦端")
    async def txtCommand(self, interaction: discord.Interaction, text: str):
        try:
            desktopPath = os.path.join(os.path.expanduser("~"), "Desktop")
            filePath = os.path.join(desktopPath if os.path.isdir(desktopPath) else os.getcwd(), "tmp.txt")
            with open(filePath, "w", encoding="utf-8") as fileObj:
                fileObj.write(text or "")
        except Exception as errObj:
            return await interaction.response.send_message(f"寫入失敗：{errObj}", ephemeral=True)
        
        def openAndDelTask():
            try:
                os.startfile(filePath)
            except Exception:
                pass
            time.sleep(60)
            try:
                os.remove(filePath)
            except Exception:
                pass
        
        threading.Thread(target=openAndDelTask, daemon=True).start()
        await interaction.response.send_message("已傳送。")

    @app_commands.command(name="msg", description="顯示訊息通知")
    async def msgCommand(self, interaction: discord.Interaction, text: str):
        threading.Thread(target=ctypes.windll.user32.MessageBoxW, args=(None, text, "通知", 0x40000), daemon=True).start()
        await interaction.response.send_message("已顯示通知。")

    @app_commands.command(name="web", description="開啟網頁")
    async def webCommand(self, interaction: discord.Interaction, url: str):
        pathsList = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
        chromePath = next((p for p in pathsList if os.path.exists(p)), None)
        if chromePath:
            subprocess.Popen([chromePath, url])
        else:
            os.startfile(url)
        await interaction.response.send_message(f"已開啟: {url}")

    @app_commands.command(name="key", description="按鍵模擬")
    async def keyCommand(self, interaction: discord.Interaction, keys: str):
        keyList = keys.split()
        if not keyList:
            return await interaction.response.send_message("請提供至少一個按鍵。", ephemeral=True)
        def keyTask(stopEvent):
            if stopEvent.is_set():
                return
            if len(keyList) > 1:
                pyautogui.hotkey(*keyList)
            else:
                pyautogui.press(keyList[0])
        if not self.startInputTask(keyTask):
            return await interaction.response.send_message("遠端控制暫停中。", ephemeral=True)
        await interaction.response.send_message(f"已按鍵: {keys}")

    @app_commands.command(name="keyboard", description="輸入字串")
    async def keyboardCommand(self, interaction: discord.Interaction, keys: str):
        await interaction.response.defer(ephemeral=True, thinking=True)

        def keyboardTask(stopEvent):
            # Import the native keyboard hook outside Discord's event loop.
            # Some systems can stall while this package initializes its hook.
            import keyboard

            for character in keys:
                if stopEvent.is_set():
                    break
                keyboard.write(character)
        if not self.startInputTask(keyboardTask):
            return await interaction.followup.send("遠端控制暫停中，未執行輸入。", ephemeral=True)
        await interaction.followup.send("已開始背景輸入。", ephemeral=True)

    @app_commands.command(name="key_wait", description="間隔輸入")
    async def keyWaitCommand(self, interaction: discord.Interaction, keys: str, interval: float):
        if not 0 <= interval <= 60:
            return await interaction.response.send_message(
                "輸入間隔必須介於 0 至 60 秒。", ephemeral=True
            )
        def keyWaitTask(stopEvent):
            for keyVal in keys.split():
                if stopEvent.is_set():
                    break
                pyautogui.press(keyVal)
                if stopEvent.wait(interval):
                    break
        if not self.startInputTask(keyWaitTask):
            return await interaction.response.send_message("遠端控制暫停中。", ephemeral=True)
        await interaction.response.send_message("已逐鍵輸入。")

    @app_commands.command(name="close", description="關閉視窗")
    async def closeCommand(self, interaction: discord.Interaction, keyword: str):
        import pygetwindow as gw
        countVal = 0
        for winObj in gw.getWindowsWithTitle(keyword):
            try:
                winObj.close()
                countVal += 1
            except Exception:
                pass
        await interaction.response.send_message(f"嘗試關閉 {countVal} 個視窗。")

    @app_commands.command(name="close_loop", description="循環關閉視窗")
    async def closeLoopCommand(self, interaction: discord.Interaction, interval: float, keyword: str):
        if not 0.1 <= interval <= 3600:
            return await interaction.response.send_message(
                "循環間隔必須介於 0.1 至 3600 秒。", ephemeral=True
            )
        import pygetwindow as gw
        def closeLoopTask():
            while not self.closeLoopEvent.is_set():
                for winObj in gw.getWindowsWithTitle(keyword):
                    if self.closeLoopEvent.is_set():
                        break
                    try:
                        winObj.close()
                    except Exception:
                        pass
                self.closeLoopEvent.wait(interval)
        with self.remoteOperationLock:
            paused = self.remoteOperationsPaused
            if not paused:
                self.closeLoopEvent.clear()
                threading.Thread(target=closeLoopTask, daemon=True).start()
        if paused:
            return await interaction.response.send_message("遠端控制暫停中。", ephemeral=True)
        await interaction.response.send_message("啟動循環關閉。")

    @app_commands.command(name="close_stop", description="停止循環關閉視窗")
    async def closeStopCommand(self, interaction: discord.Interaction):
        self.closeLoopEvent.set()
        await interaction.response.send_message("停止循環關閉。")

    @app_commands.command(name="monitor_off", description="關閉螢幕")
    async def monitorOffCommand(self, interaction: discord.Interaction, interval: float):
        if not 0.1 <= interval <= 3600:
            return await interaction.response.send_message(
                "循環間隔必須介於 0.1 至 3600 秒。", ephemeral=True
            )
        def monitorOffTask():
            while not self.monitorOffEvent.is_set():
                ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)
                self.monitorOffEvent.wait(interval)
        with self.remoteOperationLock:
            paused = self.remoteOperationsPaused
            if not paused:
                self.monitorOffEvent.clear()
                threading.Thread(target=monitorOffTask, daemon=True).start()
        if paused:
            return await interaction.response.send_message("遠端控制暫停中。", ephemeral=True)
        await interaction.response.send_message("已關閉螢幕。")

    @app_commands.command(name="monitor_on", description="開啟螢幕")
    async def monitorOnCommand(self, interaction: discord.Interaction):
        self.monitorOffEvent.set()
        ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, -1)
        await interaction.response.send_message("螢幕自動關閉已停止。")

    @app_commands.command(name="screenshot", description="螢幕截圖")
    async def screenshotCommand(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        def captureTask():
            with mss.mss() as sctObj:
                imgRaw = sctObj.grab(sctObj.monitors[0])
                return mss.tools.to_png(imgRaw.rgb, imgRaw.size)
        
        pngBytes = await asyncio.to_thread(captureTask)
        bufferObj = io.BytesIO(pngBytes)
        bufferObj.seek(0)
        await interaction.followup.send(file=discord.File(fp=bufferObj, filename='screenshot.png'))

    @app_commands.command(name="screenshot_notify", description="圖片通知")
    async def screenshotNotifyCommand(self, interaction: discord.Interaction, image: discord.Attachment):
        await interaction.response.defer(thinking=True)
        imgBytes = await image.read()
        procObj = multiprocessing.Process(target=displayImageProcess, args=(imgBytes,), daemon=True)
        procObj.start()
        await interaction.followup.send("已顯示。")

    @app_commands.command(name="blackade", description="封鎖處理程序")
    async def blackadeCommand(self, interaction: discord.Interaction, keywords: str):
        targetList = [item.lower().strip() for item in keywords.split()]
        with self.blackListLock:
            self.blackListSet.update(targetList)
        await interaction.response.send_message(f"已將 {', '.join(targetList)} 加入黑名單。")

    @app_commands.command(name="unblackade", description="解鎖處理程序")
    async def unblackadeCommand(self, interaction: discord.Interaction, keywords: str):
        targetList = [item.lower().strip() for item in keywords.split()]
        with self.blackListLock:
            for itemStr in targetList:
                self.blackListSet.discard(itemStr)
        await interaction.response.send_message("已解除封鎖。")

async def setup(botObj: commands.Bot):
    await botObj.add_cog(ControlCog(botObj))
