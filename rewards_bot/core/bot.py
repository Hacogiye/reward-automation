"""Bot Microsoft Rewards cho MỘT profile. Mỗi profile chạy trong thread riêng với sync_playwright riêng."""

import base64
import json
import random
import re
import threading
import time
from urllib.parse import quote_plus, urljoin, urlparse

from playwright.sync_api import sync_playwright, BrowserContext, Page, TimeoutError as PWTimeout

from . import credentials, edge_launcher, security
from .browser import ProfileInUse, free_profile
from .config import VISUAL_TRIES_FILE, profile_dir, read_json, write_json
from .rewards_page import (SCRAPE_JS, activity, build_task_rows, empty_state, group_icons, icon, parse_breakdown,
                           parse_page, stats, streak_info)
from ..search.bank import QueryBank
from ..search.catalog import IMAGE_QUERIES

REWARDS = "https://rewards.bing.com"
DASHBOARD_URL = REWARDS + "/dashboard"
EARN_URL = REWARDS + "/earn"
POINTS_PER_SEARCH = 3

# Dùng khi không đọc được phiên bản trình duyệt thật
FALLBACK_VERSIONS = {"chromium": "141.0.7390.55", "edge": "141.0.3537.57"}

# Trang dùng cho task "browse": tin tức / kiến thức, nhiều link nội bộ để lướt tiếp
BROWSE_SITES = [
    "https://www.msn.com/",
    "https://www.bing.com/news",
    "https://en.wikipedia.org/wiki/Special:Random",
    "https://apnews.com/",
    "https://www.nationalgeographic.com/",
    "https://www.theverge.com/",
    "https://www.reuters.com/",
    "https://www.britannica.com/",
    "https://www.bing.com/weather",
    "https://www.howstuffworks.com/",
]


_VISUAL_LOCK = threading.Lock()  # nhiều tài khoản chạy song song cùng ghi visual_tries.json


def visual_tries(name: str, add: int = 0, path=None) -> int:
    """Số lần đã thử Visual Search hôm nay của tài khoản (cộng thêm `add`). Chỉ giữ số của ngày hiện tại."""
    path = path or VISUAL_TRIES_FILE
    today = time.strftime("%Y-%m-%d")
    with _VISUAL_LOCK:
        data = read_json(path, {})
        day = data.get(today, {}) if isinstance(data, dict) else {}
        n = int(day.get(name, 0)) + add
        if add:
            write_json(path, {today: {**day, name: n}})
        return n


class StopRequested(Exception):
    pass


class NotLoggedIn(Exception):
    pass


class RewardsBot:
    def __init__(self, profile: dict, settings: dict, bank: QueryBank, log, status, stop: threading.Event):
        self.profile = profile
        self.name = profile["name"]
        self.s = settings
        self.bank = bank
        self._log = log          # log(name, msg)
        self._status = status    # status(name, dict)
        self.stop = stop
        self.state = empty_state()
        self.stalled: set = set()  # loại search bị dừng vì không được cộng điểm
        self.local: dict = {}    # task do app tự làm: title -> {"progress","max","unit"}
        self._launched = None    # trình duyệt do bot mở (edge_launcher), None ở chế độ gắn vào Edge
        self._browser = None
        self.now = time.time     # đồng hồ (test thay bằng đồng hồ giả)
        # giới hạn chỉnh được trong Cài đặt (thiếu thì dùng mặc định của lớp)
        self.STALL_AFTER = int(settings.get("stall_after", RewardsBot.STALL_AFTER))
        self.VISUAL_MAX_TRIES = int(settings.get("visual_max_tries", RewardsBot.VISUAL_MAX_TRIES))

    # ------------------------------------------------------------ helpers
    def log(self, msg: str) -> None:
        # lỗi Playwright kèm "Call log:" nhiều dòng -> chỉ giữ dòng lỗi chính cho nhật ký gọn
        self._log(self.name, msg.split("\nCall log:")[0].rstrip())

    def status(self, **kw) -> None:
        self._status(self.name, kw)

    def sleep(self, a: float, b: float = None) -> None:
        if self.stop.wait(random.uniform(a, b if b is not None else a)):
            raise StopRequested()

    def check_stop(self) -> None:
        if self.stop.is_set():
            raise StopRequested()

    # task của app -> dòng "Your activity" trên Rewards mà nó nhắm tới (key = tên dòng viết thường)
    LOCAL_TO_ACTIVITY = {"Browse": "edge", "Visual Search": "visual search"}

    def report(self) -> None:
        """Gửi danh sách task (từ Rewards + task thêm của app) lên giao diện."""
        rows = build_task_rows(self.state)
        local_icons = {"Visual Search": icon(self.state, "visual search"), "Browse": icon(self.state, "edge", "bing")}
        for title, t in self.local.items():
            bot_note = f"bot: {t['progress']}/{t['max']} {t['unit']}"
            target = activity(self.state, self.LOCAL_TO_ACTIVITY.get(title, ""))
            row = next((r for r in rows if target and r["group"] == "Hoạt động" and r["title"] == target["title"]),
                       None)
            if row:  # cập nhật vào dòng Rewards tương ứng thay vì thêm dòng mới; tiến độ chính vẫn là số của Rewards
                row["bot"] = bot_note
                continue
            rows.append({"group": "Task thêm", "title": title, "progress": t["progress"], "max": t["max"],
                         "unit": t["unit"], "done": t["progress"] >= t["max"], "img": local_icons.get(title, "")})
        self.status(tasks=rows, today=self.state.get("today"), stats=stats(self.state),
                    icons=group_icons(self.state), streak=streak_info(self.state),
                    updated=time.strftime("%H:%M %d/%m"))

    def set_local(self, title: str, progress, total, unit: str) -> None:
        self.local[title] = {"progress": progress, "max": total, "unit": unit}
        self.report()

    # ------------------------------------------------------------ browser
    def _open(self, p, headless: bool) -> BrowserContext:
        if self.profile.get("mode") == "cdp":
            port = security.validate_port(self.profile.get("cdp_port") or 9222)
            if security.cdp_exposed(port):
                raise RuntimeError(f"Cổng debug {port} đang mở ra mạng LAN, máy khác có thể điều khiển trình duyệt. "
                                   "Mở lại Edge chỉ với --remote-debugging-port (không dùng --remote-debugging-address)")
            self.log(f"Gắn vào trình duyệt đang mở ở cổng {port} (chỉ localhost)")
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            return browser.contexts[0] if browser.contexts else browser.new_context()
        d = profile_dir(self.profile)
        d.mkdir(parents=True, exist_ok=True)
        free_profile(d, self.log)  # đóng Edge mồ côi của bot / báo rõ nếu profile đang mở ở cửa sổ khác
        own_proxy = security.validate_proxy(self.profile.get("proxy"))
        if own_proxy:
            self.log(f"Trình duyệt đi qua proxy riêng của tài khoản: {own_proxy}")
        elif self.s.get("bypass_proxy", True):
            proxy = security.system_proxy()
            if proxy:
                self.log(f"Máy đang bật proxy ({proxy}); trình duyệt của bot bỏ qua proxy này")
        # mở trình duyệt "thường" (ít cờ, không có cờ tự động hóa của Playwright) rồi gắn vào qua CDP cục bộ;
        # chứng chỉ HTTPS vẫn được kiểm tra như trình duyệt bình thường
        self._launched = edge_launcher.launch(self.s.get("browser_channel", "msedge"), str(d), headless,
                                              extra=security.browser_args(self.s, own_proxy),
                                              profile_directory=edge_launcher.pinned_profile(str(d)))
        try:
            self._browser = p.chromium.connect_over_cdp(self._launched.cdp_url)
        except Exception:
            self._launched.close()
            self._launched = None
            raise
        ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        ctx.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})  # trang Rewards hiện tiếng Anh để đọc được
        return ctx

    def _close(self, ctx: BrowserContext, own: list) -> None:
        for pg in own:
            try:
                pg.close()
            except Exception:
                pass
        if self._launched is not None:
            self._launched.close(self._browser)
            self._launched = self._browser = None

    @staticmethod
    def _real_versions(ctx: BrowserContext, cdp) -> dict:
        """Phiên bản Chromium / Edge thật của trình duyệt đang chạy (để giả lập mobile không lệch phiên bản)."""
        for pg in ctx.pages:  # tab desktop đang ở https -> có fullVersionList đầy đủ
            if not pg.url.startswith("https://"):
                continue
            try:
                lst = pg.evaluate("async () => (await navigator.userAgentData.getHighEntropyValues("
                                  "['fullVersionList'])).fullVersionList")
                v = {b["brand"]: b["version"] for b in lst}
                if "Chromium" in v:
                    return {"chromium": v["Chromium"], "edge": v.get("Microsoft Edge")}
            except Exception:
                pass
        try:  # UA rút gọn: chỉ có số phiên bản chính
            ua = cdp.send("Browser.getVersion")["userAgent"]
            v = {"chromium": re.search(r"Chrome/([\d.]+)", ua).group(1)}
            edge = re.search(r"Edg/([\d.]+)", ua)
            v["edge"] = edge.group(1) if edge else None
            return v
        except Exception:
            return dict(FALLBACK_VERSIONS)

    @staticmethod
    def mobile_profile(versions: dict) -> dict:
        """UA + client hints của Edge trên Android, khớp đúng phiên bản trình duyệt thật.

        Bing so sánh User-Agent với Sec-CH-UA-*; nếu lệch (vd UA cũ 129 nhưng full-version-list là 155,
        bitness 64 trên điện thoại) thì search Mobile có thể không được tính cho tài khoản bị soi kỹ.
        """
        chromium, edge = versions["chromium"], versions.get("edge")
        major = chromium.split(".")[0]
        brands = [{"brand": "Chromium", "version": major}, {"brand": "Not(A:Brand", "version": "24"}]
        full = [{"brand": "Chromium", "version": chromium}, {"brand": "Not(A:Brand", "version": "24.0.0.0"}]
        ua = f"Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Mobile Safari/537.36"
        if edge:
            brands.insert(0, {"brand": "Microsoft Edge", "version": edge.split(".")[0]})
            full.insert(0, {"brand": "Microsoft Edge", "version": edge})
            ua += f" EdgA/{edge.split('.')[0]}.0.0.0"
        else:
            brands.insert(0, {"brand": "Google Chrome", "version": major})
            full.insert(0, {"brand": "Google Chrome", "version": chromium})
        return {
            "userAgent": ua,
            "platform": "Linux armv81",
            "userAgentMetadata": {
                "brands": brands, "fullVersionList": full, "fullVersion": edge or chromium,
                "platform": "Android", "platformVersion": "14.0.0", "architecture": "", "bitness": "",
                "model": "Pixel 8", "mobile": True, "wow64": False,
            },
        }

    @classmethod
    def _emulate_mobile(cls, ctx: BrowserContext, page: Page):
        """Giả lập điện thoại Android cho 1 tab (search Mobile được tính riêng với PC)."""
        cdp = ctx.new_cdp_session(page)
        cdp.send("Emulation.setUserAgentOverride", cls.mobile_profile(cls._real_versions(ctx, cdp)))
        cdp.send("Emulation.setDeviceMetricsOverride",
                 {"width": 412, "height": 915, "deviceScaleFactor": 2.625, "mobile": True})
        cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
        return cdp

    # ------------------------------------------------------------ đọc trạng thái
    def _load(self, page: Page, url: str, marker: str) -> list:
        """Mở trang Rewards và đợi nội dung chính hiện ra (theo chữ marker hoặc số điểm trong nút hồ sơ).

        Trang Rewards thỉnh thoảng tải rất chậm hoặc treo một lần rồi lần sau lại bình thường, nên lỗi hết giờ được
        thử lại 1 lần trước khi báo lỗi.
        """
        for attempt in (1, 2):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_function(
                    """(m) => document.body && (document.body.innerText.toLowerCase().includes(m.toLowerCase())
                             || !!document.querySelector('button[aria-label="View profile"]'))""",
                    arg=marker, timeout=25000)
                break
            except PWTimeout as e:
                host = urlparse(page.url).netloc
                if "login" in host or "microsoftonline" in host or page.locator("text=Sign in").count():
                    raise NotLoggedIn()
                if attempt == 1:
                    self.log(f"  trang {urlparse(url).path} tải chậm, thử lại")
                    self.sleep(3, 6)
                    continue
                if "goto" in str(e).lower():
                    raise RuntimeError(f"Không mở được {url} sau 2 lần (mạng chậm hoặc Rewards đang lỗi)")
                raise RuntimeError(f"Trang {urlparse(url).path} không có mục '{marker}' sau 2 lần chờ "
                                   "(mạng chậm hoặc Rewards đã đổi giao diện)")
        self.sleep(1.5, 2.5)
        return page.evaluate(SCRAPE_JS)

    def read_state(self, page: Page) -> dict:
        """Đọc điểm + trạng thái task từ /dashboard và /earn."""
        st = empty_state()
        parse_page(self._load(page, DASHBOARD_URL, "Available points"), st)
        try:  # trang Earn là phần phụ: lỗi thì vẫn chạy tiếp với dữ liệu từ Dashboard
            parse_page(self._load(page, EARN_URL, "Today's points"), st)
            self._read_breakdown(page, st)
        except (StopRequested, NotLoggedIn):
            raise
        except Exception as e:
            self.log(f"cảnh báo: không đọc được trang Earn ({e}); Keep earning và điểm PC/Mobile có thể thiếu")
        self.state = st
        self.status(points=st["available"] if st["available"] is not None else "")
        self.report()
        return st

    def _read_breakdown(self, page: Page, st: dict) -> None:
        """Mở hộp 'Points breakdown' (đang ở /earn) để lấy điểm search PC/Mobile."""
        try:
            page.get_by_role("button", name=re.compile("Points breakdown")).first.click(timeout=8000)
            dlg = page.locator("[role=dialog]").first
            dlg.get_by_text("Desktop Bing search").first.wait_for(timeout=10000)
            parse_breakdown(dlg.inner_text(), st)
            page.keyboard.press("Escape")
        except Exception as e:
            self.log(f"Không đọc được Points breakdown: {e}")

    # ------------------------------------------------------------ làm 1 thẻ task
    def _poll(self, page: Page) -> None:
        self._click(page, f"#btoption{random.randint(0, 1)}", 8000)
        self.sleep(3, 5)

    @staticmethod
    def _click(page: Page, selector: str, timeout: int = 3000) -> bool:
        try:
            page.locator(selector).first.click(timeout=timeout)
            return True
        except Exception:
            return False

    def _quiz(self, page: Page) -> None:
        self._click(page, "#rqStartQuiz", 8000)
        self.sleep(2, 4)
        for _ in range(30):
            self.check_stop()
            if page.locator("#quizCompleteContainer").count():
                break
            options = page.locator("[id^='rqAnswerOption']")
            n = options.count()
            if n == 0:
                if not self._click(page, "[id^='questionOptionChoice']"):
                    break
                self.sleep(2, 3)
                self._click(page, "[id^='nextQuestionbtn']")
                self.sleep(2, 3)
                continue
            clicked = False
            for i in range(n):
                opt = options.nth(i)
                try:
                    if opt.get_attribute("iscorrectoption") == "True" and opt.is_visible():
                        opt.click(timeout=3000)
                        clicked = True
                        self.sleep(2, 4)
                except Exception:
                    pass
            if not clicked:
                try:
                    options.nth(random.randrange(n)).click(timeout=3000)
                except Exception:
                    pass
                self.sleep(2, 4)

    def _interact(self, tab: Page) -> None:
        """Thao tác trên trang task vừa mở: poll / quiz nếu có, không thì đọc và cuộn trang."""
        self.sleep(4, 7)
        if tab.locator("#btoption0").count():
            self._poll(tab)
        elif tab.locator("#rqStartQuiz, [id^='rqAnswerOption'], [id^='questionOptionChoice']").count():
            self._quiz(tab)
        else:
            for _ in range(random.randint(2, 4)):
                tab.mouse.wheel(0, random.randint(300, 800))
                self.sleep(2, 4)

    @staticmethod
    def _card_locator(page: Page, card: dict):
        """Đúng thẻ cần bấm: ưu tiên theo vị trí (kiểm tra tiêu đề khớp), không thì thẻ thứ n cùng tiêu đề + link."""
        if card.get("index", -1) >= 0:
            loc = page.locator("a").nth(card["index"])
            try:
                if loc.inner_text(timeout=3000).split("\n")[0].strip() == card["title"]:
                    return loc
            except Exception:
                pass
        return page.locator(f"a[href={json.dumps(card['href'])}]", has_text=card["title"]).nth(card.get("dup", 0))

    def _open_card(self, page: Page, card: dict) -> None:
        """Bấm thẻ task trên trang Rewards (mở tab mới), làm task, rồi đóng tab."""
        href = card["href"]
        link = self._card_locator(page, card)
        tab = None
        try:
            with page.context.expect_page(timeout=15000) as info:
                link.click(timeout=10000)
            tab = info.value
            tab.wait_for_load_state("domcontentloaded", timeout=30000)
        except PWTimeout:
            # thẻ không mở tab mới -> mở trực tiếp
            tab = page.context.new_page()
            tab.goto(urljoin(REWARDS, href), wait_until="domcontentloaded", timeout=30000)
        try:
            self._interact(tab)
        finally:
            try:
                tab.close()
            except Exception:
                pass

    # ------------------------------------------------------------ các nhóm task
    def do_cards(self, page: Page) -> None:
        """Daily Set + Keep earning."""
        for group, key, url, marker in (("Daily Set", "daily", DASHBOARD_URL, "Available points"),
                                        ("Keep earning", "more", EARN_URL, "Today's points")):
            todo = [c for c in self.state.get(key, []) if not c["done"]]
            self.log(f"{group}: {len(todo)} task chưa làm")
            for i, c in enumerate(todo, 1):
                self.check_stop()
                self.status(progress=f"{group} {i}/{len(todo)}")
                self.log(f"  {group}: {c['title']} (+{c['points']})")
                try:
                    self._load(page, url, marker)
                    self._open_card(page, c)
                except (StopRequested, NotLoggedIn):
                    raise
                except Exception as e:
                    self.log(f"  lỗi task: {e}")
                self.sleep(2, 4)

    def do_quest_tasks(self, page: Page) -> None:
        """Quests (nhiều bước, vd "5/6 tasks"): trang quest chỉ hiện bước kế tiếp ở mục 'Activities'.

        Bước không làm được trên máy tính (vd chỉ có trên app điện thoại) hoặc làm 2 lần vẫn không được ghi nhận thì
        bỏ qua quest đó, để không lặp mãi.
        """
        todo = [q for q in self.state.get("quests", []) if q["progress"] < q["max"]]
        self.log(f"Quests: {len(todo)} quest chưa xong")
        for q in todo:
            last, repeats = None, 0
            for step in range(q["max"] - q["progress"]):
                self.check_stop()
                self.status(progress=f"Quest {q['title'][:25]} {q['progress'] + step + 1}/{q['max']}")
                page.goto(urljoin(REWARDS, q["href"]), wait_until="domcontentloaded", timeout=60000)
                self.sleep(4, 6)
                acts = [it for it in page.evaluate(SCRAPE_JS)
                        if it["section"].lower() == "activities" and it["tag"] == "A" and it["href"].startswith("http")]
                if not acts:
                    try:  # quest khóa sau app Rewards trên máy tính (các bước không có link, có ổ khóa)
                        needs_app = page.locator("text=Desktop Rewards App").count() > 0
                    except Exception:
                        needs_app = False
                    self.log(f"  Quest '{q['title'][:40]}': " + ("các bước còn lại phải mở khóa bằng app Microsoft "
                                                                  "Rewards trên máy tính, bỏ qua" if needs_app else
                                                                  "bước tiếp theo không làm được trên máy tính, bỏ qua"))
                    break
                act = acts[0]
                repeats = repeats + 1 if act["href"] == last else 0
                if repeats >= 2:
                    self.log(f"  Quest '{q['title'][:40]}': bước này làm 2 lần vẫn không được ghi nhận, bỏ qua")
                    break
                last = act["href"]
                self.log(f"  Quest: {q['title'][:40]} → {act['lines'][0]}")
                try:
                    self._open_card(page, {"title": act["lines"][0], "href": act["href"], "index": act["index"]})
                except (StopRequested, NotLoggedIn):
                    raise
                except Exception as e:
                    self.log(f"  lỗi quest: {e}")
                self.sleep(3, 6)

    def retry_missed_cards(self, page: Page) -> None:
        """Thẻ đã làm mà Rewards chưa ghi nhận (thường do bấm chưa đủ lâu hoặc trang tải chậm) thì làm lại 1 lần."""
        def missed(st):
            return [c["title"] for c in st["daily"] + st["more"] if not c["done"]]

        left = missed(self.read_state(page))
        if not left:
            return
        self.log(f"{len(left)} thẻ chưa được Rewards ghi nhận, làm lại 1 lần: " + "; ".join(left))
        self.sleep(5, 10)
        self.do_cards(page)
        left = missed(self.read_state(page))
        if left:
            self.log("cảnh báo: các thẻ vẫn chưa được Rewards ghi nhận sau 2 lần làm: " + "; ".join(left))
        else:
            self.log("Đã ghi nhận đủ các thẻ sau khi làm lại")

    # Điểm Rewards mà bing.com hiển thị ở góc phải header = điểm của tài khoản đang đăng nhập trên bing.com
    BING_POINTS_JS = r"""() => Array.from(document.querySelectorAll('#id_h *, #rewid *, .id_button *'))
        .map(e => e.textContent.trim()).filter(x => /^[\d,]{2,}$/.test(x)).map(x => +x.replace(/,/g, ''))"""

    def bing_account_check(self, page: Page) -> tuple:
        """(level, chi tiết): bing.com có đăng nhập đúng tài khoản Rewards không. level: ok / warn / fail."""
        rewards_pts = self.state.get("available")
        try:
            page.goto("https://www.bing.com/", wait_until="domcontentloaded", timeout=30000)
            self.sleep(4, 6)
            pts = page.evaluate(self.BING_POINTS_JS)
        except (StopRequested, NotLoggedIn):
            raise
        except Exception as e:
            return "warn", f"không mở được bing.com để đối chiếu ({e})"
        if not pts or rewards_pts is None:
            return "warn", "không đọc được điểm trên bing.com để đối chiếu tài khoản"
        if abs(pts[0] - rewards_pts) > 200:
            return "fail", (f"bing.com đang đăng nhập tài khoản khác ({pts[0]:,} điểm, Rewards là {rewards_pts:,}). "
                            "Search sẽ cộng điểm cho tài khoản kia. Bấm Đăng nhập, đăng xuất ở tab bing.com "
                            "rồi đăng nhập lại đúng tài khoản")
        return "ok", f"cùng tài khoản ({pts[0]:,} điểm)"

    def bing_account_ok(self, page: Page) -> bool:
        level, detail = self.bing_account_check(page)
        if level == "fail":
            self.log("Lỗi: " + detail + ". Bot bỏ qua phần search.")
            return False
        self.log(("bing.com " + detail) if level == "ok" else ("cảnh báo: " + detail + ", vẫn tiếp tục"))
        return True

    CHECK_EVERY = 3   # cứ bao nhiêu lượt search thì đọc lại điểm
    STALL_AFTER = 6   # bao nhiêu lượt liên tiếp không được cộng điểm thì dừng

    # số lượt mặc định khi không đọc được Points breakdown (90 điểm PC, 60 điểm Mobile / 3 điểm mỗi lượt)
    FALLBACK_SEARCHES = {"pc": 30, "mobile": 20}

    def search_goal(self, kind: str):
        """Số điểm search cần đạt hôm nay: mức tối đa, hoặc số lượt tự chọn × 3 khi bật custom_searches.

        Tính theo tổng điểm search trong ngày, nên chạy lại trong ngày không search thêm khi đã đạt.
        """
        c = self.state.get(kind)
        max_points = c["max"] if c else self.FALLBACK_SEARCHES[kind] * POINTS_PER_SEARCH
        if not self.s.get("custom_searches"):
            return max_points
        return min(max_points, POINTS_PER_SEARCH * max(0, int(self.s.get(f"{kind}_searches", 0))))

    def searches_needed(self, kind: str):
        """Số lượt search còn thiếu cho 'pc' / 'mobile' theo Points breakdown (3 điểm/lượt); None = không rõ."""
        c = self.state.get(kind)
        if c:
            return max(0, -(-(self.search_goal(kind) - c["progress"]) // POINTS_PER_SEARCH))
        return None

    def _recheck(self, check_page: Page, kind: str):
        """Đọc lại breakdown trên tab desktop để cập nhật dashboard; trả về dict progress/max hoặc None."""
        try:
            self._load(check_page, EARN_URL, "Today's points")
            self._read_breakdown(check_page, self.state)
            self.report()
            return self.state.get(kind)
        except (StopRequested, NotLoggedIn):
            raise
        except Exception as e:
            self.log(f"  không kiểm tra được điểm: {e}")
            return None

    def do_searches(self, page: Page, kind: str, label: str, check_page: Page = None) -> None:
        check_page = check_page or page
        need = self.searches_needed(kind)
        if need is None:
            self.log(f"{label}: không đọc được Points breakdown, thử lại...")
            self._recheck(check_page, kind)
            need = self.searches_needed(kind)
            if need is None:
                need = -(-self.search_goal(kind) // POINTS_PER_SEARCH)
                self.log(f"{label}: vẫn không đọc được, dùng mặc định {need} lượt")
        cur = self.state.get(kind) or {}
        goal = self.search_goal(kind)
        full = goal >= cur.get("max", self.FALLBACK_SEARCHES[kind] * POINTS_PER_SEARCH)
        if not full:
            self.log(f"{label}: mục tiêu tự chọn hôm nay {goal // POINTS_PER_SEARCH} lượt = {goal}/{cur.get('max', '?')} điểm")
        if need <= 0:
            self.log(f"{label}: đã đủ điểm search" if full else f"{label}: đã đạt mục tiêu {goal} điểm")
            return
        # search thêm chỉ khi lấy đủ điểm tối đa; có số lượt tự chọn thì không vượt quá mục tiêu
        count = need + (int(self.s.get("extra_searches", 0)) if full else 0)
        self.log(f"{label}: {count} lượt search (đang {cur.get('progress', '?')}/{cur.get('max', '?')} điểm)")
        last_progress, last_gain_at = cur.get("progress"), 0
        for i in range(count):
            self.check_stop()
            if i and i % self.CHECK_EVERY == 0:  # đọc lại điểm định kỳ
                c = self._recheck(check_page, kind)
                if c:
                    self.log(f"  {label}: {c['progress']}/{c['max']} điểm")
                    if c["progress"] >= min(goal, c["max"]):
                        self.log(f"{label}: đã đủ điểm, dừng sớm" if full else f"{label}: đã đạt mục tiêu {goal} điểm, dừng")
                        return
                    if last_progress is None or c["progress"] > last_progress:
                        last_progress, last_gain_at = c["progress"], i
                    elif i - last_gain_at >= self.STALL_AFTER:
                        self._stall(kind, label, f"sau {i - last_gain_at} lượt liên tiếp", c)
                        return
            self.status(progress=f"{label} {i + 1}/{count}")
            self._search_once(page, f"{label} {i + 1}/{count}")
            self._idle_browse(page, random.uniform(self.s["search_delay_min"], self.s["search_delay_max"]))

    def _search_once(self, page: Page, tag: str) -> None:
        q = self.bank.take(self.name)
        try:
            page.goto(f"https://www.bing.com/search?q={quote_plus(q)}&form=QBLH",
                      wait_until="domcontentloaded", timeout=30000)
            page.mouse.wheel(0, random.randint(200, 1200))
        except Exception as e:
            self.log(f"  lỗi khi tìm '{q}': {e}")
        self.log(f"  [{tag}] {q}")

    # Kết quả tìm kiếm thật (bỏ quảng cáo) trên trang Bing: [{i, cite}] theo thứ tự trên trang
    SERP_RESULT = "#b_results > li.b_algo h2 a[href]"
    _SERP_RESULTS_JS = r"""(sel) => Array.from(document.querySelectorAll(sel)).map((a, i) => {
      const li = a.closest('li');
      const ad = !!(li && (li.closest('.b_ad') || li.querySelector('.b_adSlug, .b_adProvider')));
      const cite = ((li && li.querySelector('cite')) || {}).textContent || '';
      return {i, ad, cite, href: a.href};
    }).filter(r => !r.ad && /^https:\/\//.test(r.href)).slice(0, 6)"""
    # link tải file: không bấm (Edge thật sẽ lưu file vào thư mục Downloads)
    _FILE_LINK = re.compile(r"\.(pdf|zip|rar|7z|exe|msi|dmg|apk|docx?|xlsx?|pptx?)(\b|$)", re.I)
    IDLE_BROWSE_MIN = 6  # giây: thời gian chờ ngắn hơn thì chỉ nghỉ, không lướt

    def _idle_browse(self, page: Page, seconds: float) -> None:
        """Dùng thời gian chờ giữa 2 lượt search để thao tác như người thật: cuộn đọc trang kết quả, đôi khi bấm vào
        một kết quả rồi lướt trang đó. Không đổi tổng thời gian chờ, không liên quan tới điểm."""
        end = self.now() + seconds
        if not self.s.get("search_browse", True) or seconds < self.IDLE_BROWSE_MIN:
            self.sleep(seconds)
            return
        try:
            click = random.random() * 100 < int(self.s.get("search_click_pct", 40))
            # đọc trang kết quả trước; có bấm kết quả thì chỉ đọc khoảng 1/3 thời gian
            self._scroll_for(page, self.now() + seconds * (random.uniform(0.25, 0.4) if click else 1))
            if click and end - self.now() >= self.IDLE_BROWSE_MIN:
                self._open_result(page, end)
        except StopRequested:
            raise
        except Exception as e:
            if "has been closed" in str(e):
                raise
            self.log(f"  lỗi khi lướt kết quả: {e}")
        rest = end - self.now()
        if rest > 0:
            self.sleep(rest)

    def _scroll_for(self, page: Page, until: float) -> None:
        """Cuộn từng nhịp nhỏ, có lúc dừng đọc lâu hơn hoặc cuộn ngược lên, tới thời điểm `until`."""
        while (left := until - self.now()) > 0.5:
            r = random.random()
            dy = -random.randint(150, 400) if r < 0.15 else random.randint(120, 600)
            page.mouse.wheel(0, dy)
            self.sleep(min(left, random.uniform(2.5, 6) if r > 0.85 else random.uniform(0.7, 2.2)))

    def _open_result(self, page: Page, end: float) -> None:
        """Bấm 1 kết quả ở đầu trang (nghiêng về kết quả trên cùng), lướt trang đó tới `end` (trừ ~1 giây)."""
        results = [r for r in page.evaluate(self._SERP_RESULTS_JS, self.SERP_RESULT)
                   if not self._FILE_LINK.search(r.get("cite", "")) and not self._FILE_LINK.search(r.get("href", ""))]
        if not results:
            return
        pick = random.choices(results, weights=[6, 4, 3, 2, 1, 1][:len(results)])[0]
        ctx = page.context
        before = list(ctx.pages)
        link = page.locator(self.SERP_RESULT).nth(pick["i"])
        link.scroll_into_view_if_needed(timeout=5000)
        self.sleep(min(max(0.0, end - self.now()), random.uniform(0.5, 1.5)))
        link.click(timeout=5000, no_wait_after=True)
        self.sleep(min(max(0.0, end - self.now()), 1.5))
        new = [p for p in ctx.pages if p not in before]  # kết quả mở tab mới (target=_blank)
        target = new[-1] if new else page
        try:
            try:
                target.wait_for_load_state("domcontentloaded", timeout=int(max(1.0, min(15.0, end - self.now())) * 1000))
            except PWTimeout:
                pass  # trang chậm: vẫn lướt phần đã tải
            self.log(f"    lướt: {urlparse(target.url).netloc or pick['cite'][:60]}")
            self._scroll_for(target, end - 1)
        finally:
            for p in new:  # đóng tab mở thêm, quay lại tab search
                try:
                    p.close()
                except Exception:
                    pass
            if new:
                try:
                    page.bring_to_front()
                except Exception:
                    pass

    def _stall(self, kind: str, label: str, why: str, c: dict) -> None:
        self.log(f"Lỗi: {label} không được cộng điểm {why} (đứng ở {c['progress']}/{c['max']}), dừng {label}. "
                 "Nguyên nhân thường gặp: bing.com đăng nhập sai tài khoản (bấm Kiểm tra), hoặc Microsoft tạm "
                 "không tính search cho tài khoản này.")
        self.stalled.add(kind)

    @staticmethod
    def new_bing_session(ctx: BrowserContext) -> None:
        """Xóa cookie phiên search của Bing (không đụng cookie đăng nhập).

        Bing gắn loại thiết bị theo phiên: search Mobile trong phiên đã search PC bị tính là PC (+0 khi PC đã đủ).
        """
        ctx.clear_cookies(name=re.compile(r"^(_SS|_EDGE_S|_Rwho)$"), domain=re.compile(r"bing\.com$"))

    VISUAL_MAX_TRIES = 4  # số lần thử Visual Search tối đa mỗi tài khoản mỗi ngày
    VISUAL_MISSION_URL ="https://www.bing.com/?features=vsstreak,vstooltip&form=ML2XES"
    VISUAL_RESULT_MARKERS = ("form=sbi", "iss=sbi", "bcid=", "view=detailv2")

    def _pick_visual_image(self, ctx: BrowserContext, page: Page):
        """Lấy 1 ảnh ngẫu nhiên từ Bing Images (mỗi lần một ảnh khác) để làm Visual Search: (tên, mime, bytes)."""
        for _ in range(3):
            q = random.choice(IMAGE_QUERIES)
            page.goto(f"https://www.bing.com/images/search?q={quote_plus(q)}&form=HDRSC2&first=1",
                      wait_until="domcontentloaded", timeout=30000)
            self.sleep(2, 4)
            srcs = page.evaluate(r"""() => Array.from(document.querySelectorAll('img.mimg, a.iusc img'))
                .map(i => i.currentSrc || i.src).filter(u => /^https:\/\/[a-z0-9.-]*bing\.(com|net)\//.test(u)).slice(0, 20)""")
            random.shuffle(srcs)
            for src in srcs[:5]:
                try:
                    r = ctx.request.get(src, timeout=15000)
                    body = r.body()
                except Exception:
                    continue
                mime = (r.headers.get("content-type") or "").split(";")[0]
                if r.ok and mime in ("image/jpeg", "image/png", "image/webp") and len(body) > 3000:
                    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime]
                    return f"{random.randrange(10**8, 10**9)}.{ext}", mime, body
        return None

    def do_visual_search(self, ctx: BrowserContext, page: Page) -> None:
        """Visual Search: bấm camera trên Bing Images và tải 1 ảnh lên (cách AutoRewarder làm, đã kiểm chứng)."""
        title = "Visual Search"
        row = activity(self.state, "visual search")
        if row and row["progress"] >= row["max"]:
            self.log("Visual Search: hôm nay đã xong")
            return
        # Bing chặn Visual Search ("Unable to process this search") khi một tài khoản thử nhiều lần trong ngày,
        # nên giới hạn số lần thử mỗi ngày (tính cả các lượt chạy trước)
        if visual_tries(self.name) >= self.VISUAL_MAX_TRIES:
            self.log(f"Visual Search: hôm nay đã thử {self.VISUAL_MAX_TRIES} lần không được, để mai thử lại "
                     "(thử nhiều Bing càng chặn)")
            return
        self.status(progress=title)
        self.set_local(title, 0, 1, "lượt")
        for attempt in (1, 2):  # lượt 2 dùng ảnh khác (Bing ghi nhận theo nội dung ảnh)
            image = self._pick_visual_image(ctx, page)
            if not image:
                self.log("cảnh báo: Visual Search: không lấy được ảnh nào từ Bing Images, bỏ qua")
                return
            visual_tries(self.name, add=1)
            if self._visual_upload(ctx, page, *image):
                return
            # Bing hay báo lỗi nhưng Rewards vẫn tính lượt đó: đọc lại trước khi thử ảnh khác,
            # để khỏi tốn thêm một lần thử (thử nhiều Bing càng chặn)
            if self._visual_credited(page):
                self.log("Visual Search: Bing báo lỗi nhưng Rewards vẫn đã ghi nhận")
                self.set_local(title, 1, 1, "lượt")
                return
            if attempt == 1 and visual_tries(self.name) < self.VISUAL_MAX_TRIES:
                self.log("  Visual Search: thử lại với ảnh khác")
                self.sleep(5, 10)
            else:
                break

    def _visual_credited(self, page: Page) -> bool:
        """Points breakdown đã tính Visual Search hôm nay chưa (đọc lại trang Rewards)."""
        try:
            row = activity(self.read_state(page), "visual search")
        except (StopRequested, NotLoggedIn):
            raise
        except Exception:
            return False
        return bool(row and row["progress"] >= row["max"])

    # Thả ảnh vào khung upload như kéo-thả thật (cách AutoRewarder dùng). Đưa ảnh qua ô chọn file thì Bing trả 400.
    _DROP_JS = r"""([b64, name, mime]) => {
      const bin = atob(b64), bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const dt = new DataTransfer();
      dt.items.add(new File([bytes], name, {type: mime}));
      const target = document.querySelector("#sb_sbipane, [class*='sbipane']") || document.body;
      for (const t of ["dragenter", "dragover", "drop"])
        target.dispatchEvent(new DragEvent(t, {bubbles: true, cancelable: true, dataTransfer: dt}));
      return dt.files.length;
    }"""

    def _visual_result(self, ctx: BrowserContext, seconds: float) -> str:
        """URL trang kết quả Visual Search nếu đã tới (tab hiện tại hoặc tab mới), chờ tối đa `seconds`."""
        end = time.time() + seconds
        while True:
            url = next((pg.url for pg in ctx.pages if any(m in pg.url.lower() for m in self.VISUAL_RESULT_MARKERS)), "")
            if url or time.time() >= end:
                return url
            self.sleep(1)

    def _visual_upload(self, ctx: BrowserContext, page: Page, name: str, mime: str, body: bytes) -> bool:
        title = "Visual Search"
        # trang kết quả tự gọi /rewardsapp/reportactivity?...bcid=... khi Rewards ghi nhận lượt tìm bằng ảnh
        reported = []

        def on_response(resp):
            if "/rewardsapp/reportactivity" in resp.url.lower():
                reported.append(resp.status)

        ctx.on("response", on_response)
        try:
            page.goto(self.VISUAL_MISSION_URL, wait_until="domcontentloaded", timeout=30000)  # như nút "Search now"
            self.sleep(1, 3)
            page.goto("https://www.bing.com/images", wait_until="load", timeout=30000)
            self.sleep(2, 4)
            page.locator("#sb_sbi, #sbiarea [role='button'], #sbi_b").first.click(timeout=15000)
            page.locator("#sb_sbipane, [class*='sbipane']").first.wait_for(timeout=15000)
            self.sleep(2, 4)
            page.evaluate(self._DROP_JS, [base64.b64encode(body).decode("ascii"), name, mime])
            result = self._visual_result(ctx, 20)
            if not result:  # dự phòng: ô chọn file (nếu trang có)
                file_input = page.locator("#sb_fileinput, input.fileinput[type='file'], input[type='file'][accept*='image']")
                if file_input.count():
                    file_input.first.set_input_files({"name": name, "mimeType": mime, "buffer": body}, timeout=15000)
                    result = self._visual_result(ctx, 25)
        except StopRequested:
            raise
        except Exception as e:
            self.log(f"Lỗi: Visual Search: không mở được ô tải ảnh của Bing ({e})")
            ctx.remove_listener("response", on_response)
            return False
        if not result:
            ctx.remove_listener("response", on_response)
            unable = page.locator("text=Unable to process this search").count() > 0
            self.log("Lỗi: Visual Search: Bing " + ("báo 'Unable to process this search'" if unable
                                                    else "không trả kết quả sau 45 giây"))
            return False
        self.log(f"  Visual Search: Bing đã tìm bằng ảnh ({result[:90]})")
        self.sleep(4, 8)
        ctx.remove_listener("response", on_response)
        self.log("  Visual Search: trang kết quả đã báo hoạt động cho Rewards" if reported
                 else "  cảnh báo: Visual Search: chưa thấy trang kết quả báo hoạt động cho Rewards")
        for pg in list(ctx.pages):  # đóng tab kết quả mở thêm
            if pg is not page and any(m in pg.url.lower() for m in self.VISUAL_RESULT_MARKERS):
                try:
                    pg.close()
                except Exception:
                    pass
        try:  # trang kết quả có thể còn tự chuyển tiếp thêm một lần
            page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
        try:
            st = self.read_state(page)
        except (StopRequested, NotLoggedIn):
            raise
        except Exception:
            self.sleep(3)
            st = self.read_state(page)
        row = activity(st, "visual search")
        if row and row["progress"] >= row["max"]:
            self.log("Visual Search: đã được Rewards ghi nhận")
            self.set_local(title, 1, 1, "lượt")
        else:
            self.log("cảnh báo: Visual Search đã chạy nhưng Rewards chưa ghi nhận (có thể cập nhật trễ, bấm Làm mới sau)")
        return True

    EDGE_CHECK_EVERY = 10  # phút: bao lâu đọc lại "Edge – Minutes" trên Rewards một lần
    EDGE_GIVE_UP = 20      # phút: "Edge – Minutes" không tăng sau từng này phút thì dừng Browse

    def _edge_minutes(self, ctx: BrowserContext):
        """Dòng "Edge – Minutes" mới nhất trên Rewards (đọc ở tab riêng để không cắt trang đang lướt); None nếu lỗi."""
        tab = ctx.new_page()
        try:
            return activity(self.read_state(tab), "edge")
        except (StopRequested, NotLoggedIn):
            raise
        except Exception as e:
            self.log(f"  không đọc được Edge – Minutes: {e}")
            return None
        finally:
            try:
                tab.close()
            except Exception:
                pass

    def do_browse(self, page: Page, minutes: int) -> None:
        """Lướt web cho "Edge – Minutes", vừa lướt vừa đo xem Rewards có tính phút không.

        Edge tự đo thời gian dùng trình duyệt rồi báo cho Rewards; điều kiện để được tính không công khai. Vì vậy mỗi
        lượt Browse ghi lại phút trước/sau kèm chế độ chạy (ẩn / hiện cửa sổ) để so sánh, và dừng sớm khi đã đủ
        hoặc khi phút không tăng (lướt tiếp cũng vô ích).
        """
        title = "Browse"
        mode = "chạy ẩn" if self.s.get("headless") else "hiện cửa sổ"
        row = activity(self.state, "edge")
        if row is None:
            self.log(f"{title}: tài khoản này không có mục Edge – Minutes trên Rewards, bỏ qua")
            return
        if row["progress"] >= row["max"]:
            self.log(f"{title}: Edge – Minutes hôm nay đã đủ {row['progress']}/{row['max']}, bỏ qua")
            return
        first = best = row["progress"]
        total = minutes * 60
        start = last_gain = self.now()
        next_check = start + self.EDGE_CHECK_EVERY * 60
        self.log(f"{title}: lướt web tối đa {minutes} phút ({mode}), Edge – Minutes đang {first}/{row['max']}")
        self.set_local(title, 0, minutes, "phút")
        blocked: set = set()  # trang không kết nối được (vd mạng chặn bằng DNS) -> bỏ qua trong lượt này

        def pick_site() -> str:
            ok = [u for u in BROWSE_SITES if urlparse(u).netloc not in blocked]
            return random.choice(ok or BROWSE_SITES)

        def measure() -> bool:
            """Đọc lại Edge – Minutes; True = nên dừng (đã đủ hoặc không tăng quá lâu)."""
            nonlocal best, last_gain
            r = self._edge_minutes(page.context)
            if not r:
                return False
            mins = int((self.now() - start) // 60)
            self.log(f"  Edge – Minutes: {first} → {r['progress']}/{r['max']} sau {mins} phút ({mode})")
            if r["progress"] > best:
                best, last_gain = r["progress"], self.now()
            if r["progress"] >= r["max"]:
                self.log(f"{title}: Edge – Minutes đã đủ, dừng")
                return True
            if self.s.get("browse_auto_stop", True) and self.now() - last_gain >= self.EDGE_GIVE_UP * 60:
                self.log(f"cảnh báo: {title}: Edge – Minutes không tăng sau {int((self.now() - last_gain) // 60)} phút "
                         f"({mode}). Edge không tính phút cho lượt này, dừng để khỏi lướt vô ích")
                return True
            return False

        url = pick_site()
        while (elapsed := self.now() - start) < total:
            if self.now() >= next_check:
                next_check = self.now() + self.EDGE_CHECK_EVERY * 60
                if measure():
                    break
            self.check_stop()
            self.status(progress=f"Browse {int(elapsed // 60)}/{minutes} phút")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                for _ in range(random.randint(3, 6)):
                    page.mouse.wheel(0, random.randint(250, 700))
                    self.sleep(4, 12)
                    if self.now() - start >= total:
                        break
                links = page.evaluate(
                    "() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
                    ".filter(h => h.startsWith('http')).slice(0, 200)")
                host = urlparse(page.url).netloc
                same = [h for h in links if urlparse(h).netloc == host and h.split('#')[0] != page.url]
                url = random.choice(same) if same and random.random() < 0.7 else pick_site()
            except StopRequested:
                raise
            except Exception as e:
                if "has been closed" in str(e):  # trình duyệt / tab bị đóng giữa chừng: dừng hẳn, không lặp lỗi
                    self.log(f"Lỗi: trình duyệt đã bị đóng, dừng {title}")
                    raise
                host = urlparse(url).netloc
                if "net::ERR_" in str(e) and host not in blocked:
                    blocked.add(host)
                    self.log(f"  không vào được {host} (mạng chặn hoặc trang lỗi), bỏ qua trang này")
                else:
                    self.log(f"  lỗi browse: {e}")
                url = pick_site()
                self.sleep(2, 4)
            self.set_local(title, min(minutes, int((self.now() - start) // 60)), minutes, "phút")
        else:  # hết thời gian mà chưa dừng sớm: đo lần cuối để nhật ký có số trước/sau
            measure()
        used = min(minutes, int((self.now() - start) // 60))
        self.set_local(title, used, minutes, "phút")
        self.log(f"{title}: xong sau {used} phút ({mode}), Edge – Minutes {first} → {best}/{row['max']}"
                 + ("" if best > first else ". Không tăng: Rewards không tính phút cho lượt này"))

    # ------------------------------------------------------------ entry points
    def _session(self, work, headless: bool, label: str) -> None:
        """Mở trình duyệt, chạy work(ctx, page, own), xử lý lỗi chung."""
        own = []
        try:
            with sync_playwright() as p:
                ctx = self._open(p, headless)
                try:
                    if self.profile.get("mode") != "cdp" and ctx.pages:
                        page = ctx.pages[0]
                    else:
                        page = ctx.new_page()
                        own.append(page)
                    try:
                        work(ctx, page, own)
                    except NotLoggedIn:  # phiên hết hạn: tự đăng nhập lại bằng mật khẩu đã lưu (nếu có) rồi làm lại
                        if not self.auto_login(page):
                            raise
                        work(ctx, page, own)
                finally:
                    self._close(ctx, own)
        except StopRequested:
            self.status(state="Đã dừng", progress="")
            self.log(f"{label}: đã dừng theo yêu cầu")
        except NotLoggedIn:
            self.status(state="Chưa đăng nhập", progress="Bấm Đăng nhập")
            self.log("Chưa đăng nhập Microsoft Rewards cho profile này")
        except ProfileInUse as e:
            self.status(state="Lỗi", progress="Profile đang mở ở cửa sổ khác")
            self.log(f"Lỗi: {e}")
        except Exception as e:
            self.status(state="Lỗi", progress=str(e)[:60])
            self.log(f"Lỗi: {e}")

    # ------------------------------------------------------------ tự đăng nhập lại
    # Microsoft hỏi thêm bước xác minh: bot KHÔNG tự vượt qua, dừng lại để người dùng bấm Đăng nhập và tự làm
    _VERIFY_RE = re.compile(r"verify your identity|enter code|enter the code|approve sign in|approve the request|"
                            r"help us protect|unusual activity|prove you're not a robot|solve the puzzle|"
                            r"security info|we need to verify|check your authenticator", re.I)
    _WRONG_PW_RE = re.compile(r"password is incorrect|incorrect password|that microsoft account doesn't exist|"
                              r"account doesn't exist|account has been locked|account is locked", re.I)
    _SKIP_PROMPTS = ("#acceptButton", "#idSIButton9", "button:has-text('Yes')", "button:has-text('Skip for now')",
                     "a:has-text('Skip for now')", "button:has-text('Not now')", "#iCancel")

    def auto_login(self, page: Page) -> bool:
        """Đăng nhập lại bằng email + mật khẩu đã lưu (mã hóa DPAPI). True nếu xong; không lưu mật khẩu thì False."""
        if self.profile.get("mode") == "cdp":
            return False
        cred = credentials.load(self.name)
        if not cred:
            return False
        self.log("Phiên đăng nhập đã hết hạn, đang tự đăng nhập lại bằng mật khẩu đã lưu")
        self.status(state="Đang đăng nhập", progress="Tự đăng nhập lại")
        try:
            why = self._sign_in(page, *cred)
        except (StopRequested, NotLoggedIn):
            raise
        except Exception as e:  # không ghi chi tiết lỗi Playwright: có thể chứa giá trị đã điền
            why = f"trang đăng nhập không như mong đợi ({type(e).__name__})"
        if why:
            self.log(f"Lỗi: tự đăng nhập không được: {why}. Bấm Đăng nhập để tự đăng nhập")
            return False
        self.log("Đã tự đăng nhập lại")
        return True

    def _sign_in(self, page: Page, email: str, password: str) -> str:
        """Điền form đăng nhập Microsoft. Trả về "" nếu xong, hoặc lý do không xong."""
        page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)
        self.sleep(3, 5)
        if "rewards.bing.com" in urlparse(page.url).netloc:  # trang Rewards chưa đăng nhập: bấm "Sign in"
            self._click(page, "a:has-text('Sign in'), button:has-text('Sign in')", 10000)
            self.sleep(3, 5)
        box = page.locator("input[type=email], input[name=loginfmt]").first
        box.wait_for(state="visible", timeout=20000)
        box.fill(email)
        page.keyboard.press("Enter")
        typed_password = False
        for _ in range(12):
            self.sleep(3, 5)
            host = urlparse(page.url).netloc
            if "rewards.bing.com" in host and page.locator('button[aria-label="View profile"]').count():
                return ""
            text = page.locator("body").inner_text(timeout=10000)
            if self._WRONG_PW_RE.search(text):
                return "Microsoft báo sai email/mật khẩu hoặc tài khoản bị khóa (sửa mật khẩu đã lưu)"
            if self._VERIFY_RE.search(text) or page.locator("#enforcementFrame, iframe[title*='challenge' i]").count():
                return "Microsoft yêu cầu xác minh thêm (mã, Authenticator hoặc CAPTCHA)"
            pw = page.locator("input[type=password]:visible")
            if pw.count() and not typed_password:
                pw.first.fill(password)
                page.keyboard.press("Enter")
                typed_password = True
                continue
            if not pw.count() and not typed_password:  # Microsoft mời dùng mã/passkey trước: chọn dùng mật khẩu
                if self._click(page, "#idA_PWD_SwitchToPassword, a:has-text('Use your password'), "
                                     "button:has-text('Use your password'), span:has-text('Use your password')"):
                    continue
            if "stay signed in" in text.lower() or "skip for now" in text.lower() or "not now" in text.lower():
                for sel in self._SKIP_PROMPTS:  # "Duy trì đăng nhập?" -> Yes; mời tạo passkey -> Skip
                    if self._click(page, sel, 2000):
                        break
                continue
            if "rewards.bing.com" in host:
                break
        try:
            self._load(page, DASHBOARD_URL, "Available points")
            return ""
        except NotLoggedIn:
            return "chưa vào được Rewards sau khi đăng nhập"

    def login(self) -> None:
        if self.profile.get("mode") == "cdp":
            self.log("Profile CDP: hãy đăng nhập trực tiếp trên trình duyệt đang mở của bạn")
            return
        self.status(state="Đang đăng nhập", progress="Đóng cửa sổ khi xong")
        with sync_playwright() as p:
            ctx = self._open(p, headless=False)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(DASHBOARD_URL)
            bing = ctx.new_page()
            bing.goto("https://www.bing.com/")
            page.bring_to_front()
            self.log("Đăng nhập tài khoản Microsoft ở tab Rewards, rồi sang tab bing.com kiểm tra góc phải: "
                     "phải là CÙNG tài khoản (nếu khác thì đăng xuất và đăng nhập lại). Xong thì đóng cửa sổ.")
            # đợi người dùng đóng cửa sổ trình duyệt (process kết thúc) hoặc bấm Dừng
            while not self.stop.is_set() and self._launched.alive():
                self.stop.wait(1)
            self._close(ctx, [])
        self.status(state="Sẵn sàng", progress="")
        self.log("Đã lưu phiên đăng nhập")

    def edge_profile_check(self) -> tuple:
        """(level, "Profile Edge", chi tiết): bot dùng profile Edge nào trong thư mục, có profile lạ nào khác không."""
        d = str(profile_dir(self.profile))
        pinned, all_profiles = edge_launcher.pinned_profile(d), edge_launcher.edge_profiles(d)
        def who(k):
            return f"{k} ({all_profiles[k]})" if all_profiles.get(k) else k

        others = [who(k) for k in sorted(all_profiles) if k != pinned]
        if not others:
            return "ok", "Profile Edge", f"dùng {who(pinned)}"
        # đã ghim nên profile khác trong thư mục (vd Windows tự đăng nhập Edge bằng tài khoản công ty) không ảnh hưởng;
        # chỉ cảnh báo khi profile đang ghim chưa đăng nhập trình duyệt mà profile khác lại có
        if all_profiles.get(pinned) or not any(all_profiles.values()):
            return "ok", "Profile Edge", f"luôn dùng {who(pinned)}, bỏ qua {', '.join(others)}"
        return "warn", "Profile Edge", (f"bot luôn dùng {who(pinned)} (chưa đăng nhập trình duyệt), thư mục còn "
                                        f"{', '.join(others)}. Nếu sai, sửa tên trong {edge_launcher.PIN_FILE} "
                                        "ở thư mục profile")

    def diagnose(self) -> list:
        """Nút Kiểm tra: chạy các bước kiểm tra, KHÔNG search. Trả về [{level, title, detail}]."""
        results = []

        def add(level, title, detail):
            results.append({"level": level, "title": title, "detail": detail})
            self.log(f"[Kiểm tra] {'OK' if level == 'ok' else level.upper()} – {title}: {detail}")

        proxy = security.system_proxy()
        own = self.profile.get("proxy") if self.profile.get("mode") != "cdp" else ""
        if own:
            try:
                add("ok", "Proxy riêng", f"{security.validate_proxy(own)} (bỏ qua proxy hệ thống)")
            except ValueError as e:
                add("fail", "Proxy riêng", str(e))
        elif proxy:
            add("ok" if self.s.get("bypass_proxy", True) else "warn", "Proxy hệ thống",
                f"đang bật ({proxy}); " + ("bot bỏ qua proxy này" if self.s.get("bypass_proxy", True)
                                         else "bot ĐANG đi qua proxy này (bật lại tùy chọn trong Cài đặt)"))
        else:
            add("ok", "Proxy hệ thống", "không có")

        def work(ctx, page, own):
            add("ok", "Mở trình duyệt", "profile không bị chương trình khác giữ")
            if self.profile.get("mode") != "cdp":
                add(*self.edge_profile_check())
            try:
                st = self.read_state(page)
            except NotLoggedIn:
                add("fail", "Đăng nhập rewards.bing.com", "chưa đăng nhập. Bấm Đăng nhập")
                return
            add("ok", "Đăng nhập rewards.bing.com", f"{st['available']:,} điểm, hôm nay +{st.get('today') or 0}")
            pc, mob = st.get("pc"), st.get("mobile")
            if pc and mob:
                add("ok", "Points breakdown", f"PC {pc['progress']}/{pc['max']}, Mobile {mob['progress']}/{mob['max']}")
            else:
                add("warn", "Points breakdown", "không đọc được; bot sẽ dùng số lượt search mặc định")
            n_daily, n_more = len(st["daily"]), len(st["more"])
            add("ok" if n_daily else "warn", "Daily Set / Keep earning",
                f"{n_daily} thẻ Daily Set, {n_more} thẻ Keep earning" if n_daily
                else "không thấy thẻ Daily Set nào (có thể Rewards đổi giao diện)")
            level, detail = self.bing_account_check(page)
            add(level, "Tài khoản trên bing.com", detail)
            m = ctx.new_page()
            own.append(m)
            self._emulate_mobile(ctx, m)
            m.goto("https://www.bing.com/", wait_until="domcontentloaded", timeout=30000)
            self.sleep(3, 4)
            signed = any(c["name"] == "_U" for c in ctx.cookies("https://www.bing.com"))
            prompt = m.locator("a[href*='login.live.com'], #mb_signin").count() > 0
            add("ok" if signed and not prompt else "fail", "bing.com trên giao diện Mobile",
                "đã đăng nhập" if signed and not prompt else "chưa đăng nhập: search Mobile sẽ không được tính")

        self.status(state="Đang kiểm tra", progress="")
        self._session(work, headless=True, label="Kiểm tra")
        if self.profile.get("mode") == "cdp":
            add("ok", "Cổng debug", f"chỉ localhost (cổng {self.profile.get('cdp_port')})")
        if not any(r["title"] == "Mở trình duyệt" for r in results):
            add("fail", "Mở trình duyệt", "không mở được profile (xem dòng lỗi phía trên trong nhật ký)")
        worst = "fail" if any(r["level"] == "fail" for r in results) else                 "warn" if any(r["level"] == "warn" for r in results) else "ok"
        self.status(check=results, check_time=time.strftime("%H:%M %d/%m"),
                    state={"ok": "Sẵn sàng", "warn": "Sẵn sàng", "fail": "Lỗi"}[worst],
                    progress={"ok": "Kiểm tra: tất cả OK", "warn": "Kiểm tra: có cảnh báo",
                              "fail": "Kiểm tra: có lỗi"}[worst])
        return results

    def refresh(self) -> None:
        """Chỉ đọc điểm và trạng thái task, không làm gì."""
        def work(ctx, page, own):
            self.status(state="Đang làm mới", progress="")
            st = self.read_state(page)
            self.status(state="Sẵn sàng", progress="")
            self.log(f"Đã cập nhật: {st['available']} điểm, hôm nay {st['today']}")
        self._session(work, headless=True, label="Làm mới")

    def run(self) -> None:
        def work(ctx, page, own):
            self.status(state="Đang chạy", progress="Khởi động")
            start = self.read_state(page)["available"] or 0
            self.status(start=start)
            self.log(f"Điểm hiện tại: {start}")

            # thứ tự: Daily Set / Keep earning -> Quests -> Visual Search -> search PC -> search Mobile -> Browse
            if self.s.get("do_quests", True):  # Daily Set + Keep earning
                self.do_cards(page)
                self.retry_missed_cards(page)
            if self.s.get("do_quest_tasks", True) and self.state.get("quests"):  # Quests (riêng)
                self.do_quest_tasks(page)
                self.read_state(page)
            wants_search = any(self.s.get(k, d) for k, d in (("do_pc", True), ("do_mobile", True), ("do_visual", True)))
            account_ok = self.bing_account_ok(page) if wants_search else True
            if account_ok:
                if self.s.get("do_visual", True):
                    self.do_visual_search(ctx, page)
                if self.s.get("do_pc", True):
                    self.do_searches(page, "pc", "Search PC")
                if self.s.get("do_mobile", True):
                    self.new_bing_session(ctx)
                    mpage = ctx.new_page()
                    own.append(mpage)
                    self._emulate_mobile(ctx, mpage)
                    self.do_searches(mpage, "mobile", "Search Mobile", check_page=page)
                    mpage.close()
                    own.remove(mpage)
                    self.new_bing_session(ctx)  # browse sau đó lại là PC
            if self.s.get("do_browse", False):
                self.read_state(page)  # số phút Edge mới nhất (có thể đã tăng trong lúc search)
                self.do_browse(page, int(self.s.get("browse_minutes", 30)))

            end = self.read_state(page)["available"] or start
            self.log(f"Xong! {start} -> {end} (+{end - start})")
            if not account_ok:
                self.status(state="Lỗi", progress="bing.com đăng nhập sai tài khoản")
            elif self.stalled:
                names = ", ".join({"pc": "PC", "mobile": "Mobile"}[k] for k in sorted(self.stalled))
                self.status(state="Lỗi", progress=f"+{end - start} · Search {names} không được cộng điểm")
            else:
                self.status(state="Hoàn thành", progress=f"+{end - start}")
        self._session(work, bool(self.s.get("headless")), label="Chạy")
