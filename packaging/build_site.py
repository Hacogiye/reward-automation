"""Build the public project site (GitHub Pages) into _site/.

Everything on the site comes from one place: the SITE / PAGES data below plus the version in
rewards_bot/__init__.py. The HTML, the JSON-LD, sitemap.xml, robots.txt and llms.txt are all
generated from it, so they can never disagree with each other.

    python packaging/build_site.py               # writes _site/
    SITE_URL=https://example.com/ python packaging/build_site.py

Rules this follows (so ChatGPT search / Bing / Google can find and read the site):
- every fact is plain text in the HTML (no text in images, nothing in collapsed tabs);
- JSON-LD only states what the page shows, and never has empty fields or ratings;
- a page marked noindex gets <meta name="robots" content="noindex"> and is left out of the sitemap;
- robots.txt allows every crawler, OAI-SearchBot named explicitly.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"

REPO = "https://github.com/NT101-lc/reward-automation"
SITE_URL = os.environ.get("SITE_URL", "https://nt101-lc.github.io/reward-automation/").rstrip("/") + "/"


def read_version() -> str:
    text = (ROOT / "rewards_bot" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("__version__ not found in rewards_bot/__init__.py")
    return m.group(1)


def last_modified() -> str:
    """Date of the last commit (YYYY-MM-DD), today when git is unavailable."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", out):
            return out
    except (OSError, subprocess.CalledProcessError):
        pass
    return date.today().isoformat()


# ---------------------------------------------------------------- the single source of site content

SITE = {
    "name": "PrixAuto",
    "author": "NT101-lc",
    "author_url": "https://github.com/NT101-lc",
    "license": "MIT",
    "license_url": f"{REPO}/blob/main/LICENSE",
    "operating_systems": ["Windows 10", "Windows 11", "Linux"],
    "category": "UtilitiesApplication",
    "repo": REPO,
    "releases": f"{REPO}/releases/latest",
    "changelog": f"{REPO}/blob/main/CHANGELOG.md",
    "issues": f"{REPO}/issues",
    "icon": "images/app-icon-256.png",
    # IndexNow (Bing, Yandex...): published as <key>.txt so search engines can check our pings. Not a secret.
    "indexnow_key": "2747f2c80ea55e573dd56a9557147968",
}

# images copied into _site/images/ (source -> published name)
IMAGES = {
    ROOT / "rewards_bot" / "ui" / "web" / "assets" / "app-icon-256.png": "app-icon-256.png",
    **{p: p.name for p in sorted((ROOT / "docs" / "images").glob("*.png"))},
}

PAGES = [
    {
        "path": "",  # -> index.html
        "lang": "en",
        "noindex": False,
        "title": "PrixAuto: free Microsoft Rewards bot for multiple accounts (Windows, Linux)",
        "tagline": "Your daily Microsoft Rewards tasks, done for several accounts, from one desktop app.",
        "description": ("PrixAuto is a free, open-source (MIT) Microsoft Rewards bot for Windows and Linux. It earns "
                        "Microsoft Rewards points automatically: the Daily Set, quests and PC and mobile Bing "
                        "searches, for several Microsoft accounts in parallel, with a dashboard of points and history."),
        "screenshot": "dashboard.png",
        "screenshot_alt": "PrixAuto overview page: points, today's progress and daily chart",
        "labels": {
            "download": "Download for Windows", "source": "Source code on GitHub", "version": "Latest version",
            "features": "Features", "not_supported": "Not supported",
            "install": "Install on Windows", "daily": "Run it every day", "source_h": "Run from source (Windows, Linux)",
            "faq": "Frequently asked questions", "privacy": "Privacy", "links": "Links",
            "changelog": "Changelog", "issues": "Report a problem", "license": "License",
            "other_lang": "Tiếng Việt", "screens": "Screenshots",
        },
        "warning": ("The Microsoft Rewards terms do not allow bots or automated tools to earn points. Microsoft can "
                    "suspend the Rewards account and cancel unredeemed points or orders. PrixAuto is not affiliated "
                    "with or endorsed by Microsoft. Use it at your own risk, and not with an account you cannot "
                    "afford to lose."),
        "features": [
            "Daily tasks: Daily Set, Keep earning (links, polls, simple quizzes) and multi-step Quests.",
            "PC and mobile Bing searches until the points are full, with queries from 22 topics, never repeated "
            "across accounts or within N days.",
            "Optional Visual Search and Browse (Edge – Minutes).",
            "Several accounts in parallel, each in its own Edge profile and window.",
            "Dashboard: points, today's progress, streaks, daily charts, a reward goal with an ETA and per-day history.",
            "Self-check without searching: sign-in, bing.com account, Points breakdown and proxy, with a fix for "
            "each problem.",
            "Optional auto sign-in; the password is encrypted with Windows DPAPI. The bot stops at any verification "
            "step (code, Authenticator, CAPTCHA).",
            "Headless mode (--run-all --headless) for Windows Task Scheduler or cron.",
            "Light and dark theme, English and Vietnamese interface.",
        ],
        "not_supported": "The daily check-in, which only exists in the Microsoft Rewards phone app.",
        "install": [
            "Requirements: Windows 10 or 11 (64-bit), Microsoft Edge (built in) and a Microsoft account that has "
            "joined Microsoft Rewards. No Python needed.",
            "Download the file ending in -win64.zip from the latest release on GitHub.",
            "Extract it to C:\\PrixAuto (not inside the zip, not in Program Files, not in a OneDrive folder).",
            "Open C:\\PrixAuto\\PrixAuto.exe. If Windows SmartScreen appears, click More info, then Run anyway.",
            "On the Accounts page, sign in once per account, then click Check, then Run or Run all. A run takes "
            "about 20–40 minutes per account.",
        ],
        "daily": ("Create a daily task in Windows Task Scheduler that starts C:\\PrixAuto\\PrixAuto.exe with the "
                  "arguments --run-all --headless and starts in C:\\PrixAuto. On Linux, use cron with "
                  "./scripts/run.sh --run-all --headless."),
        "source_cmds": [
            "git clone https://github.com/NT101-lc/reward-automation.git",
            "cd reward-automation",
            "pip install -r requirements.txt",
            "python -m rewards_bot",
        ],
        "source_note": ("Needs Python 3.10 or newer. On Linux you also need Edge, Chrome or Chromium, and GTK or Qt "
                        "for the window."),
        "faq": [
            ("Is PrixAuto free?", "Yes. It is open source under the MIT License, with no ads and no telemetry."),
            ("Can my Microsoft Rewards account be banned?",
             "Yes. Automated tools break the Microsoft Rewards terms, and Microsoft can suspend the account and "
             "cancel points. Only use an account you can afford to lose."),
            ("The app window is blank or closes right away.",
             "Install the Microsoft Edge WebView2 Runtime (Evergreen Bootstrapper) and open the app again. Details "
             "are in data\\crash.log."),
            ("Mobile searches give 0 points.",
             "Run Check and make sure the bing.com tab is signed in to the same account as Rewards."),
            ("How do I update?",
             "The app shows a bar when a new version is released. Click Update now: it downloads the zip, checks its "
             "SHA-256 and restarts. Accounts and settings are kept."),
        ],
        "privacy": ("Everything stays on your computer. The only network calls besides Bing and Rewards are the "
                    "update check, which reads the public release list on GitHub and can be turned off."),
    },
    {
        "path": "vi/",
        "lang": "vi",
        "noindex": False,
        "title": "PrixAuto: tool auto Microsoft Rewards miễn phí, cày điểm nhiều tài khoản (Windows, Linux)",
        "tagline": "Tự làm các việc Microsoft Rewards hằng ngày cho nhiều tài khoản, trong một app trên máy tính.",
        "description": ("PrixAuto là tool auto Microsoft Rewards miễn phí, mã nguồn mở (MIT) cho Windows và Linux. App "
                        "tự cày điểm Microsoft Rewards: làm Daily Set, Quests, tự search Bing trên PC và Mobile cho "
                        "nhiều tài khoản Microsoft cùng lúc, kèm dashboard điểm và lịch sử."),
        "screenshot": "dashboard-vi.png",
        "screenshot_alt": "Trang Tổng quan của PrixAuto: điểm, tiến độ hôm nay và biểu đồ theo ngày",
        "labels": {
            "download": "Tải cho Windows", "source": "Mã nguồn trên GitHub", "version": "Phiên bản mới nhất",
            "features": "Tính năng", "not_supported": "Chưa làm được",
            "install": "Cài đặt trên Windows", "daily": "Chạy tự động mỗi ngày",
            "source_h": "Chạy từ mã nguồn (Windows, Linux)",
            "faq": "Câu hỏi thường gặp", "privacy": "Quyền riêng tư", "links": "Liên kết",
            "changelog": "Danh sách thay đổi", "issues": "Báo lỗi", "license": "Giấy phép",
            "other_lang": "English", "screens": "Ảnh chụp màn hình",
        },
        "warning": ("Điều khoản của Microsoft Rewards cấm dùng bot hay công cụ tự động để kiếm điểm. Microsoft có thể "
                    "khóa tài khoản Rewards, hủy điểm chưa đổi hoặc hủy quà đã đổi. PrixAuto không liên quan và không "
                    "được Microsoft xác nhận. Bạn tự chịu mọi rủi ro; đừng dùng với tài khoản mà bạn không muốn mất."),
        "features": [
            "Task hằng ngày: Daily Set, Keep earning (link, poll, quiz cơ bản), Quests nhiều bước.",
            "Search Bing trên PC và Mobile đến khi đủ điểm, câu search từ 22 lĩnh vực, không trùng giữa các tài "
            "khoản và không lặp lại trong N ngày.",
            "Visual Search và Browse (Edge – Minutes), bật tắt riêng.",
            "Nhiều tài khoản song song, mỗi tài khoản một profile Edge và một cửa sổ riêng.",
            "Dashboard: điểm, tiến độ hôm nay, streak, biểu đồ theo ngày, mục tiêu đổi quà kèm dự kiến số ngày, "
            "lịch sử từng ngày.",
            "Kiểm tra không search: đăng nhập, tài khoản bing.com, Points breakdown, proxy; mỗi lỗi kèm cách sửa.",
            "Tự đăng nhập lại (không bắt buộc), mật khẩu mã hóa bằng Windows DPAPI. Gặp bước xác minh (mã, "
            "Authenticator, CAPTCHA) thì bot dừng.",
            "Chạy không cần cửa sổ (--run-all --headless) để đặt lịch bằng Task Scheduler hoặc cron.",
            "Giao diện sáng / tối, tiếng Việt / English.",
        ],
        "not_supported": "Check-in hằng ngày (chỉ có trong app Microsoft Rewards trên điện thoại).",
        "install": [
            "Cần: Windows 10 hoặc 11 bản 64-bit, Microsoft Edge (có sẵn) và một tài khoản Microsoft đã tham gia "
            "Microsoft Rewards. Không cần cài Python.",
            "Tải file có đuôi -win64.zip ở bản phát hành mới nhất trên GitHub.",
            "Giải nén ra C:\\PrixAuto (không chạy trong file zip, không để trong Program Files hay thư mục OneDrive).",
            "Mở C:\\PrixAuto\\PrixAuto.exe. Nếu Windows SmartScreen hiện ra, bấm More info rồi Run anyway.",
            "Ở trang Tài khoản, đăng nhập một lần cho mỗi tài khoản, bấm Kiểm tra, rồi Chạy hoặc Chạy tất cả. Mỗi tài "
            "khoản chạy khoảng 20–40 phút.",
        ],
        "daily": ("Tạo một task hằng ngày trong Windows Task Scheduler chạy C:\\PrixAuto\\PrixAuto.exe với tham số "
                  "--run-all --headless, thư mục bắt đầu C:\\PrixAuto. Trên Linux dùng cron với "
                  "./scripts/run.sh --run-all --headless."),
        "source_cmds": [
            "git clone https://github.com/NT101-lc/reward-automation.git",
            "cd reward-automation",
            "pip install -r requirements.txt",
            "python -m rewards_bot",
        ],
        "source_note": ("Cần Python 3.10 trở lên. Trên Linux cần thêm Edge, Chrome hoặc Chromium, và GTK hoặc Qt để "
                        "mở cửa sổ app."),
        "faq": [
            ("PrixAuto có miễn phí không?", "Có. Mã nguồn mở theo giấy phép MIT, không quảng cáo, không thu thập dữ liệu."),
            ("Tài khoản Microsoft Rewards có bị khóa không?",
             "Có thể. Công cụ tự động vi phạm điều khoản Microsoft Rewards; Microsoft có thể khóa tài khoản và hủy "
             "điểm. Chỉ dùng với tài khoản mà bạn chấp nhận mất."),
            ("Cửa sổ app trắng trơn hoặc tắt ngay.",
             "Cài Microsoft Edge WebView2 Runtime (Evergreen Bootstrapper) rồi mở lại app. Chi tiết lỗi nằm trong "
             "data\\crash.log."),
            ("Search Mobile được 0 điểm.",
             "Bấm Kiểm tra và xem tab bing.com có đăng nhập đúng tài khoản Rewards không."),
            ("Cập nhật thế nào?",
             "Khi có bản mới, app hiện thanh thông báo. Bấm Cập nhật ngay: app tải zip, kiểm tra SHA-256 rồi khởi "
             "động lại. Tài khoản và cài đặt được giữ nguyên."),
        ],
        "privacy": ("Mọi dữ liệu nằm trên máy bạn. Ngoài Bing và Rewards, app chỉ kiểm tra bản cập nhật bằng cách đọc "
                    "danh sách phát hành công khai trên GitHub (tắt được trong Cài đặt)."),
    },
]


# ---------------------------------------------------------------- builders

def page_url(page: dict) -> str:
    return SITE_URL + page["path"]


def check_no_empty(value, where: str = "jsonld") -> None:
    """JSON-LD must not carry empty strings, lists or objects."""
    if value is None or value == "" or value == [] or value == {}:
        raise ValueError(f"empty JSON-LD value at {where}")
    if isinstance(value, dict):
        for k, v in value.items():
            check_no_empty(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            check_no_empty(v, f"{where}[{i}]")


def jsonld(page: dict, version: str) -> dict:
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": SITE["name"],
        "description": page["description"],
        "url": page_url(page),
        "inLanguage": page["lang"],
        "applicationCategory": SITE["category"],
        "operatingSystem": ", ".join(SITE["operating_systems"]),
        "softwareVersion": version,
        "downloadUrl": SITE["releases"],
        "releaseNotes": SITE["changelog"],
        "license": SITE["license_url"],
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "image": SITE_URL + SITE["icon"],
        "screenshot": SITE_URL + "images/" + page["screenshot"],
        "author": {"@type": "Person", "name": SITE["author"], "url": SITE["author_url"]},
        "sameAs": [SITE["repo"]],
    }
    check_no_empty(data)
    return data


def faq_jsonld(page: dict) -> dict:
    """FAQPage built from the same questions and answers that the page shows as text."""
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": page["lang"],
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in page["faq"]
        ],
    }
    check_no_empty(data)
    return data


def _ld_script(data: dict) -> str:
    body = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{body}\n</script>'


def indexnow_payload() -> dict:
    """Body for https://api.indexnow.org/indexnow: every indexable page, checked against the published key."""
    host = re.sub(r"^https?://", "", SITE_URL).split("/")[0]
    return {
        "host": host,
        "key": SITE["indexnow_key"],
        "keyLocation": SITE_URL + SITE["indexnow_key"] + ".txt",
        "urlList": [page_url(p) for p in PAGES if not p["noindex"]],
    }


CSS = """
:root{--bg:#ffffff;--fg:#0f172a;--muted:#475569;--card:#f1f5f9;--accent:#2563eb;--warn-bg:#fef3c7;--warn-fg:#78350f}
@media (prefers-color-scheme:dark){:root{--bg:#0b1120;--fg:#e2e8f0;--muted:#94a3b8;--card:#1e293b;--accent:#60a5fa;--warn-bg:#422006;--warn-fg:#fde68a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 48px}
header{text-align:center}
header img.logo{width:80px;height:80px}
h1{margin:.3em 0 .1em;font-size:2rem}
.tagline{color:var(--muted);font-size:1.1rem;margin:0 0 1em}
.buttons a{display:inline-block;margin:4px;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600}
.primary{background:var(--accent);color:#fff}
.secondary{background:var(--card);color:var(--fg)}
.meta{color:var(--muted);font-size:.9rem}
.warning{background:var(--warn-bg);color:var(--warn-fg);padding:12px 16px;border-radius:8px;margin:24px 0}
img.shot{width:100%;height:auto;border-radius:8px;border:1px solid var(--card)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
pre{background:var(--card);padding:12px;border-radius:8px;overflow-x:auto}
a{color:var(--accent)}
h3{margin-bottom:.2em}
footer{color:var(--muted);font-size:.9rem;margin-top:40px;border-top:1px solid var(--card);padding-top:16px}
"""


def render_page(page: dict, version: str) -> str:
    e = html.escape
    L = page["labels"]
    other = next(p for p in PAGES if p is not page)
    to_root = "../" * page["path"].count("/")
    img = to_root + "images/"

    alternates = "\n".join(
        f'<link rel="alternate" hreflang="{p["lang"]}" href="{page_url(p)}">' for p in PAGES if not p["noindex"]
    )
    robots = '<meta name="robots" content="noindex">' if page["noindex"] else ""
    features = "\n".join(f"<li>{e(f)}</li>" for f in page["features"])
    install = "\n".join(f"<li>{e(s)}</li>" for s in page["install"])
    cmds = e("\n".join(page["source_cmds"]))
    faq = "\n".join(f"<h3>{e(q)}</h3>\n<p>{e(a)}</p>" for q, a in page["faq"])
    shots = "\n".join(
        f'<img class="shot" src="{img}{name}" alt="{e(name.removesuffix(".png").replace("-", " "))}" '
        f'loading="lazy" width="900" height="560">'
        for name in ("accounts.png", "history.png", "dashboard-dark.png", "settings.png")
    )
    ld = _ld_script(jsonld(page, version)) + "\n" + _ld_script(faq_jsonld(page))

    return f"""<!doctype html>
<html lang="{page['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(page['title'])}</title>
<meta name="description" content="{e(page['description'])}">
{robots}
<link rel="canonical" href="{page_url(page)}">
{alternates}
<link rel="icon" href="{img}app-icon-256.png">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(page['title'])}">
<meta property="og:description" content="{e(page['description'])}">
<meta property="og:url" content="{page_url(page)}">
<meta property="og:image" content="{SITE_URL}images/{page['screenshot']}">
<meta property="og:image:alt" content="{e(page['screenshot_alt'])}">
<meta property="og:site_name" content="{SITE['name']}">
<meta property="og:locale" content="{'vi_VN' if page['lang'] == 'vi' else 'en_US'}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(page['title'])}">
<meta name="twitter:description" content="{e(page['description'])}">
<meta name="twitter:image" content="{SITE_URL}images/{page['screenshot']}">
<style>{CSS}</style>
{ld}
</head>
<body>
<main>
<header>
<img class="logo" src="{img}app-icon-256.png" alt="{SITE['name']} logo" width="80" height="80">
<h1>{SITE['name']}</h1>
<p class="tagline">{e(page['tagline'])}</p>
<p>{e(page['description'])}</p>
<p class="buttons">
<a class="primary" href="{SITE['releases']}">{e(L['download'])}</a>
<a class="secondary" href="{SITE['repo']}">{e(L['source'])}</a>
</p>
<p class="meta">{e(L['version'])}: {e(version)} · {e(SITE['license'])} · {e(', '.join(SITE['operating_systems']))} ·
<a href="{to_root}{other['path']}" hreflang="{other['lang']}" lang="{other['lang']}">{e(L['other_lang'])}</a></p>
</header>

<p class="warning"><strong>⚠</strong> {e(page['warning'])}</p>

<img class="shot" src="{img}{page['screenshot']}" alt="{e(page['screenshot_alt'])}" width="900" height="560">

<h2>{e(L['features'])}</h2>
<ul>
{features}
</ul>
<p><strong>{e(L['not_supported'])}:</strong> {e(page['not_supported'])}</p>

<h2>{e(L['install'])}</h2>
<ol>
{install}
</ol>

<h2>{e(L['daily'])}</h2>
<p>{e(page['daily'])}</p>

<h2>{e(L['source_h'])}</h2>
<pre><code>{cmds}</code></pre>
<p>{e(page['source_note'])}</p>

<h2>{e(L['screens'])}</h2>
<div class="grid">
{shots}
</div>

<h2>{e(L['faq'])}</h2>
{faq}

<h2>{e(L['privacy'])}</h2>
<p>{e(page['privacy'])}</p>

<h2>{e(L['links'])}</h2>
<ul>
<li><a href="{SITE['repo']}">GitHub: {SITE['repo']}</a></li>
<li><a href="{SITE['releases']}">{e(L['download'])}</a></li>
<li><a href="{SITE['changelog']}">{e(L['changelog'])}</a></li>
<li><a href="{SITE['issues']}">{e(L['issues'])}</a></li>
<li><a href="{SITE['license_url']}">{e(L['license'])}: {e(SITE['license'])}</a></li>
</ul>

<footer>
<p>"Microsoft", "Bing", "Edge" and "Microsoft Rewards" are trademarks of Microsoft Corporation.
{SITE['name']} is not affiliated with Microsoft. © {SITE['author']} · {e(SITE['license'])}</p>
</footer>
</main>
</body>
</html>
"""


def render_sitemap(lastmod: str) -> str:
    urls = "\n".join(
        f"  <url><loc>{html.escape(page_url(p))}</loc><lastmod>{lastmod}</lastmod></url>"
        for p in PAGES if not p["noindex"]
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n")


def render_robots() -> str:
    return ("# Search and AI search crawlers are welcome.\n"
            "User-agent: OAI-SearchBot\nAllow: /\n\n"
            "User-agent: *\nAllow: /\n\n"
            f"Sitemap: {SITE_URL}sitemap.xml\n")


def render_llms(version: str) -> str:
    en = PAGES[0]
    feats = "\n".join(f"- {f}" for f in en["features"])
    pages = "\n".join(f"- [{p['title']}]({page_url(p)})" for p in PAGES if not p["noindex"])
    return f"""# {SITE['name']}

> {en['description']}

Latest version: {version}. License: {SITE['license']}. Platforms: {', '.join(SITE['operating_systems'])}.

Warning: {en['warning']}

## Features

{feats}

## Pages

{pages}

## Links

- [Source code]({SITE['repo']})
- [Download (latest release)]({SITE['releases']})
- [README (English)]({SITE['repo']}/blob/main/README.en.md)
- [README (Vietnamese)]({SITE['repo']}/blob/main/README.md)
- [Changelog]({SITE['changelog']})
"""


def build(out: Path = OUT) -> Path:
    version = read_version()
    lastmod = last_modified()
    if out.exists():
        shutil.rmtree(out)
    (out / "images").mkdir(parents=True)
    for src, name in IMAGES.items():
        shutil.copyfile(src, out / "images" / name)
    for page in PAGES:
        target = out / page["path"] / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_page(page, version), encoding="utf-8")
    (out / "sitemap.xml").write_text(render_sitemap(lastmod), encoding="utf-8")
    (out / "robots.txt").write_text(render_robots(), encoding="utf-8")
    (out / "llms.txt").write_text(render_llms(version), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / f"{SITE['indexnow_key']}.txt").write_text(SITE["indexnow_key"], encoding="utf-8")
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--indexnow"]:
        print(json.dumps(indexnow_payload()))
        raise SystemExit(0)
    path = build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
    print(f"site written to {path} ({SITE_URL})")
