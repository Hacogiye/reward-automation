# AGENTS.md

Microsoft Rewards bot for Windows: Playwright drives Microsoft Edge (one persistent profile per account) and a
pywebview UI (`rewards_bot/ui/web`). The user speaks Vietnamese. UI strings, log messages and code comments are
written in Vietnamese, and new ones should be too. Identifiers stay in English.

Runs on Windows (main target) and Linux. Keep OS-specific code behind `sys.platform` checks:
`edge_launcher` finds the browser per OS (`microsoft-edge-stable`/`google-chrome`/`chromium` on Linux) and builds
the UA platform token per OS; `browser.py` lists processes with PowerShell on Windows and `ps` elsewhere; the UI uses
WebView2 on Windows and lets pywebview pick GTK/Qt elsewhere. Tests fake `sys.platform` to cover the Linux paths.

## Commands

```bash
python -m pytest -q tests                  # or check.bat; run before every commit
python -m rewards_bot                      # UI (single instance: data/app.lock)
python -m rewards_bot --check              # self-check every account, no searches
python -m rewards_bot --run-all --headless # what Task Scheduler runs
```

## Layout

- `core/bot.py`: `RewardsBot`, one account per thread. Entry points `run()`, `diagnose()` and `refresh()` all go
  through `_session()`, which opens the browser and handles errors.
- `core/rewards_page.py`: parses rewards.bing.com (points, cards, Points breakdown). It is tested against
  `tests/fixtures`.
- `core/runner.py`: runs accounts in parallel (`max_parallel`) and writes `data/logs/<date>.log` (kept 14 days).
- `core/config.py`: settings defaults plus atomic JSON writes (`.bak` kept). `ui/webapp.py` has `SETTING_SCHEMA`:
  every new setting needs a default in `DEFAULT_SETTINGS`, an entry in the schema and a field in
  `ui/web/app.js` (`SETTING_FIELDS`).
- `ui/web`: the UI uses Tabler 1.0 (Bootstrap 5), Tabler Icons and ApexCharts, all vendored in `ui/web/vendor/`.
  The CSP allows only `'self'`, so never load anything from a CDN. Theme = `data-bs-theme` on `<html>`, driven by
  the `theme` setting ("system"/"light"/"dark"). Style with `--tblr-*` variables so both themes work.
  `tests/test_ui_smoke.py` renders every page in headless Edge with a mocked API.
  Task icons are Fluent Emoji 3D PNGs (MIT, `vendor/fluent-emoji/`, 96px), picked in `app.js` by `ICON_RULES`
  (title first, then Bing image name, then group). The Cyberpunk skin (`cyberpunk.css`, `data-skin="cyberpunk"`) uses
  Chakra Petch (OFL, `vendor/fonts/`) and the app's own `assets/skyline.svg`.
- `search/catalog.py`: the query catalog. `search/bank.py` hands out queries without repeats across accounts or
  across `history_days`.
- `data/` holds login sessions and cookies. It is never committed. Profile dir = `data/profiles/<profile["dir"]>`,
  which is fixed at creation and is not the display name (for example account `alice` may use `alice_2`).
  One such folder can hold several Edge profiles (for example `Default` = a work account and `Profile 1` = the
  personal MSA). `edge_launcher.pinned_profile()` pins one into `rewards_bot_profile.txt` on first open and the bot
  always passes `--profile-directory`. Never drop that, or Edge silently opens whichever profile was used last.
- `core/credentials.py`: optional auto re-login. Email + DPAPI-encrypted password in `data/credentials.json`, Windows
  only, never sent to the UI or written to logs. `RewardsBot.auto_login()` runs from `_session()` on `NotLoggedIn` and
  stops (does not try to pass) at any verification step: code, Authenticator, CAPTCHA.

## Hard-won facts (verified 2026-10)

- **Mobile searches counted as PC.** Bing sets the session cookie `_Rwho=u=d` (desktop) on the first desktop search
  or bing.com visit. Every later search in that browser session is then counted as PC, including the emulated
  mobile tab, so Mobile earns +0 once PC is full. `RewardsBot.new_bing_session()` clears `_Rwho`, `_SS` and
  `_EDGE_S` before and after the mobile tab. Clearing only `_SS`/`_EDGE_S` is not enough. Do not remove this.
- Mobile emulation (`_emulate_mobile`) builds UA and client hints from the real running Edge version. Both the old
  hard-coded UA and the new one earn points, so the UA was not the cause of the mobile bug.
- Points for a search usually show up in Points breakdown immediately (3 per search). A "rate limit / delayed credit"
  theory was tested and was wrong. Do not reintroduce slow-mode style workarounds without an A/B test.
- Edge adds desktop-only headers (`sec-ms-gec`, `x-client-data`, `x-edge-*`) at the network layer. Playwright
  `route` cannot remove them. Chrome cannot read Edge's cookies (app-bound encryption), so a copied profile is
  logged out.
- **Browser launch.** Managed profiles are opened by `core/edge_launcher.py`. It starts the real msedge.exe with a
  few flags plus `--remote-debugging-port=0` on 127.0.0.1, then Playwright attaches with `connect_over_cdp`. This
  is how Selenium/AutoRewarder runs. Do NOT go back to `launch_persistent_context`: Playwright's ~40 automation
  flags (`navigator.webdriver=true`) make Bing reject Visual Search ("Unable to process this search", kblob
  upload 400). With the plain launch, Visual Search works (verified 2026-10-21: kblob 200, results FORM=SBIIRP).
- **Visual Search** (`do_visual_search`): download a random Bing Images thumbnail, open the mission URL
  `bing.com/?features=vsstreak`, go to `bing.com/images`, click the camera `#sb_sbi`, wait for `#sb_sbipane`, then
  **dispatch a synthetic drag-and-drop** (DataTransfer with the image) on the pane. Bing can take more than 5 s to
  react, so wait up to 20 s for a result URL (`form=sbi`/`iss=sbi`/`bcid=`/`view=detailv2`). `set_input_files` on
  `#sb_fileinput` gets kblob 400 ("Unable to process this search"); it is only a fallback.
- **Headless tell.** `--headless=new` puts `HeadlessChrome` in the UA, and Bing then rejects Visual Search.
  `edge_launcher` passes `--user-agent` with the normal UA (version read from the folder next to msedge.exe) and
  `--screen-info` 1920x1080. Verified: headless Visual Search works after this.
- 2026-10-21 the Edge Browsing Streak did count for one test account (streak day 2), but on 2026-10-22 about 5 h of headless
  Browse in the same `Profile 1` left Edge – Minutes at 0/30. The cause is unknown. `do_browse` now reads Edge – Minutes
  every 10 min, logs `first → now (chạy ẩn/hiện cửa sổ)`, and stops when full or after 20 min without gain. Read those
  log lines before claiming anything about what earns it.
- Older note: "Edge – Minutes" (Edge Browsing Streak, 30 min/day) was NOT earned by the bot's Browse in early tests. The following were all
  tested on one account and all gave 0/30: headless, headed, Playwright's background-blocking flags removed, and the Edge
  browser itself signed in to the right MSA (checked in edge://signin-internals). The minutes that did count came
  from the user's own Edge use: the bot profile's History shows no long browse on those days. Do not claim Browse
  earns it.
- Other bots (TheNetsky/Microsoft-Rewards-Script, GPL-3.0) "earn" Edge minutes by POSTing fake usage reports to
  `prod.rewardsplatform.microsoft.com/dapi/me/activities`, as EdgeDesktop, with an OAuth token minted under the
  Bing app's client id. Codex's safety classifier blocked this as a third-party attack, and it is not done
  here. Do not reimplement it. Visual Search credit shows up as the results page calling
  `/rewardsapp/reportactivity?...bcid=`; the bot watches for that request.
- Bing seems to throttle Visual Search after many attempts in one day on the same account ("Unable to process this
  search" even with the working flow). Test on an account that has not done it yet that day, and only once or twice.
- Stamp bonus: on /dashboard the element `[role=progressbar][aria-label="Stamps collected"]` carries
  `aria-valuenow` / `aria-valuemax`. Streaks are in the /earn "Streaks" section ("Day x of 7").
- Windows can auto-sign the Edge *browser* into a work account in every bot profile, even
  when bing.com cookies belong to another account. This did not affect search points.

## Debugging against real accounts

- Write throwaway scripts in the scratchpad, not the repo. Import `RewardsBot`, load settings with
  `load_settings()`, and call `bot._session(work, headless=True, label=...)` or `bot.diagnose()`.
- A profile can be opened by only one browser at a time. Check that the app is not running that account (look for
  `msedge.exe` with `--user-data-dir=...\<dir>`) before you launch it.
- Prove a fix with an A/B run on the same account: read Points breakdown, do 3 searches, read it again. Do not draw
  conclusions from log timing alone, because the account owner may also search manually on a phone.

## Conventions

- The user commits straight to `main` and asks before each push. End commit messages with the Co-Authored-By line.
- Tests use fakes (`FakePage`, `FakeBank`, `bot.sleep` patched out). Keep bot logic testable without a browser.
