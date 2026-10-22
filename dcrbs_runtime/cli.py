"""Launch the bot using the selected directory for local runtime files."""

from pathlib import Path
from dcrbs_runtime.paths import resolveRuntimeDirectory


def main():
    try:
        runtimeDir = Path(resolveRuntimeDirectory())
    except (OSError, ValueError) as errObj:
        print(f"[錯誤] 無法設定 dcrbs 執行資料夾：{errObj}")
        return
    from dcrbs import main as runBot

    runBot(runtime_dir=str(runtimeDir))
