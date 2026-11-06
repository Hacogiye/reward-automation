# CLAUDE.md

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
- Packaging: `packaging/build_exe.py` builds a PyInstaller onedir `dist/RewardsBot/` plus
  `RewardsBot-<ver>-win64.zip`. When frozen (`config.FROZEN`), `BASE_DIR` is the folder of `RewardsBot.exe`, so `data/`
  sits next to it. `packaging/launcher.py` writes uncaught errors to `data/crash.log`. The windowed exe has no usable
  stdout, and printing Vietnamese crashed it until `__main__._safe_console()` was added. Keep that.
- `core/updater.py`: checks GitHub Releases (`REPO`, private, so it needs a read-only token stored with
  `credentials.save_secret`), downloads the zip (the token is not sent to the redirect host), and `verify_zip` rejects
  traversal or any `RewardsBot/data/` entry. A detached PowerShell script then waits for the app to exit, robocopies
  over the install excluding `data/`, and restarts it. Version = `rewards_bot.__version__`. Pushing tag `v<ver>` runs
  `.github/workflows/release.yml`, and the tag must match `__version__`.
- Quests (2026-10-23): `rewards_page` parses `/earn/quest/...` cards into `state["quests"]`. A quest page lists steps under
  `H2: Activities` as `H3` rows; a step that can be done in a browser is a link there (`SCRAPE_JS` section "Activities").
  Steps locked behind the Microsoft Rewards desktop app have no link ("Install the Desktop Rewards App"), so
  `do_quest_tasks` skips them. No unfinished browser-doable quest was available on 2026-10-23 to verify a real click.
- UI language (`language` setting, "vi"/"en"): the UI is written in Vietnamese. `ui/web/i18n.js` (`I18N.apply`) walks
  text nodes and title/placeholder/aria-label, and a MutationObserver translates anything rendered later. Dictionary
  keys are the Vietnamese text with whitespace collapsed and every number replaced by `#`; strings that embed user data
  go in `PATTERNS`; text joined with " · " is translated part by part. Long prose (the Guide page, a few form hints)
  has a hand-written English copy in `data-lang="en"` blocks instead. Bot log lines (`#logbox .msg`) are never
  translated. When you add UI text, add its English entry to `I18N`.
- Accounts page: `do_quest_tasks` (Quests, separate from `do_quests` = Daily Set + Keep earning), `browse_auto_stop`
  shown as a sub-switch of Browse, and the "Làm tất cả" button = `Api.start(names, "everything")`, which runs with
  every `do_*` forced on (`webapp.EVERYTHING`) without saving. Avatars: `Api.set_avatar` stores PNG/JPEG/WebP (magic
  bytes checked, at most 300 KB) as `data/avatars/<profile dir>.<ext>`, so renames keep the photo.
- Office page (`ui/web/office.js` + `office.css`): one pixel robot per account, drawn on a canvas, with no image files.
  `activity()` maps `S.pstate` state/progress strings (for example `Search PC`, `Search Mobile`, `Visual Search`,
  `Browse`) to a desk/lounge pose and screen, so if you change progress text in `bot.py`, update those regexes. Name
  tags and speech bubbles are an HTML layer on top (bubbles are `data-no-i18n`; canvas text goes through `I18N.tr`).
  The lofi music is generated with Web Audio (`Lofi`), so there are no audio files and the CSP is unchanged. It only
  starts after a click (autoplay policy). Volume and rain are kept in `localStorage` (`pref`).
  Clicking a robot (or its name tag) opens one info card (`.ob-card`, `openCard`/`renderCard`/`placeCard`) above its
  head instead of leaving the page: linked account (saved email from `S.credentials`, plus proxy/CDP), points, today,
  state, current progress, today's tasks split into to-do / done, and Run/Stop + Overview buttons. It follows the robot,
  shrinks to the free space above (or flips below) and is re-rendered only when its HTML changes. Esc, clicking empty
  floor or clicking outside closes it. Test hook `Office._card()`.
  Isometric 2:1 view (tile 32 x 16 px): logic runs in floor coordinates `b.gx`/`b.gy` (tile units), `iso(gx, gy, z)`
  projects to the canvas and the depth is `gx + gy` (bigger = nearer the viewer, drawn later). Desks run along `gx`
  (`COLS=4`), rows along `gy`, then a corridor, then the lounge strip nearest the viewer. Robots walk along floor axes
  only (desk gap -> corridor -> `GAP_L` -> front row), never through furniture; `locate(b)` computes `b.sx/sy/depth`
  once per frame and drawing, bubbles, hit-test and FX use that (FX stay in screen space). The world size comes from
  `geom()` and depends on the number of desk rows (`W = (GX+GY)*16+12`). Window frames (left wall), the sign, clock
  and score board (right wall) use wall-local coordinates with a 2:1 shear (`withWall`); the HTML wall text (`.ow-right`)
  uses `skewY(26.565deg)` to match. Static layer (`drawStatic`, redrawn only when `staticKey()` changes): floor, walls,
  rug and wall items, i.e. only things nothing can stand behind. Desks, chairs, sofa, coffee machine, water cooler,
  plant and arcade are pre-rendered sprites (`sprites[name]`, rebuilt when `themeKey()` changes) in the depth-sorted
  list with the robots; only monitor screens, windows and LEDs are drawn per frame. The monitor is a thin box at the
  back of the desk whose glass faces `+gy`; `drawScreen` content (26 x 15) is drawn onto it with `transform(1, 0.5, 0,
  1, ...)`. The chair stands in front of the desk (`SEAT_DX/SEAT_DY`, the viewer's side), so a seated robot shows its
  back and looks at the screen up-right (1-2 o'clock). The chair is two sprites: seat (drawn before the robot) and a
  low back (`chairBack`, after it). Robots are drawn as isometric boxes (`boxO`, body + head + arms/legs); `b.fa`
  (`+gy`/`+gx`/`-gy`/`-gx`) is the facing, set from the walk direction or `restFace()`, and the visor/face is drawn
  on a visible side with `onFace()`; facing away shows only the visor edge. A waiting robot stands behind its own
  chair. Test hooks (read-only): `Office._pos(name)`, `_path(name)`, `_screens()`.
  There is always exactly one free desk slot (index `S.profiles.length`, so `rows = ceil((n+1)/4)`): a dashed outline
  in the static layer plus one HTML `.ob-add` "+" button that calls `openProfileDialog(null)`. The gear button
  `#office-settings` opens `#settings-dialog`, which borrows the settings page's `#settings-cards` block (moved in on
  open, moved back to `#settings-home` on close) so the form, ids and handlers exist only once; `.settings-help` is
  hidden inside the dialog.
  Lounge tasks: on arrival `pickSpot` picks `b.task` from `TASKS` (sofa: rest/diary, coffee, drink at the water cooler,
  water the plant, arcade game, rug: dance/stretch); `loungeTask(b)` returns it only while the robot stands still in
  the lounge, and a robot on the rug next to the sleeping cat does "pet" (hearts). Spots that face their object use
  `face: "-gy"`. The office cat (`cat`, `catStep/catThink/catRoute`, `drawCat`: isometric boxes like the robots, scaled by `K`, facing `cat.fa`, parts depth-sorted)
  walks only on the corridor and the lane in front of the lounge (`catLane()`), switching lanes at `GAP_L`, with the
  bowl (`bowlAt()`, an oval in front of the arcade; the cat eats from its -gx side facing +gx) and the rug bed as straight stubs, so its path is axis-aligned like the
  robots'. Hunger rises over time; it eats when hungry, sleeps more at night. Clicking the cat shows hearts. Test hook
  `Office._cat()`. The `activity()` regexes did not change with the isometric view. The page draws about 30 fps when something
  moves and 6 fps when all robots are idle, and stops when the page is hidden. Numbers use a 3x5 pixel font (`pix`).
  Vietnamese wall text is HTML (`.ow`). The back desk row sits 2 tiles from the right wall and the wall is 84 px tall
  so sprites and bubbles never cover the sign or score board; rows are 4.6 tiles apart so name tags (anchored under each
  seat) do not hit the next row. `walk()` routes from the robot's real `gx/gy` (desk gap, corridor, `GAP_L`, front
  row), also when the target changes mid-walk. Measured 2026-11-06 with 7 robots, 3 running (CDP `TaskDuration`, 8 s,
  old and new back to back): old top-down 34-52 ms/s, isometric 50-64 ms/s (about 1.25-1.5x, noisy); canvas
  0.49 -> 0.63 MB (492 x 338). After the box robots and chairs in front of the desks: 43-74 ms/s over 3 runs (noisy).
- Reward goal per account: `settings["goals"]`, set through `Api.set_goal`. It follows profile renames and deletes.
- `search/catalog.py`: the query catalog. `search/bank.py` hands out queries without repeats across accounts or
  across `history_days`.
- `data/` holds login sessions and cookies. It is never committed. Profile dir = `data/profiles/<profile["dir"]>`,
  which is fixed at creation and is not the display name (for example account `alice` may use `alice_2`).
  One such folder can hold several Edge profiles (for example `Default` = a work account and `Profile 1` = the
  personal MSA). `edge_launcher.pinned_profile()` pins one into `rewards_bot_profile.txt` on first open and the bot
  always passes `--profile-directory`. Never drop that, or Edge silently opens whichever profile was used last.
- Per-account proxy (`profile["proxy"]`, managed mode only): `security.validate_proxy` normalizes it to
  `scheme://host:port` (http/https/socks4/socks5) and rejects `user:pass@` (Chromium can't take it on the command
  line, and it would show in the process list). `browser_args` then passes `--proxy-server` instead of
  `--no-proxy-server`, plus `--force-webrtc-ip-handling-policy=disable_non_proxied_udp` so WebRTC doesn't leak the real IP.
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
  Browse in the same `Profile 1` left Edge – Minutes at 0/30. The cause is unknown. The user later reported (2026-10-23)
  that it does fill when Run is repeated 3–4 times in a day; the guide says so, and suggests turning auto-stop off. `do_browse` now reads Edge – Minutes
  every 10 min, logs `first → now (chạy ẩn/hiện cửa sổ)`, and stops when full or after 20 min without gain
  (the 20-min stop can be turned off with the `browse_auto_stop` setting). Read those
  log lines before claiming anything about what earns it.
- Older note: "Edge – Minutes" (Edge Browsing Streak, 30 min/day) was NOT earned by the bot's Browse in early tests. The following were all
  tested on one account and all gave 0/30: headless, headed, Playwright's background-blocking flags removed, and the Edge
  browser itself signed in to the right MSA (checked in edge://signin-internals). The minutes that did count came
  from the user's own Edge use: the bot profile's History shows no long browse on those days. Do not claim Browse
  earns it.
- Other bots (TheNetsky/Microsoft-Rewards-Script, GPL-3.0) "earn" Edge minutes by POSTing fake usage reports to
  `prod.rewardsplatform.microsoft.com/dapi/me/activities`, as EdgeDesktop, with an OAuth token minted under the
  Bing app's client id. Claude Code's safety classifier blocked this as a third-party attack, and it is not done
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
