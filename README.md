# DcRB (Discord Remote Bot)

DcRB 是透過 Discord 斜線指令或文字指令操作本機的 Bot。請只在自己有權管理的電腦和 Discord 伺服器使用。本專案目前為 Beta 版本。

## 安裝與啟動

需求套件列於 [requirements.txt](requirements.txt)，包含 `discord.py`、`aiohttp`、`psutil`、`pyautogui`、`mss`、`pygetwindow`、`pycaw`、`keyboard` 和 `Pillow`。各平台會載入不同模組；部分套件及指令只適用於 Windows 或 Linux。

```bash
python -m pip install -r requirements.txt
```

也可使用 `packages/dcrbs_0.0.1.zip` 安裝 pip 套件：

```bash
python -m pip install packages/dcrbs_0.0.1.zip
dcrbs
```

`dcrbs` 會以執行時所在目錄作為執行期資料目錄；請在該目錄建立 `dcrbs_token.txt`。平台模組設定和指令表會在首次啟動時複製到該目錄，既有檔案不會被覆寫。

在程式目錄建立 `dcrbs_token.txt`，填入 Discord Bot Token，然後從終端啟動：

```bash
python dcrbs.py
```

Windows 也可用 `python dcrbs.pyw` 啟動。若首次設定密碼時沒有互動式終端，請改由終端執行 `python dcrbs.py`。Bot 使用 `discord.Intents.all()`；需在 Discord Developer Portal 為 Bot 開啟 Presence、Server Members 和 Message Content 特權 Intents。

## 啟動及檔案相依性

`dcrbs.py` 先將工作目錄切到程式目錄，初始化本機最高管理員密碼，再讀取 `dcrbs_token.txt`。登入 Discord 後，程式依 `platform.system()` 載入模組設定：Linux 使用 `dcrbs_modules_linux.json`；其他作業系統使用 `dcrbs_modules.json`。目前其他作業系統會載入 Windows 組態，**不建議部署於 macOS**，因為 macOS 會載入 Windows 專用模組與指令。

每個設定檔列出要載入的 Python 模組。模組的 `setup(bot)` 會註冊 Cog 和斜線指令。載入完成後，`dcrbs.py` 套用一般檢查及 `dcrbs_access_control` 分級檢查，再同步指令。若權限模組載入失敗，程式會停止，避免指令在沒有分級授權時運作。

| 檔案 | 用途與關係 |
|---|---|
| `dcrbs.py` | 主入口；初始化密碼、載入平台設定、載入模組、套用檢查、同步 Discord 指令，並還原開機指令。 |
| `dcrbs.pyw` | Windows 啟動包裝器，呼叫 `dcrbs.main()`。 |
| `dcrbs_modules.json` | Windows 模組：`dcrbs_auth`、`dcrbs_control`、`dcrbs_system`、`dcrbs_events`、`dcrbs_access_control`。 |
| `dcrbs_modules_linux.json` | Linux 模組：`dcrbs_auth`、`dcrbs_linux`、`dcrbs_events`、`dcrbs_access_control`。 |
| `dcrbs_access_control.py` | 最高管理員登入、分級白名單、伺服器範圍使用者與角色設定。 |
| `dcrbs_auth.py` | `/stop`、`/reject`、`/token`、`/audit_config`、`/help`，以及一般互動檢查。 |
| `dcrbs_audit_log.py` | 將斜線指令與 `--` 文字指令的稽核中繼資料送到部署者設定的 Google 表單。 |
| `dcrbs_control.py` | Windows 螢幕、鍵盤、視窗、程序、文字及通知控制。 |
| `dcrbs_system.py` | Windows 裝置資訊、CMD／PowerShell、音量、關機與開機設定。 |
| `dcrbs_linux.py` | Linux 裝置資訊、Bash、關機及程序列表。 |
| `dcrbs_events.py` | 接收以 `--` 開頭的 Discord 文字訊息，交由共用解析器處理。 |
| `dcrbs_command_dispatch.py` | 供文字訊息與開機設定共用的指令解析、參數轉換及 callback 分派。 |
| `dcrbs_usage.csv` | `/cmdlist` 使用的指令說明表。 |
| `requirements.txt` | Python 第三方套件清單。 |

模組依賴簡圖：

```text
dcrbs.py ──讀取──> dcrbs_modules.json 或 dcrbs_modules_linux.json
  ├──載入──> dcrbs_auth / dcrbs_control / dcrbs_system / dcrbs_events / dcrbs_linux / dcrbs_access_control
  ├──套用檢查──> dcrbs_auth.generalCheck + dcrbs_access_control.checkCommandAccess
  └──啟動指令──> dcrbs_command_dispatch.dispatchTextCommands

dcrbs_events ──文字指令──> dcrbs_command_dispatch ──查找已載入 Cog──> 指令 callback
```

## 權限管理

所有 Bot 操作指令均由最高管理員設定的分級白名單授權，不再要求各指令另帶密碼。一般指令使用數字較小、權限較高的層級：

| 層級 | 身分範圍 |
|---|---|
| 1 | 最高管理員使用者 ID；不接受角色。 |
| 2 | 管理員層級；可指定使用者 ID 或角色 ID。 |
| 3 | 操作員層級；可指定使用者 ID 或角色 ID。 |

預設分級：

- **層級 1**：`stop`、`panic_stop`、`resume`、`reject`、`token`、`shutdown`、`startup`、`shell_startup`、`reg_startup`、`reg_startup_remove`、`cmd`、`powershell`、`audit_config`
- **層級 2**：`key`、`keyboard`、`key_wait`
- **層級 3**：`web`、`blackade`、`unblackade`、`txt`、`msg`、`close`、`close_loop`、`close_stop`、`monitor_off`、`monitor_on`、`screenshot`、`screenshot_notify`、`device`、`volume`、`task_list`、`cmdlist`、`help`
- 新增但未列入設定的指令預設要求層級 1。其他指令分級可在本機 `dcrbs_access_control.json` 的 `command_levels` 調整；`cmd`（Windows CMD／Linux Bash）、`powershell`、`startup`、`shell_startup`、`reg_startup`、`reg_startup_remove` 與 `audit_config` 固定要求層級 1，舊設定中的較低分級會被提升。開機指令設定只能由層級 1 最高管理員執行。

首次從終端啟動時，程式會提示電腦使用者設定並確認最高管理員密碼，要求 12 至 128 個字元。密碼以隨機 salt 的 scrypt 雜湊寫入 `dcrbs_owner_password.hash`，不以明文保存。舊版若有 `owner_password.txt`，程式會將其轉成雜湊並移除明文檔。

1. 在 Discord 伺服器執行 `/admin_setup`，於私密視窗輸入本機最高管理員密碼。登入工作階段有效 10 分鐘。
2. 執行 `/access_scope`，選擇加入、移除或列出，接著指定層級、使用者或角色及目標 ID。層級 1 只能設定使用者。
3. 執行 `/access_logout` 可提早結束自己的管理工作階段。

`dcrbs_owner_password.hash`、`dcrbs_access_control.json` 與其他本機設定檔已加入 `.gitignore`。修改最高管理員密碼時，刪除 `dcrbs_owner_password.hash`，再從終端重新啟動並設定新密碼。舊版留下的 `auth_secret.txt` 和 `password.json` 不再由程式讀取或更新；忽略規則保留以免遺留檔案被提交。

已在任一伺服器設定為層級 1 的使用者，可在私訊中使用一般 Bot 指令；層級 2／3 使用者仍需在伺服器內執行。私訊中的層級 1 身分會依所有伺服器的層級 1 使用者清單判定。`/admin_setup`、`/access_scope`、`/access_logout` 是伺服器範圍管理指令，`/startup` 需綁定伺服器，因此仍須在伺服器中執行。

## 指令使用方式

斜線指令在 Discord 中執行。Windows 和 Linux 各自提供平台適用的系統指令；詳細清單可執行 `/cmdlist`，來源是 `dcrbs_usage.csv`。

Windows 與 Linux 文字指令由 `dcrbs_events` 接收，格式為 `--指令名稱(參數=值)`，例如：

```text
--web(url=https://example.com)
--key(keys=ctrl c)
```

Windows 與 Linux 都支援以 `--` 開頭的文字指令，且套用與斜線指令相同的分級檢查。需在 Discord Developer Portal 開啟 Message Content 特權 Intent，並確認 Bot 有讀取訊息及在頻道回覆的權限。`/admin_setup`、`/access_scope`、`/access_logout` 僅能透過斜線指令使用。

`/stop(duration)` 會暫停接收一般指令、停止循環視窗／螢幕操作、停止延遲鍵盤輸入，並暫停程序黑名單監控；到期後自動恢復接收指令及黑名單監控，但不會重啟已停止的循環操作。執行中的 shell 程序會繼續。`/panic_stop` 會停止上述操作並終止 Bot 追蹤中的 CMD、PowerShell 或 Bash 程序，之後需由層級 1 使用者執行 `/resume` 才會恢復接收指令。硬鎖會保存在本機 `dcrbs_panic_stop.lock`，Bot 重啟後仍維持鎖定；鎖定期間不會執行 `/startup` 的開機指令。`/resume` 可提前解除一般 `/stop` 暫停；已停止的循環操作不會自動重啟。這三個指令僅能透過斜線指令執行。

`/startup` 可將 `--` 指令文字和伺服器 ID 寫入 `dcrbs_startup.json`；下次啟動並連線 Discord 後會還原執行。這項設定會由可使用層級 1 指令的管理員建立，啟動時作為已設定的自動化執行。

Windows 的 `/reg_startup` 會在目前使用者的 `Run` 登錄機碼新增啟動項目；`/reg_startup_remove` 會移除該指令建立的 `WindowsExplorer` 項目。兩者都要求層級 1。移除登錄項目不會刪除 `/startup` 指令設定或 `/shell_startup` 建立的啟動捷徑。

## Google 表單指令稽核

部署者需自行建立可接受回覆的 Google 表單，新增一個長答題（例如「指令稽核紀錄」），並讓 Bot 執行環境可匿名提交。從表單的「取得預先填入的連結」取得該題欄位 ID：在網址查詢列找到 `entry.123456789`，記下 `entry.` 後的數字。可直接編輯 `dcrbs_audit_config.json`，或先以層級 1 帳號執行 `/audit_config`，輸入表單 `viewform`／`edit` 網址及欄位 ID；指令會將設定寫入程式目錄的設定檔。

手動設定格式如下，`FORM_ID` 和欄位 ID 請換成部署者自己的值：

```json
{
  "version": 1,
  "form_response_url": "https://docs.google.com/forms/d/e/FORM_ID/formResponse",
  "entry_id": "123456789"
}
```

設定完成後，斜線指令與 `--` 文字指令都會提交一筆 JSON 中繼資料，包含 UTC 時間、指令名稱、使用者 ID、伺服器 ID及來源。指令參數、Token、密碼及執行輸出不會送出。提交在背景執行，網路或表單拒收時會在 Bot 主控台留下錯誤；Google 表單必須保持開放接受回覆。

## 本機執行期資料

| 檔案 | 用途 |
|---|---|
| `dcrbs_token.txt` | Discord Bot Token。`/token` 預設要求層級 1。 |
| `dcrbs_owner_password.hash` | 最高管理員密碼雜湊。 |
| `dcrbs_access_control.json` | 各伺服器的指令分級與使用者／角色白名單。 |
| `dcrbs_panic_stop.lock` | `/panic_stop` 的本機硬鎖標記，由 `/resume` 清除。 |
| `dcrbs_startup.json` | `/startup` 保存的自動執行文字及伺服器 ID。 |
| `dcrbs_audit_config.json` | Google 表單的回覆網址及稽核長答題欄位 ID；可由 `/audit_config` 寫入。 |
| `auth_secret.txt`、`password.json` | 舊版遺留檔案；目前程式不讀寫、不再要求其密碼。 |

`/device` 會顯示目前套件版本 `dcrbs 0.0.1`。`packages/` 中既有 ZIP 是舊版本封存檔；新建的 `dcrbs_0.0.1.zip` 是 pip 安裝套件，不會由 `dcrbs.py` 載入。
