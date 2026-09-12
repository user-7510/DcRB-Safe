# 注意！！！本倉庫目前屬於Beta版本，如需穩定版請至原Repo下載！！！

# Discord Remote Bot

- 免責聲明：本程式工具僅供用於您有權完全使用之電腦，使用者應為自身一切操作負完全之責任。
- 下載或使用即代表同意。
- Version<=4.0.0 已停止支援。

---

VersionVI - 升級更新摘要：
1. **指令衝突與跨模組相依性修正**：消除了原本相同命名指令在內部呼叫上的衝突，並支援全域遍歷跨模組 (Cogs) 的動態指令呼叫。
2. **開機啟動設定配置升級**：系統 `/startup` 格式由 `config.txt` 轉為以 JSON (`config.json`) 儲存，且支援綁定設定該開機指令的 Discord 伺服器 (Server ID)；重啟後開機指令輸出結果將準確回傳至該伺服器對應的權限頻道。
3. **Event 參數防呆機制**：輸入 `--指令名稱` 事件指令若缺少必要參數時，不會再被無聲吞沒報錯，而是會自動回傳該指令所需的參數提示與範例。
4. **OS 環境自動偵測**：根據 Linux 作業系統與環境差異（GUI 桌面環境與無介面 TTY 模式），系統可透過 `platform.system()` 與環境變數 `DISPLAY` / `WAYLAND_DISPLAY` 進行自動辨識並載入適配模組。

---

# DcRB (Discord Remote Bot) README

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

## 事件指令與自動執行 (JSON組態)

* 您可於任一文字頻道輸入 `--cmdName(param=value, ...)` 來快速執行事件。當未輸入必要參數時，機器人會智慧回傳語法提示與範例。
* 透過 `/startup` 指令設定的開機指令會自動儲存於 `config.json` 中，並記錄當前伺服器 ID。下次程式啟動時，機器人會在該伺服器自動還原執行狀態並發送執行結果。

## 密碼驗證提示

- 某些指令需要密碼參數，參數名通常是password，/reject的name參數也是密碼，本程式的密碼共有兩組，一組為defaultPassword存於`./auth_secret.txt`中，為/reject指令的密碼，只能從本機手動修改；另一組可以用/change_password指令改，預設密碼為admin。
- 一直顯示密碼錯誤時可以檢查本機的密碼檔案。
