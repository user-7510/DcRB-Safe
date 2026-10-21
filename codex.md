# Codex Handoff Notes

Updated: 2026-10-21

## Project summary

DcRB is a Discord bot that exposes local computer control through slash commands and, on Windows, message commands beginning with `--`. Current project version is declared as `6.0.0` in `main.py`.

## Recent work and accepted decisions

- Unified startup and message `--command(...)` parsing in `command_dispatch.py`; duplicate command names now raise a collision error instead of silently replacing one another.
- Kept `main.pyw` as a small wrapper around `main.main()`.
- Consolidated Linux desktop and TTY module configuration into `modules_linux.json`.
- Added guild-scoped access control. The local highest-administrator password is prompted for on first `main` startup, stored as a salted scrypt hash in `owner_password.hash`, and entered into Discord through the private `/admin_setup` modal.
- The Discord owner session lasts 10 minutes. `/access_scope` adds, removes, and lists per-guild user and role assignments; `/access_logout` ends the caller's session.
- Current user decision: remove every command-specific/secondary password check. All functional commands are authorized through the administrator-assigned access levels. Only the local owner password remains for `/admin_setup`.
- Current user-selected default tiers: level 1 for high-impact/system startup operations; level 2 for shell/keyboard command execution; level 3 for regular read/control operations. `reg_startup` is level 1. Unclassified commands default to level 1.
- Updated application-command error handling in `main.py` for Discord error 10062 (`Unknown interaction`): expired interactions are logged as warnings without attempting a second, doomed response. For other command errors, the handler uses a followup when the interaction was already acknowledged and catches HTTP failures while reporting.
- `1.log` showed `/admin_setup`'s modal response arriving after Discord had expired the interaction, followed by a second 10062 from the global error handler. An expired interaction cannot be used to open the modal or send a reply; retry `/admin_setup` after the bot reconnects.

## Startup and module graph

`main.py` initializes the owner hash, reads `BOT_TOKEN.txt`, then launches `BotRunner`. `setup_hook()` selects `modules_linux.json` on Linux and `modules.json` otherwise, imports each listed module and calls its `setup(bot)`. It then adds `authModule.generalCheck` and `accessControl` checks before syncing slash commands. Startup stops if `accessControl` did not load.

Windows configuration loads `authModule`, `controlModule`, `systemModule`, `eventModule`, and `accessControl`. Linux configuration loads `authModule`, `linuxModule`, and `accessControl`. The non-Linux branch currently uses Windows modules, so macOS is not separately supported.

`eventModule` passes `--` messages to `command_dispatch.dispatchTextCommands`; `main.py` uses the same dispatcher for saved startup text. Dispatcher discovers callbacks from loaded Cogs, converts simple typed arguments, and applies command checks for normal text messages. Saved startup text runs with `runChecks=False` after it was configured through `/startup`.

## Permission model

- Level 1: explicitly assigned user IDs only.
- Level 2: user IDs or role IDs.
- Level 3: user IDs or role IDs.
- The lowest numeric level grants the greatest access. A user assigned more than one level receives the strongest one.
- Permission configuration is per guild in `access_control.json`; command levels are configurable in its `command_levels` map.
- `/admin_setup`, `/access_scope`, and `/access_logout` are management commands and are excluded from ordinary command checks. Scope changes require the caller's valid owner session.
- Do not reintroduce password parameters or per-command password checks. The owner hash is the only password credential used by current code.

Default command levels in `accessControl.py`:

- **1**: `stop`, `reject`, `token`, `shutdown`, `startup`, `shell_startup`, `reg_startup`
- **2**: `powershell`, `cmd`, `key`, `keyboard`, `key_wait`
- **3**: `web`, `blackade`, `unblackade`, `txt`, `msg`, `close`, `close_loop`, `close_stop`, `monitor_off`, `monitor_on`, `screenshot`, `screenshot_notify`, `device`, `volume`, `task_list`, `cmdlist`, `help`

## Command behavior by module

- `authModule.py`: `/stop(duration)`, `/reject`, `/token(token)`, `/help`. `/stop` pauses ordinary commands; management commands remain available. `/reject` exits the process.
- `controlModule.py` (Windows): text-file display, message box, web launch, keyboard input, window closing, monitor control, screenshots, and process blacklist handling.
- `systemModule.py` (Windows): device information, CMD and PowerShell, volume, shutdown, startup config, Startup-folder shortcut, registry startup, process/window list and command list.
- `linuxModule.py`: Linux device information, Bash command, shutdown, and process list.
- `eventModule.py`: Windows text-command entry point.

## Local files and dependencies

- Required input: `BOT_TOKEN.txt`.
- Owner credential: `owner_password.hash`. First setup requires an interactive terminal and a 12–128 character password. A legacy `owner_password.txt` is migrated to the hash and removed at startup.
- Runtime state: `access_control.json` (permissions) and `config.json` (saved startup command and guild ID).
- `auth_secret.txt` and `password.json` are legacy files. Current Python code no longer reads, creates, or writes them. Their `.gitignore` entries are intentionally retained to protect leftover local copies.
- Dependencies are listed in `requirements.txt`: `discord.py`, `aiohttp`, `psutil`, `pyautogui`, `mss`, `pygetwindow`, `pycaw`, `keyboard`, `Pillow`.
- `dcrb_usage.csv` is the live `/cmdlist` content. Keep it aligned with command signatures; do not advertise removed commands such as `--kill` or obsolete password arguments.
- ZIP files under `packages/` are historical archives and are not imported by the active entry point.

## Current task status

Completed for the latest user request:

1. Removed secondary password checks, password parameters, old password generators/storage helpers, and `/change_password`.
2. Updated `dcrb_usage.csv` for the changed `/stop`, `/reject`, and `/token` signatures and removed its stale `--kill` entry.
3. Rewrote `README.md` with setup, module dependencies, platform behavior, permission levels, commands, and runtime files.
4. Created this handoff file.
5. Made the global application-command error handler tolerate expired Discord interactions and avoid the secondary unhandled task exception shown in `1.log`.

No tests have been run. After edits, inspect references for old password logic and run `git diff --check`; do not launch the bot during static handoff review because it may prompt for a local owner password or connect to Discord.
