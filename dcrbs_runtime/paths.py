"""Persist the chosen working directory for the dcrbs runtime files."""

import json
import os
import shutil
from importlib.resources import files
from pathlib import Path


RUNTIME_DATA_FILES = (
    "dcrbs_modules.json",
    "dcrbs_modules_linux.json",
    "dcrbs_usage.csv",
)


def _runtimeDirectoryConfigPath():
    if os.name == "nt":
        configRoot = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        configRoot = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return configRoot / "dcrbs" / "dcrbs_runtime.json"


def resolveRuntimeDirectory(requestedDirectory=None):
    """Use the first selected runtime directory for all later launches."""
    requestedPath = Path(requestedDirectory or Path.cwd()).expanduser().resolve()
    if not requestedPath.is_dir():
        raise NotADirectoryError(f"執行資料夾不存在：{requestedPath}")

    configPath = _runtimeDirectoryConfigPath()
    if configPath.exists():
        try:
            with configPath.open("r", encoding="utf-8") as configFile:
                configData = json.load(configFile)
            savedPath = Path(configData["runtime_directory"]).expanduser().resolve()
        except (OSError, KeyError, TypeError, ValueError) as errObj:
            print(f"[警告] 無法讀取執行資料夾設定 {configPath}：{errObj}")
        else:
            if not savedPath.is_dir():
                raise FileNotFoundError(
                    f"已保存的 dcrbs 執行資料夾不存在：{savedPath}。"
                    f"請修正或移除 {configPath} 後重新啟動。"
                )
            return str(savedPath)

    try:
        configPath.parent.mkdir(parents=True, exist_ok=True)
        tempPath = configPath.with_suffix(".tmp")
        with tempPath.open("w", encoding="utf-8") as configFile:
            json.dump(
                {"version": 1, "runtime_directory": str(requestedPath)},
                configFile,
                ensure_ascii=False,
                indent=2,
            )
            configFile.write("\n")
            configFile.flush()
            os.fsync(configFile.fileno())
        os.replace(tempPath, configPath)
        print(f"[資訊] 已保存 dcrbs 執行資料夾：{requestedPath}")
    except OSError as errObj:
        raise OSError(f"無法保存執行資料夾設定 {configPath}：{errObj}") from errObj
    return str(requestedPath)


def ensureRuntimeFiles(runtimeDirectory):
    """Copy missing default settings into the selected runtime directory."""
    runtimePath = Path(runtimeDirectory)
    packagedData = files("dcrbs_runtime").joinpath("data")
    for fileName in RUNTIME_DATA_FILES:
        targetPath = runtimePath / fileName
        if targetPath.exists():
            continue
        with packagedData.joinpath(fileName).open("rb") as sourceFile:
            with targetPath.open("wb") as targetFile:
                shutil.copyfileobj(sourceFile, targetFile)
