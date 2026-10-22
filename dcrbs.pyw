import multiprocessing
import os
import sys
import tempfile
import traceback
from pathlib import Path


def getBootstrapLogPath():
    if os.name == "nt":
        configRoot = Path(
            os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
        )
        return configRoot / "dcrbs" / "dcrbs_startup.log"
    return Path.home() / ".config" / "dcrbs" / "dcrbs_startup.log"


def launchBot():
    previousStdout, previousStderr = sys.stdout, sys.stderr
    logFiles = []
    activeLog = None
    try:
        try:
            bootstrapLogPath = getBootstrapLogPath()
            bootstrapLogPath.parent.mkdir(parents=True, exist_ok=True)
            activeLog = bootstrapLogPath.open("a", encoding="utf-8", buffering=1)
        except OSError:
            try:
                activeLog = (Path(tempfile.gettempdir()) / "dcrbs_startup.log").open(
                    "a", encoding="utf-8", buffering=1
                )
            except OSError:
                activeLog = open(os.devnull, "w", encoding="utf-8")
        logFiles.append(activeLog)
        sys.stdout = activeLog
        sys.stderr = activeLog

        from dcrbs_runtime.paths import resolveRuntimeDirectory

        runtimeDir = Path(resolveRuntimeDirectory())
        os.chdir(runtimeDir)
        runtimeLog = (runtimeDir / "dcrbs_startup.log").open(
            "a", encoding="utf-8", buffering=1
        )
        if Path(runtimeLog.name).resolve() != Path(activeLog.name).resolve():
            logFiles.append(runtimeLog)
            sys.stdout = runtimeLog
            sys.stderr = runtimeLog
        else:
            runtimeLog.close()

        print("\n[dcrbs] Windows pyw 啟動器開始執行。")
        print(f"[dcrbs] 執行資料夾：{runtimeDir}")
        from dcrbs import main

        main(runtime_dir=str(runtimeDir))
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout, sys.stderr = previousStdout, previousStderr
        for logFile in logFiles:
            try:
                logFile.close()
            except OSError:
                pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    launchBot()
