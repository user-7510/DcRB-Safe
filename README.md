# DcRB (Discord Remote Bot)

DcRB 是透過 Discord 斜線指令或文字指令操作本機的 Bot。請只在自己有權管理的電腦和 Discord 伺服器使用。本專案目前為 Beta 版本。

## 安裝與啟動

需求套件列於 [requirements.txt](requirements.txt)，包含 `discord.py`、`aiohttp`、`psutil`、`pyautogui`、`mss`、`pygetwindow`、`pycaw`、`keyboard` 和 `Pillow`。各平台會載入不同模組；部分套件及指令只適用於 Windows 或 Linux。

```bash
python -m pip install -r requirements.txt
```

在程式目錄建立 `BOT_TOKEN.txt`，填入 Discord Bot Token，然後從終端啟動：

```bash
python main.py
```

Windows 也可用 `python main.pyw` 啟動。若首次設定密碼時沒有互動式終端，請改由終端執行 `python main.py`。Bot 使用 `discord.Intents.all()`；需在 Discord Developer Portal 為 Bot 開啟 Presence、Server Members 和 Message Content 特權 Intents。

## 啟動及檔案相依性

`main.py` 先將工作目錄切到程式目錄，初始化本機最高管理員密碼，再讀取 `BOT_TOKEN.txt`。登入 Discord 後，程式依 `platform.system()` 載入模組設定：Linux 使用 `modules_linux.json`；其他作業系統使用 `modules.json`。目前其他作業系統會載入 Windows 組態。

每個設定檔列出要載入的 Python 模組。模組的 `setup(bot)` 會註冊 Cog 和斜線指令。載入完成後，`main.py` 套用一般檢查及 `accessControl` 分級檢查，再同步指令。若權限模組載入失敗，程式會停止，避免指令在沒有分級授權時運作。

| 檔案 | 用途與關係 |
|---|---|
| `main.py` | 主入口；初始化密碼、載入平台設定、載入模組、套用檢查、同步 Discord 指令，並還原開機指令。 |
| `main.pyw` | Windows 啟動包裝器，呼叫 `main.main()`。 |
| `modules.json` | Windows 模組：`authModule`、`controlModule`、`systemModule`、`eventModule`、`accessControl`。 |
| `modules_linux.json` | Linux 模組：`authModule`、`linuxModule`、`accessControl`。 |
| `accessControl.py` | 最高管理員登入、分級白名單、伺服器範圍使用者與角色設定。 |
| `authModule.py` | `/stop`、`/reject`、`/token`、`/help`，以及一般互動檢查。 |
| `controlModule.py` | Windows 螢幕、鍵盤、視窗、程序、文字及通知控制。 |
| `systemModule.py` | Windows 裝置資訊、CMD／PowerShell、音量、關機與開機設定。 |
| `linuxModule.py` | Linux 裝置資訊、Bash、關機及程序列表。 |
| `eventModule.py` | 接收以 `--` 開頭的 Discord 文字訊息，交由共用解析器處理。 |
| `command_dispatch.py` | 供文字訊息與開機設定共用的指令解析、參數轉換及 callback 分派。 |
| `dcrb_usage.csv` | `/cmdlist` 使用的指令說明表。 |
| `requirements.txt` | Python 第三方套件清單。 |

模組依賴簡圖：

```text
main.py ──讀取──> modules.json 或 modules_linux.json
  ├──載入──> authModule / controlModule / systemModule / eventModule / linuxModule / accessControl
  ├──套用檢查──> authModule.generalCheck + accessControl.checkCommandAccess
  └──啟動指令──> command_dispatch.dispatchTextCommands

eventModule ──文字指令──> command_dispatch ──查找已載入 Cog──> 指令 callback
```

## 權限管理

所有 Bot 操作指令均由最高管理員設定的分級白名單授權，不再要求各指令另帶密碼。一般指令使用數字較小、權限較高的層級：

| 層級 | 身分範圍 |
|---|---|
| 1 | 最高管理員使用者 ID；不接受角色。 |
| 2 | 管理員層級；可指定使用者 ID 或角色 ID。 |
| 3 | 操作員層級；可指定使用者 ID 或角色 ID。 |

預設分級：

- **層級 1**：`stop`、`reject`、`token`、`shutdown`、`startup`、`shell_startup`、`reg_startup`
- **層級 2**：`powershell`、`cmd`、`key`、`keyboard`、`key_wait`
- **層級 3**：`web`、`blackade`、`unblackade`、`txt`、`msg`、`close`、`close_loop`、`close_stop`、`monitor_off`、`monitor_on`、`screenshot`、`screenshot_notify`、`device`、`volume`、`task_list`、`cmdlist`、`help`
- 新增但未列入設定的指令預設要求層級 1。分級可在本機 `access_control.json` 的 `command_levels` 調整。

首次從終端啟動時，程式會提示電腦使用者設定並確認最高管理員密碼，要求 12 至 128 個字元。密碼以隨機 salt 的 scrypt 雜湊寫入 `owner_password.hash`，不以明文保存。舊版若有 `owner_password.txt`，程式會將其轉成雜湊並移除明文檔。

1. 在 Discord 伺服器執行 `/admin_setup`，於私密視窗輸入本機最高管理員密碼。登入工作階段有效 10 分鐘。
2. 執行 `/access_scope`，選擇加入、移除或列出，接著指定層級、使用者或角色及目標 ID。層級 1 只能設定使用者。
3. 執行 `/access_logout` 可提早結束自己的管理工作階段。

`owner_password.hash`、`access_control.json` 與其他本機設定檔已加入 `.gitignore`。修改最高管理員密碼時，刪除 `owner_password.hash`，再從終端重新啟動並設定新密碼。舊版留下的 `auth_secret.txt` 和 `password.json` 不再由程式讀取或更新；忽略規則保留以免遺留檔案被提交。

## 指令使用方式

斜線指令在 Discord 中執行。Windows 和 Linux 各自提供平台適用的系統指令；詳細清單可執行 `/cmdlist`，來源是 `dcrb_usage.csv`。

Windows 文字指令由 `eventModule` 接收，格式為 `--指令名稱(參數=值)`，例如：

```text
--web(url=https://example.com)
--key(keys=ctrl c)
```

文字訊息和一般斜線指令套用相同的分級檢查。`/admin_setup`、`/access_scope`、`/access_logout` 僅能透過斜線指令使用。Linux 組態目前沒有載入 `eventModule`，因此不提供 `--` 文字指令。

`/startup` 可將 `--` 指令文字和伺服器 ID 寫入 `config.json`；下次啟動並連線 Discord 後會還原執行。這項設定會由可使用層級 1 指令的管理員建立，啟動時作為已設定的自動化執行。

## 本機執行期資料

| 檔案 | 用途 |
|---|---|
| `BOT_TOKEN.txt` | Discord Bot Token。`/token` 預設要求層級 1。 |
| `owner_password.hash` | 最高管理員密碼雜湊。 |
| `access_control.json` | 各伺服器的指令分級與使用者／角色白名單。 |
| `config.json` | `/startup` 保存的自動執行文字及伺服器 ID。 |
| `auth_secret.txt`、`password.json` | 舊版遺留檔案；目前程式不讀寫、不再要求其密碼。 |

`packages/` 中的 ZIP 是舊版本封存檔，不會由目前的 `main.py` 載入。
