<div align="center">

<img src="rewards_bot/ui/web/assets/app-icon-256.png" width="96" alt="PrixAuto logo">

# PrixAuto

**Your daily Microsoft Rewards tasks, done for several accounts, from one desktop app.**

[![Release](https://img.shields.io/github/v/release/NT101-lc/reward-automation?label=download&color=2563eb)](https://github.com/NT101-lc/reward-automation/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-2563eb)](LICENSE)
![Windows 10/11](https://img.shields.io/badge/Windows-10%20%7C%2011-475569)
![Linux](https://img.shields.io/badge/Linux-headless%20%2B%20UI-475569)

[Tiếng Việt](README.md) · English

<img src="docs/images/dashboard.png" alt="PrixAuto overview page" width="900">

</div>

> [!WARNING]
> **Read this first.** The Microsoft Rewards terms do not allow bots or automated tools to earn points. Microsoft can
> suspend the Rewards account and cancel unredeemed points or orders. This project is not affiliated with or endorsed by
> Microsoft. You use it entirely at your own risk; do not use it with an account you cannot afford to lose.

## Features

- **Daily tasks**: Daily Set, Keep earning (links, polls, simple quizzes), multi-step Quests.
- **Searches**: PC and Mobile searches until the points are full, with queries from 22 topics (~2,600 real-looking
  sentences plus ~10,000 popular keywords), never repeated across accounts or within N days.
- **Visual Search** and **Browse** (Edge – Minutes) as optional extras.
- **Several accounts in parallel**, each in its own Edge profile and window, with a limit on how many run at once.
- **Dashboard**: points, today's progress, streaks and stamp bonus, daily charts, a reward goal with an ETA, and a
  per-day history of what was earned and what is still missing.
- **Self-check** (no searches): verifies sign-in, the bing.com account, the Points breakdown and the proxy, and tells
  you how to fix each problem.
- **Optional auto sign-in**: the password is encrypted with Windows DPAPI and never shown or logged. The bot stops at
  any verification step (code, Authenticator, CAPTCHA) instead of trying to pass it.
- **Runs without a window** (`--run-all --headless`), so you can schedule it with Windows Task Scheduler or cron.
- Light and dark theme, English and Vietnamese UI, keyboard accessible.

Not supported: the **daily check-in** (it lives in the Microsoft Rewards phone app).

<table>
  <tr>
    <td><img src="docs/images/accounts.png" alt="Accounts page"></td>
    <td><img src="docs/images/history.png" alt="History page"></td>
  </tr>
  <tr>
    <td><img src="docs/images/dashboard-dark.png" alt="Overview in dark theme"></td>
    <td><img src="docs/images/settings.png" alt="Settings page"></td>
  </tr>
</table>

## Install on Windows (no Python needed)

The download is a ready-to-run app: **no Python or anything else to install**. You need Windows 10/11 (64-bit),
Microsoft Edge (built in) and a Microsoft account that has joined [Microsoft Rewards](https://rewards.bing.com).

1. **Download.** On the [latest release](https://github.com/NT101-lc/reward-automation/releases/latest) page, under
   **Assets**, click the file ending in **`-win64.zip`**. Not *Source code (zip)*: that needs Python.
2. **Unzip.** Right-click the zip → **Extract All...**, type `C:\PrixAuto`, click **Extract**. Do not run the app from
   inside the zip (it cannot save your accounts). Avoid `C:\Program Files` (not writable) and OneDrive-synced folders
   such as Desktop or Documents (your sign-in cookies would be uploaded).
3. **Open** `C:\PrixAuto\PrixAuto.exe`. Windows may show *"Windows protected your PC"* because the exe is not
   code-signed: click **More info → Run anyway**. If your antivirus removes the file, add `C:\PrixAuto` as an exception
   and unzip again. The welcome screen asks for your language, the risk acknowledgement and your first account.
4. **Sign in, once per account.** On the **Accounts** page, click **⋮ → Log in**. An Edge window opens with two tabs:
   sign in on the Rewards tab, check that the **bing.com** tab shows the **same account** (top right), then close the
   window.
5. **Check and run.** Click **⋮ → Check**; any **FAIL** line in the **Log** page says how to fix it. Then click **Run**
   (one account) or **Run all**. A run usually takes 20–40 minutes per account because searches are paced like a person.

All data (accounts, sign-in sessions, settings, history) stays in the `data\` folder next to `PrixAuto.exe`.

## Run it every day

The app has no schedule button yet; use Windows' own **Task Scheduler**:

1. Press **Start**, type `Task Scheduler`, open it, then click **Create Basic Task...** and name it `PrixAuto`.
2. Choose **Daily** and a time when the PC is usually on.
3. Choose **Start a program**. **Program/script**: `C:\PrixAuto\PrixAuto.exe`. **Add arguments**:
   `--run-all --headless`. **Start in**: `C:\PrixAuto`.
4. Tick **Open the Properties dialog...**, click **Finish**, and on the **Settings** tab tick **Run task as soon as
   possible after a scheduled start is missed**.

The task only runs while the PrixAuto window is closed and you are signed in to Windows. Right-click the task → **Run**
to test it. Results appear on the **History** and **Log** pages.

## Run from source

Only needed if you want to change the code. Install **Python 3.10+** from
[python.org](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** in the installer. Then:

```bash
git clone https://github.com/NT101-lc/reward-automation.git
```
```bash
cd reward-automation
```
```bash
pip install -r requirements.txt
```
```bash
python -m rewards_bot
```

| Command | What it does |
|---|---|
| `python -m rewards_bot` | Opens the app (only one window at a time) |
| `python -m rewards_bot --run-all --headless` | Runs every account without a window |
| `python -m rewards_bot --check` | Self-checks every account, no searches |

On Windows you can also double-click `scripts/run.bat`.

<details>
<summary><b>Linux</b></summary>

The bot and the headless mode work on Linux. You need:

1. Python 3.10+ and `pip install -r requirements.txt`.
2. A Chromium-based browser: **Microsoft Edge** (`microsoft-edge-stable`, recommended), Google Chrome or Chromium.
   Pick Chrome/Chromium in Settings if you use one of those.
3. For the UI only, a web view for pywebview: GTK (`sudo apt install python3-gi gir1.2-webkit2-4.1`) or Qt
   (`pip install "pywebview[qt]"`).

```bash
./scripts/run.sh
```
```bash
./scripts/run.sh --run-all --headless
```

Daily with cron: `30 7 * * * cd /path/to/reward-automation && ./scripts/run.sh --run-all --headless`.
On Linux `data/` is not locked down automatically (`chmod 700 data` if needed) and the system proxy is not read.
</details>

## Updating

The app does not update itself. Download the new zip and unzip it over the old folder: the zip has no `data\` folder,
so your accounts and sessions are kept. From source: `git pull`.

Upgrading from the old **RewardsBot** name: copy the `data\` folder from next to `RewardsBot.exe` to next to
`PrixAuto.exe`, and point your scheduled task at `PrixAuto.exe`.

## FAQ

<details>
<summary><b>The app window is blank or closes right away</b></summary>

The app needs the **Microsoft Edge WebView2 Runtime**. Windows 11 has it; some older Windows 10 PCs do not. Install the
*Evergreen Bootstrapper* from [Microsoft's WebView2 page](https://developer.microsoft.com/microsoft-edge/webview2/) and
open the app again. If it still fails, see `data\crash.log`.
</details>

<details>
<summary><b>Mobile searches give 0 points</b></summary>

Run **Check**. Make sure the bing.com tab is signed in to the same account as Rewards. The bot clears Bing's session
cookies before the mobile tab, because otherwise Bing counts every search in that session as PC.
</details>

<details>
<summary><b>"Edge – Minutes" stays at 0/30</b></summary>

Edge measures browsing time itself and reports it to Rewards. Browse often needs to run 3–4 times in a day before it
fills up; turn off "auto stop" for Browse in that case. The log records the minutes before and after every 10 minutes.
</details>

<details>
<summary><b>Visual Search says "Unable to process this search"</b></summary>

Bing throttles Visual Search after many attempts on one account in a day. The bot tries at most 4 times per day
(configurable in Settings).
</details>

<details>
<summary><b>The bot says the profile is in use</b></summary>

An Edge window is still open on that account's profile. Close it (or stop the run) and try again. One profile can be
opened by one browser at a time.
</details>

<details>
<summary><b>Where are the logs?</b></summary>

In `data\logs\<date>.log` (kept 14 days by default). The **Log** page has an *Open folder* button. If the exe fails
to start, see `data\crash.log`. Please attach the log when you open an issue.
</details>

## Privacy and security

- Everything stays on your computer. The app has no telemetry and no update check. The bot's browser opens Bing and
  Rewards, plus the pages that Browse and the occasional search-result click visit.
- `data\` holds your Microsoft sign-in cookies. On Windows it is locked to your user account and SYSTEM on first run.
  Never share it.
- The browser runs with `--no-proxy-server` by default, so a system proxy cannot sit in the middle (turn this off in
  Settings if your network requires a proxy). Per-account proxies are supported (`http`, `https`, `socks4`, `socks5`,
  without credentials).
- Managed windows open Edge with a debug port bound to `127.0.0.1` only, which closes with the browser. Other programs
  on the same computer can control that window while it runs, so do not run the bot on a shared PC.
- The UI has a strict Content-Security-Policy: only the app's own scripts run, and all vendored libraries ship with
  the app (no CDN).

## Development

```bash
pip install -r requirements-dev.txt
```
```bash
python -m pytest -q tests
```

The UI smoke tests render every page in headless Edge with a mocked API.

Releases: bump `__version__` in `rewards_bot/__init__.py`, then push a tag `v<version>`. GitHub Actions runs the tests,
builds `PrixAuto.exe` and publishes the zip with its `.sha256`. Build locally with `python packaging/build_exe.py`.

<details>
<summary><b>Project layout</b></summary>

```
rewards_bot/
├── __main__.py           entry point: UI, --run-all, --check
├── cli.py                --run-all / --check without a window
├── core/
│   ├── bot.py            one account: tasks, searches, self-check
│   ├── rewards_page.py   parses rewards.bing.com (points, cards, Points breakdown)
│   ├── runner.py         runs accounts in parallel, daily log files
│   ├── edge_launcher.py  starts a normal Edge with a local debug port for Playwright
│   ├── browser.py        finds a leftover Edge still holding a profile folder
│   ├── instance.py       single-instance lock (data/app.lock)
│   ├── credentials.py    optional auto sign-in, DPAPI-encrypted
│   ├── security.py       data folder permissions, proxy and debug-port checks
│   └── config.py         settings and atomic JSON writes
├── search/               query catalog and no-repeat query bank
└── ui/                   pywebview app + web UI (Tabler, ApexCharts, vendored)
packaging/                PyInstaller build (PrixAuto.exe)
scripts/                  run.bat / run.sh (open the app), check.bat / check.sh (tests)
tests/                    pytest: bot logic, page parsing, API and UI smoke tests
docs/images/              README screenshots
```
</details>

## Credits and license

PrixAuto is released under the [MIT License](LICENSE). Bundled libraries keep their own licenses (see each folder in
`rewards_bot/ui/web/vendor/`): Tabler and Tabler Icons (MIT), ApexCharts (MIT), Fluent Emoji (MIT), Chakra Petch
(SIL OFL 1.1). The plain-Edge launch idea comes from [AutoRewarder](https://github.com/safarsin/AutoRewarder) (MIT).

"Microsoft", "Bing", "Edge" and "Microsoft Rewards" are trademarks of Microsoft Corporation. This project is not
affiliated with Microsoft.
