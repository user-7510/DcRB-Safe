# 注意！！！本倉庫目前屬於Beta版本，如需穩定版請至原Repo下載！！！

# Discord Remote Bot

- 免責聲明：本程式工具僅供用於您有權完全使用之電腦，使用者應為自身一切操作負完全之責任。
- 下載或使用即代表同意。
- Version<=4.0.0 已停止支援。

---

VersionVI 更新摘要：根據 Linux 作業系統與環境差異（GUI 桌面環境與無介面 TTY 模式），系統可透過 `platform.system()` 與環境變數 `DISPLAY` / `WAYLAND_DISPLAY` 進行自動辨識並載入適配模組。

---

# DcRB (Discord Remote Bot) VersionVI README

DcRB 為基於 Discord API 構建的遠端自動化管理系統。支援 Windows 與 Linux（桌面環境及純 TTY 終端機）雙系統自動識別與動態模組載入。

## 前置作業 (Privileged Intents)

由於程式核心初始化時宣告了 `discord.Intents.all()`，根據 API 規範，開發者必須前往 Discord Developer Portal，在應用程式的「Bot」設定頁面中，手動開啟以下三個特權意圖，否則啟動時將拋出錯誤 (Rapp, 2020)：
- Presence Intent
- Server Members Intent
- Message Content Intent

## 環境建置與啟動

系統讀取本地 `BOT_TOKEN.txt` 檔案作為 Discord Bot 驗證金鑰，無須設定系統環境變數。密碼驗證將於首次載入 `authModule` 時自動生成 `auth_secret.txt`。

```bash
pip install discord.py aiohttp psutil pyautogui mss pygetwindow pycaw keyboard Pillow
python main.py
```

行 1：安裝專案運作所需之所有第三方套件，包含處理圖片通知必備的 Pillow。
行 2：啟動主執行緒，系統將自動判斷作業系統並對應載入組態。
