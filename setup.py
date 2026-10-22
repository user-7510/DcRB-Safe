from pathlib import Path

from setuptools import setup


ROOT = Path(__file__).parent
README = (ROOT / "README.md").read_text(encoding="utf-8")

setup(
    name="dcrbs",
    version="0.0.1",
    description="DcRB Discord remote control bot",
    long_description=README,
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    py_modules=[
        "dcrbs",
        "dcrbs_access_control",
        "dcrbs_audit_log",
        "dcrbs_auth",
        "dcrbs_command_dispatch",
        "dcrbs_control",
        "dcrbs_events",
        "dcrbs_linux",
        "dcrbs_system",
        "dcrbs_version",
    ],
    packages=["dcrbs_runtime"],
    package_data={"dcrbs_runtime": ["data/*.json", "data/*.csv"]},
    install_requires=[
        "discord.py",
        "aiohttp",
        "psutil",
        "pyautogui",
        "mss",
        "Pillow",
        "pygetwindow; platform_system == 'Windows'",
        "pycaw; platform_system == 'Windows'",
        "keyboard; platform_system == 'Windows'",
    ],
    entry_points={"console_scripts": ["dcrbs=dcrbs_runtime.cli:main"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
