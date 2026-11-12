"""Logic của bot không cần trình duyệt thật: số lượt search, phát hiện đứng điểm, chọn thẻ, nhận diện profile."""
import re
import threading
from pathlib import Path

import pytest

from rewards_bot.core import bot as bot_mod
from rewards_bot.core.bot import RewardsBot
from rewards_bot.core.browser import _uses_dir
from rewards_bot.core.rewards_page import empty_state


class FakeMouse:
    def wheel(self, *a):
        pass


class FakePage:
    def __init__(self):
        self.visits = []
        self.mouse = FakeMouse()

    def goto(self, url, **k):
        self.visits.append(url)


class FakeBank:
    def __init__(self):
        self.n = 0

    def take(self, who):
        self.n += 1
        return f"query {self.n}"


def make_bot(**settings):
    s = {"search_delay_min": 0, "search_delay_max": 0, "extra_searches": 0, **settings}
    logs = []
    bot = RewardsBot({"name": "t", "mode": "managed"}, s, FakeBank(), lambda n, m: logs.append(m),
                     lambda n, d: None, threading.Event())
    bot.sleep = lambda *a: None
    return bot, logs


def test_searches_needed():
    bot, _ = make_bot()
    bot.state = empty_state()
    assert bot.searches_needed("pc") is None
    bot.state["pc"] = {"progress": 60, "max": 90}
    assert bot.searches_needed("pc") == 10
    bot.state["pc"] = {"progress": 89, "max": 90}
    assert bot.searches_needed("pc") == 1
    bot.state["pc"] = {"progress": 90, "max": 90}
    assert bot.searches_needed("pc") == 0


def test_search_stops_when_points_stall():
    bot, logs = make_bot()
    bot.state = empty_state()
    bot.state["mobile"] = {"progress": 24, "max": 60}
    bot._recheck = lambda page, kind: {"progress": 24, "max": 60}  # không bao giờ tăng
    page = FakePage()
    bot.do_searches(page, "mobile", "Search Mobile")
    assert "mobile" in bot.stalled
    assert len(page.visits) == bot.STALL_AFTER  # dừng sau đúng số lượt không được cộng
    assert any("không được cộng điểm" in m for m in logs)


def test_mobile_profile_matches_real_version():
    p = RewardsBot.mobile_profile({"chromium": "155.0.8059.85", "edge": "155.0.4283.62"})
    md = p["userAgentMetadata"]
    assert "Chrome/155.0.0.0" in p["userAgent"] and "EdgA/155.0.0.0" in p["userAgent"]
    assert {b["version"] for b in md["brands"] if b["brand"] != "Not(A:Brand"} == {"155"}
    assert md["fullVersion"] == "155.0.4283.62" and md["bitness"] == "" and md["mobile"]


def test_search_continues_while_points_increase():
    bot, logs = make_bot()
    bot.state = empty_state()
    bot.state["pc"] = {"progress": 60, "max": 90}
    seq = iter([69, 78, 87])  # đọc lại ở lượt 3, 6, 9: điểm vẫn tăng
    bot._recheck = lambda page, kind: {"progress": next(seq), "max": 90}
    page = FakePage()
    bot.do_searches(page, "pc", "Search PC")
    assert not bot.stalled
    assert len(page.visits) == 10  # đủ 10 lượt cần thiết


def test_search_stops_early_when_full():
    bot, logs = make_bot(extra_searches=5)
    bot.state = empty_state()
    bot.state["pc"] = {"progress": 81, "max": 90}
    bot._recheck = lambda page, kind: {"progress": 90, "max": 90}
    page = FakePage()
    bot.do_searches(page, "pc", "Search PC")
    assert any("đã đủ điểm" in m for m in logs)
    assert len(page.visits) == bot.CHECK_EVERY  # dừng ngay lần đọc lại đầu tiên


def test_full_already_does_nothing():
    bot, logs = make_bot()
    bot.state = empty_state()
    bot.state["pc"] = {"progress": 90, "max": 90}
    page = FakePage()
    bot.do_searches(page, "pc", "Search PC")
    assert page.visits == []


def test_custom_searches_stop_at_chosen_count():
    bot, logs = make_bot(custom_searches=True, pc_searches=10, extra_searches=5)
    bot.state = empty_state()
    bot.state["pc"] = {"progress": 12, "max": 90}
    seq = iter([21, 30])
    bot._recheck = lambda page, kind: {"progress": next(seq), "max": 90}
    page = FakePage()
    bot.do_searches(page, "pc", "Search PC")
    assert len(page.visits) == 6  # (10 lượt × 3 - 12) / 3, không cộng lượt search thêm
    assert any("mục tiêu tự chọn hôm nay 10 lượt = 30/90" in m for m in logs)


def test_custom_searches_zero_or_already_reached():
    bot, logs = make_bot(custom_searches=True, mobile_searches=0)
    bot.state = empty_state()
    bot.state["mobile"] = {"progress": 0, "max": 60}
    page = FakePage()
    bot.do_searches(page, "mobile", "Search Mobile")
    assert page.visits == [] and any("đã đạt mục tiêu 0 điểm" in m for m in logs)


def test_custom_searches_above_max_counts_as_full():
    bot, _ = make_bot(custom_searches=True, pc_searches=50, extra_searches=2)
    bot.state = empty_state()
    bot.state["pc"] = {"progress": 84, "max": 90}
    assert bot.search_goal("pc") == 90
    bot._recheck = lambda page, kind: None
    page = FakePage()
    bot.do_searches(page, "pc", "Search PC")
    assert len(page.visits) == 4  # 2 lượt còn thiếu + 2 lượt search thêm như khi không tự chọn


def test_uses_dir_matches_exact_folder_only(tmp_path):
    d = tmp_path / "namanh"
    assert _uses_dir(f'msedge.exe --user-data-dir="{d}" --remote-debugging-pipe', d)
    assert _uses_dir(f"msedge.exe --user-data-dir={d} about:blank", d)
    assert not _uses_dir(f"msedge.exe --user-data-dir={d}_2 about:blank", d)
    assert not _uses_dir("msedge.exe --no-startup-window", d)


def test_log_drops_playwright_call_log():
    bot, logs = make_bot()
    bot.log('  lỗi browse: Page.goto: net::ERR_CONNECTION_REFUSED at https://x.com/\nCall log:\n  - navigating to "x"')
    assert logs == ["  lỗi browse: Page.goto: net::ERR_CONNECTION_REFUSED at https://x.com/"]


def test_browse_progress_goes_into_edge_minutes_row():
    bot, _ = make_bot()
    sent = {}
    bot._status = lambda n, d: sent.update(d)
    bot.state = empty_state()
    bot.state["activity"] = [{"title": "Edge – Minutes", "key": "edge", "progress": 0, "max": 30, "img": ""}]
    bot.set_local("Browse", 6, 30, "phút")
    rows = sent["tasks"]
    assert not any(r["title"] == "Browse" for r in rows)  # không sinh dòng mới
    edge = next(r for r in rows if r["title"] == "Edge – Minutes")
    assert edge["unit"] == "phút" and edge["progress"] == 0 and edge["bot"] == "bot: 6/30 phút"


def test_local_task_without_matching_activity_gets_own_row():
    bot, _ = make_bot()
    sent = {}
    bot._status = lambda n, d: sent.update(d)
    bot.state = empty_state()
    bot.set_local("Browse", 6, 30, "phút")
    assert any(r["title"] == "Browse" and r["group"] == "Task thêm" for r in sent["tasks"])


def edge_row(progress, total=30):
    return {"title": "Edge – Minutes", "key": "edge", "progress": progress, "max": total, "img": ""}


class BrowsePage(FakePage):
    url = "https://www.theverge.com/"
    context = None

    def evaluate(self, js, *a):
        return []


def browse_bot(minutes_seq, **settings):
    """Bot với đồng hồ giả (mỗi lần sleep tiến 30 giây) và Edge – Minutes đọc lần lượt từ minutes_seq."""
    bot, logs = make_bot(**settings)
    clock = [0.0]
    bot.now = lambda: clock[0]
    bot.sleep = lambda *a: clock.__setitem__(0, clock[0] + 30)
    bot.state = empty_state()
    bot.state["activity"] = [edge_row(minutes_seq[0])]
    reads = iter(minutes_seq[1:])
    bot._edge_minutes = lambda ctx: edge_row(next(reads, minutes_seq[-1]))
    return bot, logs, clock


def test_browse_gives_up_when_edge_minutes_do_not_grow():
    bot, logs, clock = browse_bot([0, 0, 0, 0, 0], headless=True)
    bot.do_browse(BrowsePage(), 60)
    assert clock[0] < 60 * 60  # dừng sớm, không lướt hết 60 phút
    assert clock[0] >= bot.EDGE_GIVE_UP * 60
    assert any("không tăng" in m and "chạy ẩn" in m for m in logs)
    assert logs[-1].startswith("Browse: xong sau") and "0 → 0/30" in logs[-1]


def test_browse_stops_when_edge_minutes_full():
    bot, logs, clock = browse_bot([4, 14, 30], headless=False)
    bot.do_browse(BrowsePage(), 60)
    assert any(re.search(r"Edge – Minutes: 4 → 14/30 sau 1\d phút \(hiện cửa sổ\)", m) for m in logs), logs
    assert any("đã đủ" in m for m in logs)
    assert "4 → 30/30" in logs[-1] and clock[0] < 25 * 60


def test_browse_skips_when_done_or_missing():
    bot, logs, _ = browse_bot([30])
    page = BrowsePage()
    bot.do_browse(page, 30)
    assert page.visits == [] and "đã đủ 30/30" in logs[-1]
    bot.state["activity"] = []
    bot.do_browse(page, 30)
    assert page.visits == [] and "không có mục Edge – Minutes" in logs[-1]


def test_visual_tries_count_per_day(tmp_path):
    from rewards_bot.core.bot import visual_tries
    f = tmp_path / "v.json"
    assert visual_tries("a", path=f) == 0
    assert visual_tries("a", add=1, path=f) == 1
    assert visual_tries("a", add=1, path=f) == 2
    assert visual_tries("b", add=1, path=f) == 1 and visual_tries("a", path=f) == 2


def test_visual_search_respects_daily_cap(tmp_path, monkeypatch):
    from rewards_bot.core import bot as botmod
    monkeypatch.setattr(botmod, "VISUAL_TRIES_FILE", tmp_path / "v.json")
    bot, logs = make_bot()
    bot.state = empty_state()
    botmod.visual_tries("t", add=bot.VISUAL_MAX_TRIES)
    bot._pick_visual_image = lambda *a: pytest.fail("không được thử thêm")
    bot.do_visual_search(None, FakePage())
    assert "để mai thử lại" in logs[-1]


@pytest.mark.parametrize("credited, uploads", [(True, 1), (False, 2)])
def test_visual_search_checks_credit_before_retry(tmp_path, monkeypatch, credited, uploads):
    from rewards_bot.core import bot as botmod
    monkeypatch.setattr(botmod, "VISUAL_TRIES_FILE", tmp_path / "v.json")
    bot, logs = make_bot()
    bot.state = empty_state()
    tries = []
    bot._pick_visual_image = lambda *a: ("a.jpg", "image/jpeg", b"x")
    bot._visual_upload = lambda *a: tries.append(1) and False
    st = empty_state()
    st["activity"] = [{"key": "visual search", "progress": 1 if credited else 0, "max": 1}]
    bot.read_state = lambda page: st
    bot.do_visual_search(None, FakePage())
    assert len(tries) == uploads
    assert ("vẫn đã ghi nhận" in logs[-1]) == credited
    assert "thử lại với ảnh khác" not in " ".join(logs) if credited else True


def test_missed_cards_are_retried_once():
    bot, logs = make_bot()
    card = {"title": "Los Angeles Sunny October", "points": 10, "done": False}
    states = iter([{"daily": [card], "more": []}, {"daily": [dict(card, done=True)], "more": []}])
    bot.read_state = lambda page: next(states)
    redone = []
    bot.do_cards = lambda page: redone.append(1)
    bot.retry_missed_cards(FakePage())
    assert redone == [1] and logs[-1] == "Đã ghi nhận đủ các thẻ sau khi làm lại"


def test_browse_stops_when_browser_closed():
    bot, logs = make_bot()
    bot.state = empty_state()
    bot.state["activity"] = [edge_row(0)]

    class ClosedPage:
        url = "about:blank"
        calls = 0

        def goto(self, *a, **k):
            ClosedPage.calls += 1
            raise RuntimeError("Page.goto: Target page, context or browser has been closed")

    import pytest
    with pytest.raises(RuntimeError):
        bot.do_browse(ClosedPage(), 30)
    assert ClosedPage.calls == 1
    assert any("trình duyệt đã bị đóng" in m for m in logs)


def test_free_profile_only_kills_true_orphans(tmp_path, monkeypatch):
    import pytest
    from rewards_bot.core import browser
    d = tmp_path / "acc"
    killed = []
    monkeypatch.setattr(browser.subprocess, "run", lambda args, **k: killed.append(args))
    monkeypatch.setattr(browser, "_browser_processes",
                        lambda: [(11, f'msedge.exe --user-data-dir="{d}" --remote-debugging-port=0', True)])
    with pytest.raises(browser.ProfileInUse):  # bot khác đang chạy -> không đóng
        browser.free_profile(d, lambda m: None)
    assert killed == []
    monkeypatch.setattr(browser, "_browser_processes",
                        lambda: [(12, f'msedge.exe --user-data-dir="{d}" --remote-debugging-port=0', False)])
    browser.free_profile(d, lambda m: None)  # chương trình mở nó đã tắt -> mồ côi -> đóng
    assert killed and "12" in killed[0]


def test_unix_process_listing(monkeypatch):
    from rewards_bot.core import browser

    class R:
        stdout = ("    1     0 /sbin/init\n"
                  "  500     1 /opt/microsoft/msedge/msedge --user-data-dir=/x/a --remote-debugging-port=0\n"
                  "  700   650 /usr/bin/python3 -m rewards_bot\n"
                  "  710   700 /opt/microsoft/msedge/msedge --user-data-dir=/x/b --remote-debugging-port=0\n"
                  "  711   710 /opt/microsoft/msedge/msedge --type=renderer\n"
                  "  800   650 /usr/bin/bash\n")
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **k: R())
    got = {pid: alive for pid, _, alive in browser._unix_browser_processes()}
    assert got == {500: False, 710: True}  # 500 mồ côi (cha là init), 710 có python còn sống; bỏ renderer và bash


def test_load_retries_once_on_timeout():
    from playwright.sync_api import TimeoutError as PWTimeout
    bot, logs = make_bot()

    class SlowPage(FakePage):
        url = "https://rewards.bing.com/earn"

        def goto(self, url, **k):
            super().goto(url)
            if len(self.visits) == 1:
                raise PWTimeout("Page.goto: Timeout 60000ms exceeded.")

        def wait_for_function(self, *a, **k):
            pass

        def locator(self, sel):
            return type("L", (), {"count": lambda self: 0})()

        def evaluate(self, js):
            return ["ok"]

    page = SlowPage()
    assert bot._load(page, "https://rewards.bing.com/earn", "Today's points") == ["ok"]
    assert len(page.visits) == 2 and any("tải chậm, thử lại" in m for m in logs)


class FakeLoginPage:
    """Trang đăng nhập Microsoft giả: rewards (chưa đăng nhập) -> email -> mật khẩu -> bước cuối -> Rewards."""
    TEXT = {"out": "Sign in to Microsoft Rewards", "email": "Sign in", "password": "Enter password",
            "kmsi": "Stay signed in?", "verify": "Verify your identity", "rewards": "Available points"}

    def __init__(self, after_password="kmsi"):
        self.state, self.after_password, self.typed = "out", after_password, []
        page = self

        class Keyboard:
            def press(self, key):
                page.state = {"email": "password", "password": page.after_password}.get(page.state, page.state)

        class Loc:
            def __init__(self, sel):
                self.sel = sel
                self.first = self

            def count(self):
                s = page.state
                return int(("type=email" in self.sel and s == "email") or ("type=password" in self.sel and s == "password")
                           or ("View profile" in self.sel and s == "rewards"))

            def wait_for(self, **k):
                assert self.count()

            def fill(self, v):
                page.typed.append(v)

            def inner_text(self, **k):
                return page.TEXT[page.state]

            def click(self, **k):
                if "Sign in" in self.sel and page.state == "out":
                    page.state = "email"
                elif "#acceptButton" in self.sel and page.state == "kmsi":
                    page.state = "rewards"
                else:
                    raise RuntimeError("không có nút này")

        self.keyboard, self._loc = Keyboard(), Loc

    @property
    def url(self):
        return "https://rewards.bing.com/" if self.state in ("out", "rewards") else "https://login.live.com/"

    def goto(self, url, **k):
        pass

    def locator(self, sel):
        return self._loc(sel)


def login_bot(monkeypatch, cred=("me@example.com", "pw-123")):
    from rewards_bot.core import bot as botmod
    monkeypatch.setattr(botmod.credentials, "load", lambda name: cred)
    bot, logs = make_bot()
    bot._load = lambda page, url, marker: [] if page.state == "rewards" else (_ for _ in ()).throw(botmod.NotLoggedIn())
    return bot, logs


def test_auto_login_fills_form_and_accepts_stay_signed_in(monkeypatch):
    bot, logs = login_bot(monkeypatch)
    page = FakeLoginPage()
    assert bot.auto_login(page) is True
    assert page.typed == ["me@example.com", "pw-123"] and page.state == "rewards"
    assert not any("pw-123" in m for m in logs)  # mật khẩu không bao giờ vào nhật ký


def test_auto_login_stops_at_verification(monkeypatch):
    bot, logs = login_bot(monkeypatch)
    page = FakeLoginPage(after_password="verify")
    assert bot.auto_login(page) is False
    assert page.typed == ["me@example.com", "pw-123"]  # không điền gì thêm, không cố vượt qua
    assert "yêu cầu xác minh thêm" in logs[-1] and "Bấm Đăng nhập" in logs[-1]


def test_auto_login_without_saved_password_does_nothing(monkeypatch):
    bot, logs = login_bot(monkeypatch, cred=None)
    assert bot.auto_login(FakeLoginPage()) is False and logs == []


def test_edge_profile_check_ok_when_pinned_profile_signed_in(tmp_path, monkeypatch):
    import json as _json
    from rewards_bot.core import bot as botmod, edge_launcher as el
    monkeypatch.setattr(botmod, "profile_dir", lambda p: tmp_path)
    info = {"Default": {"user_name": "work@company.com"}, "Profile 1": {"user_name": "me@gmail.com"}}
    (tmp_path / "Local State").write_text(_json.dumps({"profile": {"last_used": "Profile 1", "info_cache": info}}))
    bot, _ = make_bot()
    level, _, detail = bot.edge_profile_check()
    assert level == "ok" and "Profile 1 (me@gmail.com)" in detail and "Default (work@company.com)" in detail
    info["Profile 1"]["user_name"] = ""  # profile đang ghim chưa đăng nhập trình duyệt, profile kia có
    (tmp_path / "Local State").write_text(_json.dumps({"profile": {"last_used": "Profile 1", "info_cache": info}}))
    assert bot.edge_profile_check()[0] == "warn" and (tmp_path / el.PIN_FILE).read_text().strip() == "Profile 1"


def test_run_order_daily_quests_visual_pc_mobile():
    bot, logs = make_bot(do_browse=False)
    order = []
    st = {"available": 100, "daily": [], "more": []}

    class Ctx:
        def new_page(self):
            return type("P", (), {"close": lambda self: None})()

    bot.read_state = lambda page: st
    bot.do_cards = lambda page: order.append("daily")
    bot.retry_missed_cards = lambda page: None
    bot.bing_account_ok = lambda page: True
    bot.do_quest_tasks = lambda page: order.append("quests")
    st["quests"] = [{"title": "Q", "href": "/earn/quest/x", "progress": 0, "max": 2}]
    bot.state = st
    bot.do_visual_search = lambda ctx, page: order.append("visual")
    bot.do_searches = lambda page, kind, label, check_page=None: order.append(kind)
    bot.new_bing_session = lambda ctx: order.append("reset")
    bot._emulate_mobile = lambda ctx, page: None
    bot._session = lambda work, headless, label: work(Ctx(), FakePage(), [])
    bot.run()
    assert [o for o in order if o != "reset"] == ["daily", "quests", "visual", "pc", "mobile"]
    i = order.index("mobile")
    assert order[i - 1] == "reset" and order[i + 1] == "reset"  # vẫn xóa phiên Bing trước và sau Mobile


def test_browse_keeps_going_when_auto_stop_off():
    bot, logs, clock = browse_bot([0, 0, 0, 0, 0, 0, 0], headless=True, browse_auto_stop=False)
    bot.do_browse(BrowsePage(), 45)
    assert clock[0] >= 45 * 60  # lướt đủ 45 phút dù Edge – Minutes không tăng
    assert not any("dừng để khỏi lướt vô ích" in m for m in logs)
    assert "0 → 0/30" in logs[-1]


def test_quest_steps_skip_when_not_recorded():
    bot, logs = make_bot()
    bot.state = empty_state()
    bot.state["quests"] = [{"title": "Halloween", "href": "/earn/quest/h", "progress": 1, "max": 4}]
    opened = []

    class QuestPage(FakePage):
        def evaluate(self, js):  # bước kế tiếp luôn là cùng 1 link (Rewards không ghi nhận)
            return [{"section": "Activities", "tag": "A", "href": "https://www.bing.com/search?q=x", "index": 3,
                     "lines": ["Search for pumpkins"]}]

    bot._open_card = lambda page, card: opened.append(card["title"])
    bot.do_quest_tasks(QuestPage())
    assert opened == ["Search for pumpkins"] * 2  # thử lại 1 lần rồi bỏ qua, không lặp đủ 3 bước
    assert any("không được ghi nhận, bỏ qua" in m for m in logs)


def test_quest_without_pc_step_is_skipped():
    bot, logs = make_bot()
    bot.state = empty_state()
    bot.state["quests"] = [{"title": "App only", "href": "/earn/quest/a", "progress": 0, "max": 3}]

    class AppOnly(FakePage):
        def evaluate(self, js):
            return [{"section": "Activities", "tag": "BUTTON", "href": "", "index": -1, "lines": ["Open the app"]}]

    bot._open_card = lambda page, card: pytest.fail("không được bấm")
    bot.do_quest_tasks(AppOnly())
    assert "không làm được trên máy tính" in logs[-1]


# ---------------------------------------------------------------- lướt kết quả trong lúc chờ lượt search kế
class SerpPage:
    """Trang kết quả Bing giả: có 3 kết quả (1 quảng cáo, 1 file PDF), bấm thì chuyển trang hoặc mở tab mới."""

    def __init__(self, new_tab=False):
        self.wheels, self.clicked, self.closed, self.url = [], [], False, "https://www.bing.com/search?q=x"
        self.new_tab = new_tab
        self.context = type("Ctx", (), {})()
        self.context.pages = [self]
        self.mouse = type("M", (), {"wheel": lambda _, x, y: self.wheels.append(y)})()

    def evaluate(self, js, sel):
        return [{"i": 0, "cite": "https://example.com/report.pdf", "href": "https://www.bing.com/ck/a?1"},
                {"i": 1, "cite": "https://www.example.org › guide", "href": "https://www.bing.com/ck/a?2"}]

    def locator(self, sel):
        page = self

        class Link:
            def nth(self, i):
                self.i = i
                return self

            def scroll_into_view_if_needed(self, **k):
                pass

            def click(self, **k):
                page.clicked.append(self.i)
                if page.new_tab:
                    tab = SerpPage()
                    tab.url = "https://www.example.org/guide"
                    tab.close = lambda: setattr(tab, "closed", True)
                    page.context.pages.append(tab)
                else:
                    page.url = "https://www.example.org/guide"
        return Link()

    def wait_for_load_state(self, *a, **k):
        pass

    def bring_to_front(self):
        pass


def clock_bot(**settings):
    bot, logs = make_bot(search_delay_min=20, search_delay_max=20, **settings)
    t = [0.0]
    bot.now = lambda: t[0]

    def sleep(a, b=None):
        t[0] += a
    bot.sleep = sleep
    return bot, logs, t


def test_idle_browse_clicks_a_result_and_keeps_total_wait():
    bot, logs, t = clock_bot(search_click_pct=100)
    page = SerpPage()
    bot._idle_browse(page, 20)
    assert page.clicked == [1]  # bỏ qua kết quả là file PDF
    assert page.wheels  # có cuộn
    assert t[0] == pytest.approx(20)  # tổng thời gian chờ không đổi
    assert any("lướt: www.example.org" in m for m in logs)


def test_idle_browse_closes_new_tab():
    bot, _, t = clock_bot(search_click_pct=100)
    page = SerpPage(new_tab=True)
    bot._idle_browse(page, 20)
    tab = page.context.pages[-1]
    assert tab is not page and tab.closed and tab.wheels  # lướt trên tab mới rồi đóng
    assert t[0] == pytest.approx(20)


def test_idle_browse_scroll_only_or_off():
    bot, _, t = clock_bot(search_click_pct=0)
    page = SerpPage()
    bot._idle_browse(page, 15)
    assert page.wheels and not page.clicked and t[0] == pytest.approx(15)

    bot, _, t = clock_bot(search_browse=False, search_click_pct=100)
    page = SerpPage()
    bot._idle_browse(page, 15)
    assert not page.wheels and not page.clicked and t[0] == pytest.approx(15)


def test_idle_browse_short_wait_just_sleeps():
    bot, _, t = clock_bot(search_click_pct=100)
    page = SerpPage()
    bot._idle_browse(page, 3)
    assert not page.wheels and t[0] == pytest.approx(3)


# ---------------------------------------------------------------- giới hạn chỉnh được trong Cài đặt
def test_stall_after_setting():
    bot, logs = make_bot(stall_after=3)
    bot.state = empty_state()
    bot.state["pc"] = {"progress": 0, "max": 90}
    bot._recheck = lambda page, kind: {"progress": 0, "max": 90}  # không bao giờ tăng
    page = FakePage()
    bot.do_searches(page, "pc", "Search PC")
    assert "pc" in bot.stalled and len(page.visits) == 3


def test_visual_max_tries_setting():
    bot, _ = make_bot(visual_max_tries=2)
    assert bot.VISUAL_MAX_TRIES == 2 and RewardsBot.VISUAL_MAX_TRIES == 4
    assert make_bot()[0].STALL_AFTER == RewardsBot.STALL_AFTER  # thiếu cài đặt: dùng mặc định


def test_log_keep_days_prunes_old_files(tmp_path, monkeypatch):
    from datetime import date, timedelta
    from rewards_bot.core import runner
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path)
    old = (date.today() - timedelta(days=10)).isoformat()
    new = (date.today() - timedelta(days=2)).isoformat()
    for d in (old, new):
        (tmp_path / f"{d}.log").write_text("x", encoding="utf-8")
    runner.FileLog.prune(14)
    assert (tmp_path / f"{old}.log").exists()
    runner.FileLog.prune(5)
    assert not (tmp_path / f"{old}.log").exists() and (tmp_path / f"{new}.log").exists()
    runner.FileLog.prune("x")  # giá trị hỏng: không xóa gì, không lỗi
    assert (tmp_path / f"{new}.log").exists()


# ---------------------------------------------------------------- check-in qua DAPI
def test_oauth_code_from_redirect():
    url = "https://login.live.com/oauth20_desktop.srf?code=M.abc&state=s1&lc=1033"
    assert bot_mod.oauth_code(url, "s1") == "M.abc"
    assert bot_mod.oauth_code(url, "other") == ""  # sai state: không nhận mã
    assert bot_mod.oauth_code("https://login.live.com/oauth20_desktop.srf?error=access_denied&state=s1", "s1") == ""
    assert bot_mod.oauth_code("https://login.live.com/oauth20_authorize.srf?client_id=x", "s1") is None
    assert bot_mod.oauth_code("https://evil.example/oauth20_desktop.srf?code=x&state=s1", "s1") is None


def test_dapi_country_points_and_offer_ids():
    assert bot_mod.dapi_country({"response": {"profile": {"attributes": {"country": "VN"}}}}) == "vn"
    assert bot_mod.dapi_country({"response": {"profile": {"attributes": {"country": "Vietnam"}}}}) == ""
    assert bot_mod.dapi_country(None) == "" and bot_mod.dapi_country({}) == ""
    assert bot_mod.checkin_points({"response": {"activity": {"p": 5}}}) == 5
    assert bot_mod.checkin_points({"response": {"activity": {"p": "0"}}}) == 0
    assert bot_mod.checkin_points({"response": None}) is None
    data = {"response": {"promotions": [{"name": "a", "attributes": {"offerid": "Gamification_Sapphire_DailyCheckIn"}},
                                        {"name": "b_only"}, {"name": "a", "attributes": {"offerid":
                                                                                        "Gamification_Sapphire_DailyCheckIn"}},
                                        "junk"]}}
    assert bot_mod.dapi_offer_ids(data) == ["Gamification_Sapphire_DailyCheckIn", "b_only"]
    assert bot_mod.dapi_offer_ids(None) == []


def test_checkin_body_matches_app():
    b = bot_mod.checkin_body("vn")
    assert b["type"] == 101 and b["amount"] == 1 and b["country"] == "vn"
    assert b["attributes"] == {"offerid": "Gamification_Sapphire_DailyCheckIn"}
    assert len(b["id"]) == 128 and b["id"] != bot_mod.checkin_body("vn")["id"]  # id ngẫu nhiên mỗi lần


class FakeResp:
    def __init__(self, data, status=200):
        self.data, self.status, self.ok = data, status, 200 <= status < 300

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


class FakeRequest:
    def __init__(self, me, activity):
        self.me, self.activity, self.calls = me, activity, []

    def get(self, url, **k):
        self.calls.append(("GET", url, k))
        return self.me

    def post(self, url, **k):
        self.calls.append(("POST", url, k))
        if isinstance(self.activity, list):  # mỗi lần POST lấy 1 phản hồi theo thứ tự
            return self.activity.pop(0)
        return self.activity


class FakeCtx:
    def __init__(self, me, activity):
        self.request = FakeRequest(me, activity)


ME_VN = {"response": {"profile": {"attributes": {"country": "VN"}},
                      "promotions": [{"name": "Gamification_Sapphire_DailyCheckIn",
                                      "attributes": {"offerid": "Gamification_Sapphire_DailyCheckIn"}}]}}


def app_streak(day, done):
    return {"title": "Bing App Streak", "day": day, "of": 7, "today": "1/1" if done else "0/1", "today_done": done,
            "next": 10}


def checkin_bot(me, activity, before, after=None, **settings):
    """before/after: dòng Bing App Streak trước khi check-in và sau khi đọc lại trang Rewards (None = không có)."""
    bot, logs = make_bot(**settings)
    bot.state = empty_state()
    bot.state["streaks"] = [before] if before else []

    def reread(page):
        bot.state = empty_state()
        bot.state["streaks"] = [after] if after else []
        return bot.state
    bot.read_state = reread
    bot._mobile_token = lambda ctx: "tok"
    bot.do_read_to_earn = lambda ctx: 0
    return bot, logs, FakeCtx(me, activity)


def test_checkin_confirmed_by_bing_app_streak():
    import json as _json
    bot, logs, ctx = checkin_bot(FakeResp(ME_VN), FakeResp({"response": {"activity": {"p": 10}}}),
                                 app_streak(2, False), app_streak(3, True))
    assert bot.do_checkin(ctx, FakePage()) is True
    posts = [c for c in ctx.request.calls if c[0] == "POST"]
    assert len(posts) == 2 and all(u == bot_mod.DAPI_ACTIVITIES_URL for _, u, _ in posts)
    web, app = (_json.loads(k["data"]) for _, _, k in posts)
    assert web["type"] == 101 and web["attributes"] == {"offerid": "Gamification_Sapphire_DailyCheckIn"}
    assert app["type"] == 103 and app["channel"] == "SAAndroid" and app["country"] == "vn"  # check-in app Bing
    k = posts[1][2]
    assert k["headers"]["Authorization"] == "Bearer tok" and k["headers"]["X-Rewards-Country"] == "vn"
    assert k["headers"]["X-Rewards-AppId"] == "SAAndroid" and k["headers"]["X-Rewards-PartnerId"] == "startapp"
    assert "X-Rewards-AppId" not in posts[0][2]["headers"]
    assert any("DAPI app Bing (type 103): +10 điểm" in m for m in logs)
    assert "ngày 2/7, hôm nay chưa check-in (+10 điểm)" in logs[0]
    assert any("DAPI có 1 offer: Gamification_Sapphire_DailyCheckIn" in m for m in logs)
    assert logs[-1] == "Check-in app điện thoại: Bing App Streak đã lên ngày 3/7"
    assert not any("tok" in m for m in logs)  # không lộ token ra nhật ký


def test_checkin_skipped_when_bing_app_streak_done():
    bot, logs, ctx = checkin_bot(FakeResp(ME_VN), FakeResp({}), app_streak(3, True))
    assert bot.do_checkin(ctx, FakePage()) is True
    assert ctx.request.calls == [] and "đã check-in rồi (ngày 3/7)" in logs[-1]


def test_checkin_not_done_when_streak_does_not_move():
    bot, logs, ctx = checkin_bot(FakeResp(ME_VN), FakeResp({"response": {"activity": {"p": 0}}}),
                                 app_streak(2, False), app_streak(2, False))
    assert bot.do_checkin(ctx, FakePage()) is False  # DAPI nhận nhưng streak không tăng: chưa xong
    assert "Bing App Streak vẫn 0/1" in logs[-1]
    assert any("DAPI app Bing (type 103): hôm nay đã check-in rồi" in m for m in logs)


def test_checkin_errors_do_not_crash():
    bot, logs, ctx = checkin_bot(FakeResp(ValueError("not json")), FakeResp({}, status=401), app_streak(2, False))
    assert bot.do_checkin(ctx, FakePage()) is False
    assert any("dùng 'us'" in m for m in logs) and any("HTTP 401" in m for m in logs)
    assert "cả 2 lệnh check-in DAPI đều lỗi" in logs[-1]

    def no_token(ctx):
        raise RuntimeError("không lấy được mã OAuth của app điện thoại")
    bot._mobile_token = no_token
    bot._dapi_tok = None  # bỏ token đã nhớ của lần trước
    assert bot.do_checkin(ctx, FakePage()) is False  # lỗi lấy token: chỉ ghi nhật ký
    assert "không lấy được mã OAuth" in logs[-1]


def test_run_does_checkin_first_and_respects_switch():
    for enabled in (True, False):
        bot, _ = make_bot(do_browse=False, do_checkin=enabled, do_pc=False, do_mobile=False, do_visual=False,
                          do_quest_tasks=False)
        order = []
        bot.read_state = lambda page: {"available": 1}
        bot.do_checkin = lambda ctx, page: order.append("checkin") or True
        bot.do_read_to_earn = lambda ctx: order.append("read") or 0
        bot.do_cards = lambda page: order.append("daily")
        bot.retry_missed_cards = lambda page: None
        bot._session = lambda work, headless, label: work(object(), FakePage(), [])
        bot.run()
        assert order == (["checkin", "read", "daily"] if enabled else ["read", "daily"])
    bot, _ = make_bot(do_browse=False, do_read_earn=False, do_pc=False, do_mobile=False, do_visual=False,
                      do_quest_tasks=False, do_quests=False)
    bot.read_state = lambda page: {"available": 1}
    bot.do_checkin = lambda ctx, page: True
    bot.do_read_to_earn = lambda ctx: pytest.fail("Read to Earn đang tắt")
    bot._session = lambda work, headless, label: work(object(), FakePage(), [])
    bot.run()


def test_run_retries_failed_checkin_at_end():
    bot, logs = make_bot(do_browse=False, do_pc=False, do_mobile=False, do_visual=False, do_quests=False,
                         do_quest_tasks=False)
    results, states = [False, True], []
    bot.read_state = lambda page: {"available": 1}
    bot.do_read_to_earn = lambda ctx: 0
    bot.do_checkin = lambda ctx, page: results.pop(0)
    bot._status = lambda n, d: states.append(d.get("state"))
    bot._session = lambda work, headless, label: work(object(), FakePage(), [])
    bot.run()
    assert results == [] and "Thử check-in app điện thoại lần nữa" in logs and states[-1] == "Hoàn thành"
    results[:] = [False, False]
    bot.run()
    assert states[-1] == "Lỗi"


def test_checkin_only_reads_page_then_checks_in():
    bot, _ = make_bot()
    calls, states = [], []
    bot.read_state = lambda page: calls.append("read")
    bot.do_checkin = lambda ctx, page: calls.append("checkin") or True
    bot._status = lambda n, d: states.append(d.get("state"))
    bot._session = lambda work, headless, label: work(object(), FakePage(), [])
    bot.checkin_only()
    assert calls == ["read", "checkin"] and states[-1] == "Hoàn thành"


# ---------------------------------------------------------------- check-in app Bing (type 103) + Read to Earn
def test_app_checkin_body_and_activity_result():
    b = bot_mod.app_checkin_body("vn")
    assert b["type"] == 103 and b["channel"] == "SAAndroid" and b["attributes"] == {} and b["risk_context"] == {}
    assert len(b["id"]) == 128
    assert bot_mod.activity_body("us", "X")["attributes"] == {"offerid": "X"}
    assert bot_mod.activity_result({"response": {"activity": {"p": "3"}, "balance": 100, "isDuplicate": False}}) \
        == (3, 100, False)
    assert bot_mod.activity_result({"response": {"isDuplicate": True}}) == (None, None, True)
    assert bot_mod.activity_result(None) == (None, None, False)
    assert bot_mod.dapi_balance({"response": {"balance": "250"}}) == 250 and bot_mod.dapi_balance([]) is None


def readearn_me(progress=0, mx=30, complete="False", balance=100):
    return {"response": {"balance": balance, "profile": {"attributes": {"country": "VN"}}, "promotions": [
        {"name": "Gamification_Sapphire_DailyCheckIn", "attributes": {"type": "checkin"}},
        {"name": "ENUS_readarticle3_30points", "attributes": {
            "offerid": "ENUS_readarticle3_30points", "type": "msnreadearn", "complete": complete,
            "progress": str(progress), "max": str(mx)}}]}}


def test_readearn_offer_parsing():
    assert bot_mod.readearn_offer(readearn_me(6)) == {"offerid": "ENUS_readarticle3_30points", "complete": False,
                                                      "progress": 6, "max": 30}
    assert bot_mod.readearn_offer({"response": {"promotions": [{"name": "x", "attributes": {
        "offerid": "Y_readarticle_z", "pointprogress": "3", "pointmax": "30"}}]}})["progress"] == 3
    assert bot_mod.readearn_offer(ME_VN) is None and bot_mod.readearn_offer(None) is None


def read_bot(me, posts):
    bot, logs = make_bot()
    tokens = []
    bot._mobile_token = lambda ctx: tokens.append(1) or "tok"
    return bot, logs, FakeCtx(FakeResp(me), posts), tokens


def act(p, bal, dup=False):
    return FakeResp({"response": {"activity": {"p": p}, "balance": bal, "isDuplicate": dup}})


def test_read_to_earn_reads_until_no_gain():
    import json as _json
    bot, logs, ctx, _ = read_bot(readearn_me(), [act(3, 103), act(3, 106), act(0, 106)])
    assert bot.do_read_to_earn(ctx) == 6
    posts = [c for c in ctx.request.calls if c[0] == "POST"]
    assert len(posts) == 3
    body = _json.loads(posts[0][2]["data"])
    assert body["type"] == 101 and body["attributes"] == {"offerid": "ENUS_readarticle3_30points"}
    assert body["country"] == "vn" and logs[-1] == "Read to Earn: +6 điểm"
    assert any("hết bài để đọc" in m for m in logs)


def test_read_to_earn_stops_on_duplicate_or_flat_balance_and_caps():
    bot, _, ctx, _ = read_bot(readearn_me(), [act(3, 100)])  # điểm báo +3 nhưng số dư không tăng
    assert bot.do_read_to_earn(ctx) == 0
    bot, _, ctx, _ = read_bot(readearn_me(), [act(3, 103, dup=True)])
    assert bot.do_read_to_earn(ctx) == 0
    bot, _, ctx, _ = read_bot(readearn_me(), [act(3, 103 + 3 * i) for i in range(20)])
    assert bot.do_read_to_earn(ctx) == 3 * bot_mod.READ_EARN_MAX  # không vượt quá 10 bài


def test_read_to_earn_skips_when_done_or_missing():
    for me, msg in ((readearn_me(30), "đã xong (30/30)"), (readearn_me(0, complete="True"), "đã xong"),
                    (ME_VN, "không có offer")):
        bot, logs, ctx, _ = read_bot(me, [])
        assert bot.do_read_to_earn(ctx) == 0
        assert not [c for c in ctx.request.calls if c[0] == "POST"] and any(msg in m for m in logs)


def test_read_to_earn_errors_do_not_crash():
    bot, logs, ctx, _ = read_bot(readearn_me(), [act(3, 103), FakeResp({}, status=500)])
    assert bot.do_read_to_earn(ctx) == 3
    assert any("Read to Earn không được: DAPI trả về HTTP 500" in m for m in logs)
    assert not any("tok" in m for m in logs)


def test_dapi_token_reused_within_run():
    bot, _, ctx, tokens = read_bot(readearn_me(30), [])
    clock = [1000.0]
    bot.now = lambda: clock[0]
    bot.do_read_to_earn(ctx)
    bot.do_read_to_earn(ctx)
    assert len(tokens) == 1  # check-in + Read to Earn dùng chung 1 token
    clock[0] += bot.DAPI_TOKEN_TTL + 1
    bot.do_read_to_earn(ctx)
    assert len(tokens) == 2  # hết hạn thì lấy token mới
