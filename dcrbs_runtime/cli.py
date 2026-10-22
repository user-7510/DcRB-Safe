"""Launch the bot using the current directory for local runtime files."""

import shutil
from importlib.resources import files
from pathlib import Path


RUNTIME_DATA_FILES = ("dcrbs_modules.json", "dcrbs_modules_linux.json", "dcrbs_usage.csv")


def main():
    runtimeDir = Path.cwd()
    packagedData = files("dcrbs_runtime").joinpath("data")
    for fileName in RUNTIME_DATA_FILES:
        targetPath = runtimeDir / fileName
        if not targetPath.exists():
            with packagedData.joinpath(fileName).open("rb") as sourceFile:
                with targetPath.open("wb") as targetFile:
                    shutil.copyfileobj(sourceFile, targetFile)

    from dcrbs import main as runBot

    runBot(runtime_dir=str(runtimeDir))
