"""Mở giao diện web trong Edge ẩn với API giả: không lỗi JS, CSP không chặn app.js, các trang render được."""
import contextlib
import functools
import http.server
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from conftest import FIXTURES

WEB = Path(__file__).resolve().parents[1] / "rewards_bot" / "ui" / "web"
playwright = pytest.importorskip("playwright.sync_api")


def test_app_js_syntax():
    if not shutil.which("node"):
        pytest.skip("không có node")
    for js in ("app.js", "office.js", "i18n.js"):
        r = subprocess.run(["node", "--check", str(WEB / js)], capture_output=True, text=True)
        assert r.returncode == 0, js + ": " + r.stderr


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def boot_data():
    from rewards_bot.core import rewards_page as rp
    items = json.loads((FIXTURES / "rewards_items.json").read_text(encoding="utf-8"))
    st = rp.empty_state()
    rp.parse_page(items["dashboard"], st)
    rp.parse_page(items["earn"], st)
    rp.parse_breakdown(items["breakdown"], st)
    check = [{"level": "ok", "title": "Đăng nhập rewards.bing.com", "detail": "3,417 điểm"},
             {"level": "fail", "title": "Tài khoản trên bing.com", "detail": "<b>sai tài khoản</b>"}]
    return {
        "settings": {"search_delay_min": 8, "search_delay_max": 20, "extra_searches": 2, "browser_channel": "msedge",
                     "search_browse": True, "search_click_pct": 40, "stall_after": 6, "visual_max_tries": 4, "log_keep_days": 14,
                     "headless": True, "max_parallel": 3, "history_days": 30, "do_quests": True, "do_pc": True,
                     "do_mobile": True, "do_visual": True, "do_browse": False,
                     "browse_minutes": 30, "bypass_proxy": True, "theme": "light", "fun_mode": False,
                     "onboarded": True, "risk_ack": "1.2.0"},
        "profiles": [{"name": "acc <img src=x onerror=alert(1)>", "mode": "managed", "cdp_port": 9222, "dir": "a"}],
        "pstate": {"acc <img src=x onerror=alert(1)>": {
            "state": "Sẵn sàng", "points": 3417, "today": 98, "tasks": rp.build_task_rows(st), "stats": rp.stats(st),
            "icons": rp.group_icons(st), "check": check, "check_time": "10:00 20/10",
            "streak": {"stamps": {"progress": 3, "max": 12, "bonus": 1000}, "daily_streak": 11, "streaks": [
                {"title": "Bing Search Streak", "day": 4, "of": 7, "today": "1/1", "today_done": True, "img": ""},
                {"title": "<img src=x onerror=alert(2)>", "day": 0, "of": 7, "today": "0/1", "today_done": False,
                 "img": ""}]}}},
        "history": {"acc <img src=x onerror=alert(1)>": {
            "2026-10-20": {"available": 3517, "pc": 90, "mobile": 60, "offers": 47},
            "2026-10-21": {"available": 3696, "pc": 90, "mobile": 60, "offers": 29}}},
        "running": [],
        "credentials": {"supported": True, "emails": {"acc <img src=x onerror=alert(1)>": "me@example.com"}},
        "goals": {"acc <img src=x onerror=alert(1)>": {"title": "<img src=x onerror=alert(5)>", "points": 6500}},
        "app": {"version": "1.2.0", "frozen": True},
        # ảnh 1x1 PNG
        "avatars": {"acc <img src=x onerror=alert(1)>": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="},
    }


SHOT = None  # đặt đường dẫn để chụp ảnh khi xem giao diện bằng tay

# API giả có trạng thái: lưu cài đặt thật sự (merge), xóa tài khoản thật sự, ghi lại mọi lời gọi vào window.__calls.
# window.__failStart = true thì start() trả lỗi.
STATEFUL_MOCK = """window.__B = %s; window.__calls = [];
window.pywebview = { api: new Proxy({}, { get: (_, k) => async (...a) => {
  window.__calls.push([k, ...a]);
  if (k === 'bootstrap') return window.__B;
  if (k === 'save_settings') { Object.assign(window.__B.settings, a[0]); return {ok: true, settings: window.__B.settings}; }
  if (k === 'delete_profiles') { window.__B.profiles = window.__B.profiles.filter((p) => !a[0].includes(p.name));
    return {ok: true, profiles: window.__B.profiles}; }
  if (k === 'start') return window.__failStart ? {ok: false, error: 'x'} : {ok: true, running: []};
  return {ok: true, running: [], settings: window.__B.settings, profiles: window.__B.profiles}; } }) };
window.addEventListener('load', () => window.dispatchEvent(new Event('pywebviewready')));"""


@contextlib.contextmanager
def app_page(server, boot, viewport=None, init=""):
    """Mở app trong Edge ẩn với API giả có trạng thái; trả (trang, danh sách lỗi JS). Không có Edge thì bỏ qua test."""
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            pytest.skip("không mở được Edge")
        pg = b.new_page(**({"viewport": viewport} if viewport else {}))
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "favicon" not in m.text and "Failed to load resource" not in m.text
              and "AudioContext" not in m.text and errors.append(m.text))
        pg.add_init_script(init + STATEFUL_MOCK % json.dumps(boot))
        pg.goto(server + "/index.html")
        assert poll(pg, "document.documentElement.dataset.fun !== undefined", 10000)  # app.js đã chạy applyFun
        try:
            yield pg, errors
        finally:
            b.close()


def poll(pg, js, timeout_ms=5000):
    """Hỏi lại tới khi biểu thức JS đúng (CSP của app chặn eval nên không dùng wait_for_function nhiều lượt)."""
    for _ in range(timeout_ms // 50):
        if pg.evaluate(js):
            return True
        pg.wait_for_timeout(50)
    return bool(pg.evaluate(js))


def boot_n(n):
    """Dữ liệu mẫu với n tài khoản tên sạch (acc0, acc1...) có cùng dữ liệu fixture."""
    boot = boot_data()
    proto = boot["profiles"][0]
    first = proto["name"]
    names = [f"acc{i}" for i in range(n)]
    boot["profiles"] = [{**proto, "name": nm, "dir": f"d{i}"} for i, nm in enumerate(names)]
    boot["pstate"] = {nm: json.loads(json.dumps(boot["pstate"][first])) for nm in names}
    boot["history"] = {nm: boot["history"][first] for nm in names}
    boot["avatars"], boot["goals"], boot["credentials"] = {}, {}, {"supported": True, "emails": {}}
    return boot


def open_row_action(pg, act):
    """Mở menu ba chấm của dòng tài khoản đầu tiên rồi chọn một thao tác."""
    pg.click("#profile-table button[data-bs-toggle=dropdown]")
    pg.click(f"#profile-table button[data-act={act}]")


def test_pages_render_without_errors(server):
    boot = boot_data()
    boot["settings"]["fun_mode"] = True  # Văn phòng, Cyberpunk, icon 3D, thẻ đóng dấu chỉ có ở chế độ vui
    mock = ("window.__B = " + json.dumps(boot) + ";"
            "window.pywebview = { api: new Proxy({}, { get: (_, k) => async () => k === 'bootstrap' ? window.__B"
            " : {ok: true, running: [], settings: window.__B.settings, profiles: window.__B.profiles} }) };"
            "window.addEventListener('load', () => window.dispatchEvent(new Event('pywebviewready')));")
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            pytest.skip("không mở được Edge")
        pg = b.new_page()
        errors, dialogs = [], []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "favicon" not in m.text and "Failed to load resource" not in m.text
              and "AudioContext" not in m.text  # Edge headless không có thiết bị âm thanh
              and errors.append(m.text))
        pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        pg.add_init_script(mock)
        pg.goto(server + "/index.html")
        pg.wait_for_function("document.querySelectorAll('.chip').length === 1", timeout=10000)
        assert pg.locator("#check-panel, #btn-check").count() == 0  # kết quả kiểm tra chỉ còn ở Nhật ký
        assert pg.locator("#stamps .stamp").count() >= 5
        assert pg.locator("#streak-panel").is_visible()
        assert pg.locator("#stamp-grid .sdot").count() == 12
        assert pg.locator("#stamp-grid .sdot.on").count() == 3
        assert pg.locator("#streak-list .streak-row").count() == 2
        assert pg.locator("#streak-list .streak-row").first.locator(".sday").count() == 7
        assert pg.locator("#streak-list .streak-row").first.locator(".sday.on").count() == 4
        pg.wait_for_function("document.querySelectorAll('#chart-daily .apexcharts-canvas, #chart-balance .apexcharts-canvas').length === 2",
                             timeout=10000)
        assert pg.evaluate("document.documentElement.dataset.bsTheme") == "light"
        pg.evaluate("setTheme('dark')")
        assert pg.evaluate("document.documentElement.dataset.bsTheme") == "dark"
        # icon task là PNG trong vendor/fluent-emoji hoặc SVG riêng trong assets/icons (không lấy ảnh Bing), tải được
        icons = pg.evaluate("Array.from(document.querySelectorAll('#task-groups .trow .tico img, #meters .tico img'),"
                            " (i) => [i.getAttribute('src'), i.complete && i.naturalWidth > 0])")
        assert icons and all(src.startswith(("vendor/fluent-emoji/", "assets/icons/")) and ok for src, ok in icons), icons
        srcs = [src for src, _ in icons]
        assert srcs[:2] == ["vendor/fluent-emoji/pc.png", "assets/icons/mobile.svg"]  # thanh Search PC, Mobile
        assert "assets/icons/visual.svg" in srcs  # Visual Search
        # Task hôm nay bản gọn: không lặp nhóm Tìm kiếm, việc chưa xong lên trước, bật "Ẩn việc đã xong" thì ẩn
        groups = pg.locator("#task-groups .tgroup h3 .gname").all_inner_texts()
        assert "Tìm kiếm" not in groups and groups[:3] == ["Daily Set", "Keep earning", "Quests"], groups
        daily = pg.locator("#task-groups .tgroup").first.locator(".trow")
        assert "done" not in daily.first.get_attribute("class") and "done" in daily.last.get_attribute("class")
        pg.click("#tasks-hide-done")
        assert pg.locator("#task-groups .trow.done").count() == 0
        pg.click("#tasks-hide-done")
        assert pg.locator("#task-groups .trow.done").count() > 0
        pg.evaluate("setTheme('cyberpunk')")  # giao diện Cyberpunk: nền tối + lớp riêng
        # Cyberpunk: icon task là icon nét neon (ẩn ảnh 3D); Sáng / Tối thì ngược lại
        assert pg.evaluate("getComputedStyle(document.querySelector('#meters .tico img')).display") == "none"
        assert pg.evaluate("getComputedStyle(document.querySelector('#meters .tico i')).display") == "block"
        assert pg.evaluate("document.querySelector('#meters .tico i').className") == "ti ti-device-desktop"
        assert pg.evaluate("[document.documentElement.dataset.bsTheme, document.documentElement.dataset.skin]") == ["dark", "cyberpunk"]
        assert pg.evaluate("getComputedStyle(document.body).fontFamily").lstrip('"').startswith("Bahnschrift")
        pg.evaluate("setTheme('light')")
        assert pg.evaluate("document.documentElement.dataset.skin") is None
        if SHOT:
            pg.set_viewport_size({"width": 1320, "height": 1100})
            pg.screenshot(path=SHOT, full_page=True)
        # mục tiêu đổi quà: thanh tiến độ + dự kiến; tính trung bình bỏ ngày hôm nay (chưa hết ngày)
        goal = pg.locator("#hero-goal").inner_text()
        assert "3,417 / 6,500" in goal and "3,083" in goal
        est = pg.evaluate("""goalEstimate(3417, 6500, {"2026-10-19": {today: 100}, "2026-10-20": {today: 300},
                                                       "2026-10-21": {today: 50}}, "2026-10-21")""")
        assert est["left"] == 3083 and est["avg"] == 200 and est["days"] == 16
        assert pg.evaluate("goalEstimate(7000, 6500, {}).left") == 0
        pg.click("#btn-goal")
        assert pg.locator("#goal-dialog").is_visible() and pg.input_value("#gd-points") == "6500"
        pg.click("#goal-dialog .btn-close")
        # số liệu: 4 ô KPI, lịch nhiệt 12 tuần, nguồn điểm; chưa đủ 2 tài khoản thì không hiện "So sánh tài khoản"
        assert pg.locator("#kpis .kpi").count() == 4
        assert pg.locator("#heatmap .hm").count() == 84
        assert not pg.locator("#compare-panel").is_visible()
        pg.wait_for_function("document.querySelector('#chart-sources .apexcharts-canvas')", timeout=5000)
        k = pg.evaluate("""computeKpis({
            "2026-09-14": {today: 100}, "2026-09-24": {today: 500}, "2026-10-13": {today: 999},
            "2026-10-18": {today: 100, pc: 90, pc_max: 90, mobile: 60, mobile_max: 60},
            "2026-10-19": {today: 200, pc: 90, pc_max: 90, mobile: 60, mobile_max: 60},
            "2026-10-20": {today: 300, pc: 90, pc_max: 90, mobile: 60, mobile_max: 60},
            "2026-10-21": {today: 50, pc: 30, pc_max: 90, mobile: 60, mobile_max: 60}}, "2026-10-21")""")
        assert k["avg7"] == 200 and k["avgDays"] == 3  # 7 ngày trước hôm nay: 18, 19, 20 (13/10 quá xa)
        assert k["streak"] == 3  # hôm nay chưa đủ PC: chuỗi tính 18-20
        assert k["thisMonth"] == 1649 and k["lastMonth"] == 100 and k["change"] == 1549
        cells = pg.evaluate("heatCells({'2026-10-20': {today: 100}, '2026-10-21': {today: 25}}, '2026-10-21')")
        assert len(cells) == 84 and cells[-5]["day"] == "2026-10-21" and cells[-5]["level"] == 1  # 21/10/2026 là thứ Tư
        assert cells[-6]["level"] == 4 and cells[-1]["level"] == -1 and cells[0]["level"] is None
        # trang Tài khoản: "Tự dừng" là mục con của Browse (khóa khi Browse tắt), có Quests riêng, nút Làm tất cả, avatar
        pg.evaluate("go('profiles')")
        sub = pg.locator("#task-toggles .toggle-sub input[data-key=browse_auto_stop]")
        assert sub.count() == 1 and sub.is_disabled()  # do_browse đang tắt trong dữ liệu mẫu
        assert pg.locator("#task-toggles input[data-key=do_quest_tasks]").count() == 1
        assert pg.locator("#btn-do-everything").is_visible()
        assert pg.locator("#profile-table .avatar.has-img").count() == 1
        pg.evaluate("go('dashboard')")
        assert pg.locator("#hero-avatar.has-img").count() == 1
        # thanh bên thu gọn: còn icon, tên trang thành tooltip; mở rộng lại như cũ
        pg.click("#side-toggle")
        assert pg.evaluate("document.documentElement.classList.contains('side-collapsed')")
        assert pg.evaluate("document.querySelector('.side').getBoundingClientRect().width") < 90
        assert pg.locator("#nav [data-page=office]").get_attribute("title") == "Văn phòng"
        assert pg.locator("#nav [data-page=office] .nav-link-icon").is_visible()
        assert not pg.locator("#nav [data-page=office] .nav-link-title").is_visible()
        pg.click("#side-toggle")
        assert not pg.evaluate("document.documentElement.classList.contains('side-collapsed')")
        assert pg.locator("#nav [data-page=office] .nav-link-title").is_visible()
        # Văn phòng: mỗi tài khoản 1 robot có bảng tên; robot làm theo trạng thái thật; nhạc lofi bật / tắt được
        name = pg.evaluate("S.profiles[0].name")
        pg.evaluate("go('office')")
        assert pg.locator("#office-layer .ob-tag").count() == pg.evaluate("S.profiles.length")
        assert pg.evaluate("document.querySelector('#office-canvas').width") > 0
        pg.evaluate(f"window.onEvents([{{type: 'status', name: {json.dumps(name)}, data: {{state: 'Đang chạy', progress: 'Search PC 3/30'}}}}])")
        # CSP của app chặn eval nên không dùng wait_for_function nhiều lượt; tự hỏi lại vài lần
        said = "[...document.querySelectorAll('#office-layer .ob-bubble')].some((b) => !b.hidden && b.textContent === 'Search PC 3/30')"
        for _ in range(30):
            if pg.evaluate(said):
                break
            pg.wait_for_timeout(500)
        assert pg.evaluate(said)
        # góc nhìn isometric: bảng tên nằm trong khung và không trùng nhau, bong bóng nằm trong lớp phủ,
        # bấm đúng chỗ robot (vị trí chiếu) thì mở tổng quan của tài khoản đó
        tags = pg.evaluate("[...document.querySelectorAll('#office-layer .ob-tag')].map((e) => [parseFloat(e.style.left), parseFloat(e.style.top)])")
        assert tags and all(0 <= x <= 100 and 0 <= y <= 100 for x, y in tags), tags
        assert len({tuple(t) for t in tags}) == len(tags), tags
        inside = pg.evaluate("""(() => { const L = document.querySelector('#office-layer').getBoundingClientRect();
            const b = [...document.querySelectorAll('#office-layer .ob-bubble')].find((e) => !e.hidden && e.textContent === 'Search PC 3/30');
            const r = b.getBoundingClientRect();
            return r.left >= L.left - 1 && r.right <= L.right + 1 && r.top >= L.top - 1 && r.bottom <= L.bottom + 1; })()""")
        assert inside
        pg.evaluate("document.querySelector('#office-canvas').scrollIntoView({block: 'center'})")
        pos = pg.evaluate(f"Office._pos({json.dumps(name)})")
        assert pos and pos["x"] > 0 and pos["y"] > 0, pos
        pg.mouse.click(pos["x"], pos["y"])  # bấm robot: mở thẻ thông tin trên đầu robot, không chuyển trang
        assert pg.evaluate("S.page") == "office"
        assert pg.evaluate("Office._card()") == name
        card = pg.locator("#office-layer .ob-card")
        assert card.is_visible()
        assert "me@example.com" in card.inner_text()  # tài khoản liên kết = email đã lưu
        assert card.locator(".oc-list li").count() > 0  # việc đã làm / chưa làm của hôm nay
        cb, lb = card.bounding_box(), pg.locator("#office-layer").bounding_box()
        assert cb["x"] >= lb["x"] - 1 and cb["x"] + cb["width"] <= lb["x"] + lb["width"] + 1, (cb, lb)
        assert cb["y"] + cb["height"] <= pos["y"] or cb["y"] >= pos["y"], (cb, pos)  # nằm trên (hoặc dưới) robot, không che thân
        pg.keyboard.press("Escape")
        assert pg.evaluate("Office._card()") is None and card.is_hidden()
        pg.locator("#office-layer .ob-tag").first.click()  # bấm bảng tên cũng mở thẻ
        assert pg.evaluate("Office._card()") == name
        card.locator("[data-act=open]").click()  # nút Tổng quan trong thẻ
        assert pg.evaluate("S.page") == "dashboard"
        pg.evaluate("go('office')")
        assert pg.evaluate("Office._card()") is None
        # Cyberpunk và giao diện tối: dựng lại sprite + nền, không lỗi JS
        for theme in ("cyberpunk", "dark"):
            pg.evaluate(f"setTheme('{theme}')")
            pg.wait_for_timeout(600)
            assert pg.evaluate("document.querySelector('#office-canvas').width") > 0
        pg.evaluate("setTheme('light')")
        pg.click("#office-music")
        assert "Tắt nhạc lofi" in pg.locator("#office-music").inner_text()
        pg.click("#office-music")
        assert "Bật nhạc lofi" in pg.locator("#office-music").inner_text()
        pg.evaluate(f"window.onEvents([{{type: 'status', name: {json.dumps(name)}, data: {{state: 'Sẵn sàng', progress: ''}}}}, {{type: 'done', name: {json.dumps(name)}}}])")
        pg.evaluate("go('dashboard')")
        # ngôn ngữ: EN dịch cả chữ vẽ sau (đổi trang), số trong câu giữ nguyên; về VI thì trả lại chữ gốc
        pg.click(".lang-switch button[data-set-lang=en]")
        assert pg.evaluate("document.documentElement.lang") == "en"
        assert pg.locator("#nav [data-page=dashboard]").inner_text().strip() == "Overview"
        assert "Today's tasks" in pg.locator("#task-groups").locator("xpath=ancestor::div[contains(concat(' ',@class,' '),' card ')][1]").inner_text()
        pg.evaluate("go('profiles')")
        assert pg.locator("#btn-do-everything").inner_text().strip() == "Run every task once"
        pg.evaluate("go('guide')")
        assert pg.locator("#guide-en").is_visible() and not pg.locator("#guide").is_visible()
        assert pg.evaluate("I18N.tr('Lướt web tối đa 45 phút cho Edge – Minutes, đo số phút mỗi 10 phút')") == \
            "Browses up to 45 minutes for Edge – Minutes, measuring every 10 minutes"
        assert pg.evaluate("I18N.tr('Tokyo Glow · Chưa làm · +10 điểm')") == "Tokyo Glow · Not done · +10 points"
        assert pg.evaluate("I18N.tr('(09-11), trung bình 188/ngày')") == "(09-11), averaging 188/day"
        pg.click(".lang-switch button[data-set-lang=vi]")
        assert pg.evaluate("document.documentElement.lang") == "vi"
        assert pg.locator("#guide").is_visible() and not pg.locator("#guide-en").is_visible()
        assert pg.locator("#nav [data-page=dashboard]").inner_text().strip() == "Tổng quan"
        pg.evaluate("go('dashboard')")
        # lịch sử: mỗi ngày 1 dòng, cột "Còn thiếu" lấy từ missing (bỏ PC/Mobile vì đã có cột riêng)
        pg.evaluate("""(() => { const today = new Date().toISOString().slice(0, 10);
            const h = window.__B.history[Object.keys(window.__B.history)[0]];
            h[today] = {available: 3700, today: 150, pc: 60, pc_max: 90, mobile: 60, mobile_max: 60, offers: 30,
                        missing: [{t: "Search PC", g: "Tìm kiếm", p: 60, m: 90}, {t: "Edge – Minutes", g: "Hoạt động", p: 0, m: 30},
                                  {t: "<img src=x onerror=alert(4)>", g: "Daily Set", p: 0, m: 10}]};
            S.history = window.__B.history; })()""")
        pg.evaluate("go('history')")
        rows = pg.locator("#history-table tbody tr")
        assert rows.count() >= 1
        first = rows.first.inner_text()
        assert "+150" in first and "60/90" in first and "Edge – Minutes 0/30" in first and "Search PC" not in first
        # tài khoản đã lưu mật khẩu: có nhãn "tự đăng nhập"; hộp sửa hiện email, không bao giờ có mật khẩu
        pg.evaluate("go('profiles')")
        assert pg.locator("#profile-table .badge:has-text('tự đăng nhập')").count() == 1
        open_row_action(pg, "edit")
        assert pg.locator("#pd-cred").is_visible() and pg.input_value("#pd-email") == "me@example.com"
        assert pg.input_value("#pd-pass") == "" and pg.locator("#pd-cred-del-wrap").is_visible()
        pg.click("#profile-dialog .btn-close")
        for page in ("profiles", "log", "history", "settings", "guide", "dashboard"):
            pg.evaluate(f"go('{page}')")
            pg.wait_for_timeout(200)
        # nhật ký: mỗi dòng có mức (lỗi / cảnh báo / xong), đếm số lỗi; tên chứa HTML vẫn chỉ là chữ
        pg.evaluate("go('log')")
        assert pg.locator("#logbox .log-empty").is_visible()  # chưa có dòng nào: ô trống có hướng dẫn
        pg.evaluate("window.onEvents(" + json.dumps([
            {"type": "log", "name": "acc <img src=x onerror=alert(3)>", "msg": m, "time": "10:00:00"}
            for m in ("[Kiểm tra] OK – Đăng nhập", "[Kiểm tra] FAIL – Tài khoản trên bing.com", "cảnh báo: chậm",
                      "lỗi: không mở được profile", "Daily Set chưa xong", "Search PC 3/30",
                      "Điểm hiện tại: 3417", "  Visual Search: Bing đã tìm bằng ảnh")]) + ")")
        levels = pg.evaluate("Array.from(document.querySelectorAll('#logbox .l'), (l) => l.className.replace('l', '').trim())")
        assert levels == ["ok", "er", "warn", "er", "", "", "", ""], levels
        counts = pg.locator("#log-levels .lvl b").all_inner_texts()
        assert counts == ["8", "2", "1", "1"], counts  # Tất cả / Lỗi / Cảnh báo / Xong
        assert pg.locator("#logbox .lsep").count() == 1  # "Điểm hiện tại" mở đầu 1 lượt chạy -> vạch ngăn
        kinds = pg.evaluate("Array.from(document.querySelectorAll('#logbox .l .lk'), (i) => i.className.split(' ')[1])")
        assert kinds[0] == "ti-stethoscope" and kinds[4] == "ti-cards" and kinds[-1] == "ti-camera", kinds
        pg.click("#log-levels .lvl-er")
        assert pg.locator("#logbox .l").count() == 2 and pg.locator("#logbox .l.er").count() == 2
        pg.click("#log-levels .lvl-all")
        assert pg.locator("#logbox .l").count() == 8
        # hộp thoại thêm tài khoản: nền đặc, ô cổng chỉ hiện ở chế độ gắn vào Edge, nút nằm trong khung
        pg.evaluate("go('profiles')"); pg.click("#btn-add")
        assert pg.locator("#profile-dialog").is_visible()
        assert pg.evaluate("getComputedStyle(document.querySelector('#profile-dialog')).backgroundColor") not in ("rgba(0, 0, 0, 0)", "transparent")
        assert not pg.locator("#pd-port").is_visible()
        pg.click("input[name=mode][value=cdp] + .form-selectgroup-label")
        assert pg.locator("#pd-port").is_visible()
        box, save = pg.locator("#profile-dialog").bounding_box(), pg.locator("#pd-save").bounding_box()
        assert save["x"] + save["width"] <= box["x"] + box["width"] and save["y"] + save["height"] <= box["y"] + box["height"]
        if SHOT:
            pg.screenshot(path=SHOT.replace(".png", "_dialog.png"))
        pg.click("#profile-dialog .btn-close")
        assert not pg.locator("#profile-dialog").is_visible()
        pg.evaluate("go('guide')")
        assert pg.locator("#page-guide .accordion-item").count() >= 5
        pg.click("#page-guide [data-bs-target='#g-fix']")
        pg.wait_for_selector("#g-fix.show", timeout=3000)  # accordion của Tabler/Bootstrap hoạt động
        b.close()
    assert errors == []
    assert dialogs == []  # tên/tiêu đề chứa HTML không được chạy


def settings_home(pg, timeout_ms=3000):
    """Chờ khối cài đặt về lại trang Cài đặt (sự kiện "close" của <dialog> chạy sau một nhịp).
    Không dùng wait_for_function: CSP của app chặn eval nên Playwright không thăm dò được bằng chuỗi JS."""
    for _ in range(timeout_ms // 50):
        if pg.evaluate("document.querySelector('#settings-cards').parentElement.id") == "settings-home":
            return
        pg.wait_for_timeout(50)
    assert pg.evaluate("document.querySelector('#settings-cards').parentElement.id") == "settings-home"


def test_office_many_accounts_layout(server):
    """7 tài khoản: bảng tên / bong bóng không đè nhau, chữ trên tường không bị màn hình hàng sau che, robot không đi chéo qua đồ."""
    boot = boot_data()
    boot["settings"]["fun_mode"] = True  # trang Văn phòng chỉ có ở chế độ vui
    proto = boot["profiles"][0]
    first = proto["name"]
    names = [f"acc{i}" for i in range(7)]
    boot["profiles"] = [{**proto, "name": n, "dir": f"d{i}"} for i, n in enumerate(names)]
    boot["pstate"] = {n: json.loads(json.dumps(boot["pstate"][first])) for n in names}
    boot["history"] = {n: boot["history"][first] for n in names}
    boot["avatars"], boot["goals"], boot["credentials"] = {}, {}, {"supported": True, "emails": {}}
    mock = ("window.__B = " + json.dumps(boot) + ";"
            "window.pywebview = { api: new Proxy({}, { get: (_, k) => async () => k === 'bootstrap' ? window.__B"
            " : {ok: true, running: [], settings: window.__B.settings, profiles: window.__B.profiles} }) };"
            "window.addEventListener('load', () => window.dispatchEvent(new Event('pywebviewready')));")

    def status(pg, name, state, prog=""):
        pg.evaluate(f"window.onEvents([{{type: 'status', name: {json.dumps(name)}, data: {{state: {json.dumps(state)}, progress: {json.dumps(prog)}}}}}])")

    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            pytest.skip("không mở được Edge")
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.add_init_script(mock)
        pg.goto(server + "/index.html")
        pg.wait_for_function("document.querySelectorAll('.chip').length >= 1", timeout=10000)
        pg.evaluate("go('office')")
        # đổi việc giữa lúc đang đi: mọi đoạn đường phải chạy dọc 1 trục sàn (không đi chéo qua đồ đạc)
        status(pg, "acc6", "Đang chạy", "Khởi động")
        pg.wait_for_timeout(1500)
        status(pg, "acc6", "Đang chạy", "Search PC 1/30")
        path = pg.evaluate("Office._path('acc6')")
        assert len(path) >= 3
        for a, c in zip(path, path[1:]):
            assert abs(a["gx"] - c["gx"]) < 1e-6 or abs(a["gy"] - c["gy"]) < 1e-6, path
        status(pg, "acc6", "Sẵn sàng")
        pg.wait_for_timeout(300)
        for n, (s, q) in {"acc0": ("Đang chạy", "Search PC 3/30"), "acc1": ("Đang chạy", "Search Mobile 4/20"),
                          "acc2": ("Đang chạy", "Visual Search"), "acc3": ("Đang chạy", "Browse 5 phút"),
                          "acc4": ("Lỗi", "Lỗi mạng"), "acc5": ("Đang chờ", ""), "acc6": ("Đang chạy", "Quest 1/3")}.items():
            status(pg, n, s, q)
        for _ in range(60):  # chờ robot ngồi vào bàn (đi bộ từ khu nghỉ)
            if not any(pg.evaluate(f"Office._pos('acc{i}').moving") for i in range(7)):
                break
            pg.wait_for_timeout(500)
        pg.wait_for_timeout(500)
        res = pg.evaluate("""(() => {
            const R = (e) => { const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom}; };
            const hit = (a, c, s = 1) => a.l < c.r - s && c.l < a.r - s && a.t < c.b - s && c.t < a.b - s;
            const tags = [...document.querySelectorAll('#office-layer .ob-tag')].map(R);
            const bubs = [...document.querySelectorAll('#office-layer .ob-bubble')].filter((e) => !e.hidden).map(R);
            const out = {tagTag: 0, tagBub: 0, bubBub: 0, wallMon: [], nb: bubs.length};
            tags.forEach((a, i) => tags.forEach((c, j) => { if (i < j && hit(a, c)) out.tagTag++; }));
            tags.forEach((a) => bubs.forEach((c) => { if (hit(a, c)) out.tagBub++; }));
            bubs.forEach((a, i) => bubs.forEach((c, j) => { if (i < j && hit(a, c)) out.bubBub++; }));
            // chữ trên tường là hình bình hành (skewY 2:1): so với khung màn hình các bàn
            const inner = document.querySelector('#office-inner').getBoundingClientRect();
            const mons = Office._screens();
            for (const e of document.querySelectorAll('#office-layer .ow')) {
                const l = inner.left + e.offsetLeft, t = inner.top + e.offsetTop, w = e.offsetWidth, h = e.offsetHeight;
                mons.forEach((m, i) => {
                    const x0 = Math.max(l, m.left), x1 = Math.min(l + w, m.right);
                    if (x1 <= x0) return;
                    const top = (x) => t + (x - l) / 2, lo = Math.min(top(x0), top(x1)), hi = Math.max(top(x0), top(x1)) + h;
                    if (lo < m.bottom && hi > m.top) out.wallMon.push([e.className, i]);
                });
            }
            return out;
        })()""")
        assert res["nb"] >= 3, res
        assert res["tagTag"] == 0 and res["tagBub"] == 0 and res["bubBub"] == 0, res
        assert res["wallMon"] == [], res
        # con mèo: trạng thái hợp lệ, nằm trong sàn, đường đi (nếu đang đi) dọc 1 trục sàn
        cat = pg.evaluate("Office._cat()")
        assert cat["st"] in ("walk", "sit", "groom", "eat", "sleep"), cat
        assert 0 <= cat["gx"] <= cat["GX"] and 0 <= cat["gy"] <= cat["GY"], cat
        pts = [{"gx": cat["gx"], "gy": cat["gy"]}] + cat["path"]
        for a, c in zip(pts, pts[1:]):
            assert abs(a["gx"] - c["gx"]) < 1e-6 or abs(a["gy"] - c["gy"]) < 1e-6, cat
        # nhật ký của robot: tóm tắt từ dữ liệu thật, có bản tiếng Anh cho từng dòng (trừ dòng Search giống nhau 2 thứ tiếng)
        diary = pg.evaluate("Office._diary('acc0')")
        assert diary[0] == "Nhật ký: hôm nay +98 điểm" and any(d.startswith("Search PC 60/90") for d in diary), diary
        en = pg.evaluate("Office._diary('acc0').map((d) => I18N.tr(d))")
        assert all(e for d, e in zip(diary, en) if not d.startswith("Search")), list(zip(diary, en))
        assert en[0] == "Diary: +98 points today", en
        # đúng 1 nút "+" ở chỗ bàn trống, không đè bảng tên nào; bấm vào mở hộp thêm tài khoản
        assert pg.locator("#office-layer .ob-add").count() == 1
        add_hits = pg.evaluate("""(() => {
            const R = (e) => e.getBoundingClientRect(), a = R(document.querySelector('#office-layer .ob-add'));
            return [...document.querySelectorAll('#office-layer .ob-tag')].map(R)
              .filter((c) => a.left < c.right && c.left < a.right && a.top < c.bottom && c.top < a.bottom).length;
        })()""")
        assert add_hits == 0
        pg.click("#office-layer .ob-add")
        assert pg.locator("#profile-dialog").is_visible()
        assert pg.locator("#pd-title").inner_text() == "Thêm tài khoản"
        pg.click("#profile-dialog .btn-close")
        assert not pg.locator("#profile-dialog").is_visible()
        # cài đặt ngay trên trang Văn phòng: mượn khối cài đặt vào hộp thoại, lưu thì đóng và trả khối về trang Cài đặt
        pg.click("#office-settings")
        assert pg.locator("#settings-dialog").is_visible()
        assert pg.locator("#settings-dialog #set-browser").count() == 1
        assert pg.locator("#settings-dialog .settings-help").is_hidden()
        pg.click("#sd-save")
        assert not pg.locator("#settings-dialog").is_visible()
        settings_home(pg)
        pg.click("#office-settings")
        pg.keyboard.press("Escape")  # sự kiện "close" chạy sau một nhịp: chờ khối cài đặt về chỗ cũ
        settings_home(pg)
        pg.evaluate("go('settings')")
        assert pg.locator("#page-settings #set-browser").is_visible()
        b.close()
    assert errors == []


CONTRAST_JS = r"""(sel) => {
  const lum = (c) => { const v = c.map((x) => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); });
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const parse = (s) => { const m = s.match(/[\d.]+/g).map(Number); return { rgb: m.slice(0, 3), a: m.length > 3 ? m[3] : 1 }; };
  const els = Array.from(document.querySelectorAll(sel)).filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
  const out = { n: els.length, min: 99 };
  for (const el of els) {
  // nền thực: lần lượt pha các lớp nền bán trong suốt từ phần tử lên tới tổ tiên đầu tiên có nền đặc
  const layers = [];
  for (let e = el; e; e = e.parentElement) {
    const b = parse(getComputedStyle(e).backgroundColor);
    if (b.a > 0) { layers.push(b); if (b.a >= 1) break; }
  }
  let bg = [255, 255, 255];
  for (const l of layers.reverse()) bg = bg.map((x, i) => l.rgb[i] * l.a + x * (1 - l.a));
  const fg = parse(getComputedStyle(el).color);
  const f = fg.rgb.map((x, i) => x * fg.a + bg[i] * (1 - fg.a));
  const [a, b] = [lum(f), lum(bg)];
  out.min = Math.min(out.min, (Math.max(a, b) + .05) / (Math.min(a, b) + .05));
  }
  return out;
}"""


@pytest.mark.parametrize("fun", [False, True])
def test_neutral_palette_phase1(server, fun):
    """TC-1.1..1.3: bảng màu trung tính, thẻ điểm phẳng, nhật ký không còn 3 chấm, chữ phụ đạt AA ở sáng và tối
    (cả khi tắt và bật chế độ vui: mỗi chế độ có bộ phần tử riêng cho thẻ tiến độ và streak)."""
    boot = boot_data()
    boot["settings"]["fun_mode"] = fun
    mock = ("window.__B = " + json.dumps(boot) + ";"
            "window.pywebview = { api: new Proxy({}, { get: (_, k) => async () => k === 'bootstrap' ? window.__B"
            " : {ok: true, running: [], settings: window.__B.settings, profiles: window.__B.profiles} }) };"
            "window.addEventListener('load', () => window.dispatchEvent(new Event('pywebviewready')));")
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            pytest.skip("không mở được Edge")
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "favicon" not in m.text and "Failed to load resource" not in m.text
              and "AudioContext" not in m.text and errors.append(m.text))
        pg.add_init_script(mock)
        pg.goto(server + "/index.html")
        pg.wait_for_function("document.querySelectorAll('.chip').length === 1", timeout=10000)
        for theme in ("light", "dark"):
            pg.evaluate(f"setTheme('{theme}')")
            assert pg.evaluate("document.documentElement.dataset.bsTheme") == theme
            for page in ("dashboard", "profiles", "log", "history", "settings", "guide", "office"):  # TC-1.1 (office: chỉ khi bật chế độ vui)
                pg.evaluate(f"go('{page}')")
                pg.wait_for_timeout(150)
            # TC-1.2
            pg.evaluate("go('dashboard')")
            assert pg.evaluate("getComputedStyle(document.querySelector('.hero')).backgroundImage") == "none"
            pg.evaluate("go('log')")
            assert pg.locator(".logcard .log-dots").count() == 0
            assert "rewards-bot://" not in pg.locator(".logcard").inner_text()
            assert pg.locator(".logcard .log-title").inner_text().strip() == "Nhật ký hoạt động"
            # TC-1.3: tương phản WCAG >= 4.5 cho MỌI phần tử hiện (chữ), icon >= 3
            plain = (".prow .pts", ".srow .sub")  # chế độ vui tắt: danh sách tiến độ + bảng streak
            stamps = (".stamp .pts", ".streak-row .sub")  # chế độ vui bật: đĩa dấu + thẻ streak
            checks = {"dashboard": (".brand span", ".hero-mini .lbl", ".text-secondary", ".side .nav-link", ".hero-state",
                                    ".kpi-label", ".meter .val") + (stamps if fun else plain),
                      "log": (".log-head .lvl",), "settings": (".text-secondary",)}
            for page, sels in checks.items():
                pg.evaluate(f"go('{page}')")
                pg.wait_for_timeout(150)
                for sel in sels:
                    r = pg.evaluate(f"({CONTRAST_JS})({json.dumps(sel)})")
                    assert r["n"] > 0, (page, sel)
                    assert r["min"] >= 4.5, (theme, sel, r)
            pg.evaluate("go('profiles')")  # .form-hint chỉ có trong hộp sửa tài khoản
            open_row_action(pg, "edit")
            pg.wait_for_selector("#profile-dialog", state="visible"); pg.wait_for_timeout(400)
            r = pg.evaluate(f"({CONTRAST_JS})('#profile-dialog .form-hint')")
            assert r["n"] > 0 and r["min"] >= 4.5, (theme, ".form-hint", r)
            pg.click("#profile-dialog .btn-close")
            pg.wait_for_selector("#profile-dialog", state="hidden")
            pg.evaluate("go('dashboard')")
            r = pg.evaluate(f"({CONTRAST_JS})('.side .nav-link.active .nav-link-icon')")
            assert r["n"] > 0 and r["min"] >= 3.0, (theme, "nav icon", r)
        assert not errors, errors
        b.close()


# ---------------------------------------------------------------- Phase 2, 3, 5: chế độ vui, icon nét, tổng quan gọn, trạng thái


def test_fun_off_default_look(server):
    """TC-2.1, TC-2.2, TC-3.1, TC-5.1: tắt chế độ vui (mặc định) = giao diện gọn, không Văn phòng / Cyberpunk / ảnh 3D."""
    boot = boot_data()
    boot["settings"].update(fun_mode=False, theme="cyberpunk")  # theme đã lưu là cyberpunk
    with app_page(server, boot, {"width": 1400, "height": 1000}) as (pg, errors):
        assert poll(pg, "document.querySelectorAll('.chip').length === 1")
        # TC-2.2: hiện như Tối, không skin, và giá trị đã lưu không bị ghi đè
        assert pg.evaluate("[document.documentElement.dataset.bsTheme, document.documentElement.dataset.skin ?? null]") == ["dark", None]
        assert pg.evaluate("S.settings.theme") == "cyberpunk"
        assert pg.evaluate("document.querySelector('#theme-choice input:checked').value") == "dark"
        # TC-2.1: không có mục Văn phòng, không có nút Cyberpunk (thanh bên và Cài đặt); go('office') về tổng quan
        assert pg.locator("#nav [data-page=office]").is_hidden()
        pg.evaluate("go('office')")
        assert pg.evaluate("S.page") == "dashboard"
        assert pg.locator("#page-dashboard").is_visible() and pg.locator("#page-office").is_hidden()
        # TC-3.1: mọi icon task / thanh tiến độ / streak là icon nét; không có ảnh nào trong tổng quan (hero, chip, hàng task)
        assert pg.evaluate("document.querySelectorAll('#page-dashboard img').length") == 0
        icons = pg.evaluate("Array.from(document.querySelectorAll('#page-dashboard .tico'), (e) => [!!e.querySelector('i.ti'),"
                            " !!e.querySelector('img'), e.querySelector('i').className])")
        assert len(icons) >= 14 and all(i and not im for i, im, _ in icons), icons
        assert not any("ti-point" in c for _, _, c in icons), icons  # không rơi về icon chung chung
        assert pg.locator("#meters .tico i").first.get_attribute("class") == "ti ti-device-desktop"
        assert pg.locator("#hero-coin").inner_html() == "" and pg.locator(".chip .pts").first.inner_html().strip() == "3,417"
        assert pg.locator(".chip .pts").first.inner_text().strip() == "3,417"
        # TC-5.1: "Tiến độ hôm nay": mỗi việc một dòng, bỏ Search PC/Mobile (đã có thanh tiến độ ngay dưới)
        assert pg.locator("#stamp-title").inner_text().strip() == "Tiến độ hôm nay"
        assert pg.locator("#stamps .stamp").count() == 0 and pg.locator("#stamps .prow").count() == 6
        assert pg.locator("#stamps .prow.done").count() == 2
        assert pg.locator("#stamp-count").inner_text().strip() == "2/6 xong"
        assert "Veggie burgers" in pg.locator("#stamps .prow.done").nth(1).inner_text()
        assert "+10 điểm" in pg.locator("#stamps .prow").first.inner_text()
        assert pg.locator("#meters .meter").count() == 2 and pg.locator("#meters .progress").count() == 2
        # streak: một dòng daily streak, một thanh Stamp bonus x/12, mỗi streak một dòng "Ngày x/7" + thanh 7 đoạn, không đĩa sao
        assert pg.locator("#stamp-grid .sdot").count() == 0 and pg.locator("#stamp-grid .progress").count() == 1
        assert pg.locator("#stamp-grid").inner_text().split() == ["Stamp", "bonus", "3/12"]
        assert pg.get_attribute("#stamp-grid", "aria-valuenow") == "3"
        assert "11 ngày" in pg.locator("#daily-streak").inner_text()
        rows = pg.locator("#streak-list .srow")
        assert rows.count() == 2 and "Ngày 4/7" in rows.first.inner_text() and "Ngày 0/7" in rows.nth(1).inner_text()
        assert rows.first.locator(".seg").count() == 7 and rows.first.locator(".seg.on").count() == 4
        assert pg.locator("#streak-list .sday").count() == 0
        # "Độ đều đặn" + "Điểm đến từ đâu" nằm trong mục "Thêm biểu đồ" gập sẵn
        assert pg.locator("#more-charts").is_visible() and pg.locator("#heatmap").is_hidden()
        assert pg.locator("#more-charts-body #heat-col").count() == 1
        pg.click("#more-charts .more-toggle")
        assert poll(pg, "document.querySelector('#heatmap').offsetWidth > 0 && !!document.querySelector('#chart-sources .apexcharts-canvas')", 8000)
        assert pg.locator("#heatmap .hm").count() == 84
        # trang Tài khoản: Chạy là nút chính, các thao tác còn lại nằm trong menu; icon công tắc là icon nét
        pg.evaluate("go('profiles')")
        assert pg.evaluate("document.querySelectorAll('#task-toggles .tico img, #profile-table img').length") == 0
        assert pg.locator("#profile-table button[data-act=run].btn-primary").is_visible()
        assert pg.locator("#profile-table button[data-act=edit]").is_hidden()
        assert pg.locator("#btn-do-everything").inner_text().strip() == "Chạy mọi task một lần"
        assert pg.locator("#page-profiles .page-hint").is_visible()
        # Cài đặt: chỉ còn Sáng / Tối / Theo Windows, và công tắc chế độ vui đang tắt
        pg.evaluate("go('settings')")
        assert pg.locator("#theme-choice label:has(input[value=cyberpunk])").is_hidden()
        assert pg.locator("#theme-choice label:visible").count() == 3
        assert not pg.is_checked("#set-fun-mode")
        assert errors == []


def test_fun_mode_toggle_without_reload(server):
    """TC-2.3, TC-3.2: bật / tắt chế độ vui ở Cài đặt áp ngay (không tải lại trang) và được lưu qua save_settings."""
    boot = boot_data()
    boot["settings"].update(fun_mode=False, theme="cyberpunk")
    with app_page(server, boot, {"width": 1400, "height": 1000}) as (pg, errors):
        assert poll(pg, "document.querySelectorAll('.chip').length === 1")
        pg.evaluate("window.__marker = 42")
        pg.evaluate("go('settings')")
        pg.check("#set-fun-mode")
        assert poll(pg, "document.querySelector('#nav [data-page=office]').offsetWidth > 0")
        assert pg.evaluate("window.__marker") == 42  # không tải lại
        assert pg.evaluate("window.__calls.filter((c) => c[0] === 'save_settings').map((c) => c[1])")[-1] == {"fun_mode": True}
        assert pg.locator("#theme-choice label:has(input[value=cyberpunk])").is_visible()
        # theme đã lưu là cyberpunk nên skin trở lại
        assert pg.evaluate("[document.documentElement.dataset.bsTheme, document.documentElement.dataset.skin]") == ["dark", "cyberpunk"]
        assert pg.evaluate("document.querySelector('#theme-choice input:checked').value") == "cyberpunk"
        # TC-3.2: icon 3D, đồng xu, ngọn lửa và đĩa dấu quay lại như cũ
        pg.evaluate("setTheme('light')")
        pg.evaluate("go('dashboard')")
        assert poll(pg, "[...document.querySelectorAll('#task-groups .trow .tico img, #meters .tico img')].every((i) => i.complete && i.naturalWidth > 0)")  # ảnh mới thêm cần một nhịp để tải
        icons = pg.evaluate("Array.from(document.querySelectorAll('#task-groups .trow .tico img, #meters .tico img'),"
                            " (i) => [i.getAttribute('src'), i.complete && i.naturalWidth > 0])")
        assert icons and all(src.startswith(("vendor/fluent-emoji/", "assets/icons/")) and ok for src, ok in icons), icons
        assert [src for src, _ in icons][:2] == ["vendor/fluent-emoji/pc.png", "assets/icons/mobile.svg"]
        assert pg.locator("#hero-coin img[src='assets/point.svg']").count() == 1
        assert pg.locator(".chip .pts img").count() == 1 and pg.locator("#streak-title img[src='assets/flame.png']").count() == 1
        assert pg.locator("#stamps .stamp").count() >= 5 and pg.locator("#stamp-grid .sdot").count() == 12
        assert pg.locator("#stamp-grid .sdot.on").count() == 3 and pg.locator("#streak-list .streak-row").count() == 2
        assert pg.locator("#stamp-title").inner_text().strip() == "Thẻ đóng dấu hôm nay"
        assert pg.locator("#more-charts").is_hidden() and pg.locator("#heatmap").is_visible()
        assert pg.locator("#nav [data-page=office]").is_visible()
        pg.click("#nav [data-page=office]")
        assert pg.evaluate("S.page") == "office"
        # tắt ngay trên trang Văn phòng (qua hộp Cài đặt): về tổng quan, mọi thứ trở lại bản gọn
        pg.click("#office-settings")
        pg.uncheck("#set-fun-mode")
        assert poll(pg, "S.page === 'dashboard'")
        assert not pg.evaluate("document.querySelector('#settings-dialog').open")  # hộp Cài đặt đóng theo
        settings_home(pg)  # và khối cài đặt đã về trang Cài đặt
        assert pg.locator("#nav [data-page=office]").is_hidden() and pg.evaluate("document.documentElement.dataset.skin ?? null") is None
        assert pg.evaluate("document.querySelectorAll('#page-dashboard img').length") == 0
        assert errors == []


def test_empty_states(server):
    """TC-5.2: chưa có tài khoản: tổng quan, trang Tài khoản, Lịch sử và Nhật ký hiện khối trạng thái có nút chính."""
    boot = boot_n(0)
    with app_page(server, boot) as (pg, errors):
        assert pg.locator("#dash-empty .state-block").is_visible() and pg.locator("#dash-main").is_hidden()
        assert pg.locator("#btn-first-profile.btn-primary").is_visible()
        pg.click("#btn-first-profile")
        assert pg.evaluate("S.page") == "profiles" and pg.locator("#profile-dialog").is_visible()
        pg.click("#profile-dialog .btn-close")
        assert not pg.locator("#profile-dialog").is_visible()
        assert pg.locator("#profile-table .state-block").is_visible()
        pg.click("#btn-empty-add")
        assert pg.locator("#profile-dialog").is_visible()
        pg.click("#profile-dialog .btn-close")
        pg.evaluate("go('history')")
        assert pg.locator("#history-table .state-block").is_visible()
        pg.click("#btn-history-go")
        assert pg.evaluate("S.page") == "profiles"
        pg.evaluate("go('log')")
        assert pg.locator("#logbox .state-block.log-empty").is_visible()
        pg.click("#btn-log-go")
        assert pg.evaluate("S.page") == "profiles"
        assert errors == []


def test_action_error_banner(server):
    """TC-5.3: start() lỗi -> thanh .alert-danger role=alert nằm đó (không tự tắt như toast), đóng được; toast có aria-live."""
    boot = boot_n(1)
    with app_page(server, boot) as (pg, errors):
        assert poll(pg, "document.querySelectorAll('.chip').length === 1")
        assert pg.get_attribute("#toast", "aria-live") == "polite"
        assert pg.locator(".alert-danger").is_hidden()
        pg.evaluate("window.__failStart = true")
        pg.click("#btn-run-one")
        banner = pg.locator("#error-banner.alert-danger")
        assert banner.is_visible() and banner.get_attribute("role") == "alert" and banner.inner_text().strip() == "x"
        pg.wait_for_timeout(3000)  # lâu hơn toast (2,6 giây) mà vẫn còn
        assert banner.is_visible()
        pg.click("#error-dismiss")
        assert banner.is_hidden()
        # thành công thì chỉ có toast, không có thanh lỗi
        pg.evaluate("window.__failStart = false")
        pg.click("#btn-run-one")
        assert pg.locator("#toast").is_visible() and banner.is_hidden()
        assert errors == []


def test_delete_confirm_dialog(server):
    """TC-5.4: Xóa mở hộp xác nhận có style; Hủy / Esc giữ nguyên, Xóa gọi delete_profiles."""
    boot = boot_n(1)
    with app_page(server, boot) as (pg, errors):
        pg.evaluate("go('profiles')")
        dialogs = []
        pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))  # hộp confirm() gốc của trình duyệt không được dùng nữa
        calls = "window.__calls.filter((c) => c[0] === 'delete_profiles').length"
        open_row_action(pg, "del")
        dlg = pg.locator("#confirm-dialog")
        assert dlg.is_visible() and "acc0" in dlg.inner_text() and "Xóa tài khoản?" in dlg.inner_text()
        assert pg.evaluate("document.activeElement.id") == "cd-cancel"  # mặc định rơi vào Hủy
        assert pg.locator("#cd-ok.btn-danger").is_visible()
        pg.click("#cd-cancel")
        assert poll(pg, "!document.querySelector('#confirm-dialog').open")
        assert pg.evaluate(calls) == 0 and pg.locator("#profile-table tbody tr[data-name]").count() == 1
        open_row_action(pg, "del")
        pg.keyboard.press("Escape")  # Esc = hủy
        assert poll(pg, "!document.querySelector('#confirm-dialog').open")
        assert pg.evaluate(calls) == 0 and pg.locator("#profile-table tbody tr[data-name]").count() == 1
        open_row_action(pg, "del")
        pg.click("#cd-ok")
        assert poll(pg, calls + " === 1")
        assert pg.evaluate("window.__calls.filter((c) => c[0] === 'delete_profiles')[0][1]") == ["acc0"]
        assert poll(pg, "document.querySelectorAll('#profile-table tbody tr[data-name]').length === 0")
        assert pg.locator("#profile-table .state-block").is_visible()
        assert dialogs == [] and errors == []


def test_row_menu_keyboard(server):
    """TC-5.5: menu ba chấm mở bằng bàn phím (focus + Enter), mũi tên chọn mục, Esc đóng và trả focus; không bị bảng cắt."""
    boot = boot_n(1)
    with app_page(server, boot, {"width": 1400, "height": 700}) as (pg, errors):
        pg.evaluate("go('profiles')")
        toggle = "#profile-table button[data-bs-toggle=dropdown]"
        menu = pg.locator("#profile-table .dropdown-menu")
        assert menu.is_hidden() and pg.get_attribute(toggle, "aria-label") == "Thêm thao tác"
        pg.focus(toggle)
        pg.keyboard.press("Enter")
        assert menu.is_visible() and pg.get_attribute(toggle, "aria-expanded") == "true"
        assert [t.strip() for t in menu.locator(".dropdown-item").all_inner_texts()] == ["Kiểm tra", "Đăng nhập", "Sửa", "Xóa"]
        # mục cuối không bị khung bảng cuộn / cắt mất: điểm giữa của nó đúng là nó
        assert pg.evaluate("""(() => { const it = document.querySelector('#profile-table .dropdown-item[data-act=del]'), r = it.getBoundingClientRect();
            return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest('.dropdown-item') === it; })()""")
        pg.keyboard.press("ArrowDown")
        assert pg.evaluate("document.activeElement.classList.contains('dropdown-item')")
        pg.keyboard.press("Escape")
        assert menu.is_hidden() and pg.get_attribute(toggle, "aria-expanded") == "false"
        assert pg.evaluate("document.activeElement === document.querySelector('#profile-table button[data-bs-toggle=dropdown]')")
        # đang mở menu mà trạng thái bot đổi: bảng không vẽ lại (menu không biến mất), đóng rồi mới cập nhật
        pg.keyboard.press("Enter")
        pg.evaluate("window.onEvents([{type: 'status', name: 'acc0', data: {state: 'Hoàn thành', progress: 'xong'}}])")
        assert menu.is_visible()
        pg.keyboard.press("Escape")
        assert poll(pg, "document.querySelector('#profile-table tbody').innerText.includes('Hoàn thành')")
        assert errors == []


def test_lofi_follows_fun_mode(server):
    """R1: nhạc lofi chỉ chạy ở chế độ vui. (A) pref officeMusic bật mà fun tắt: bấm đâu cũng không phát. (B) tắt fun thì nhạc dừng,
    pref giữ nguyên nên bật lại fun là phát tiếp ở lần bấm đầu. Tín hiệu: chữ trong #office-now."""
    now = "document.querySelector('#office-now').textContent"
    boot = boot_n(2)
    with app_page(server, boot, init="localStorage.setItem('officeMusic', 'true');") as (pg, errors):  # A
        assert pg.evaluate(now) == "Nhạc đang tắt"
        pg.click("#nav [data-page=profiles]")
        pg.wait_for_timeout(400)
        assert pg.evaluate(now) == "Nhạc đang tắt" and not pg.evaluate("document.querySelector('#office-music').classList.contains('active')")
        assert errors == []
    boot = boot_n(2)
    boot["settings"]["fun_mode"] = True
    with app_page(server, boot) as (pg, errors):  # B
        pg.evaluate("go('office')")
        pg.click("#office-music")
        assert poll(pg, now + ".startsWith('Lofi')")
        pg.evaluate("go('settings')")
        pg.uncheck("#set-fun-mode")
        assert poll(pg, now + " === 'Nhạc đang tắt'")
        assert pg.evaluate("localStorage.getItem('officeMusic')") == "true"  # pref còn
        pg.click("#nav [data-page=profiles]")  # fun tắt: bấm đâu cũng không phát
        pg.wait_for_timeout(300)
        assert pg.evaluate(now) == "Nhạc đang tắt"
        pg.evaluate("go('settings')")
        pg.check("#set-fun-mode")
        pg.click("#nav [data-page=profiles]")  # fun bật lại: lần bấm đầu phát tiếp
        assert poll(pg, now + ".startsWith('Lofi')")
        assert errors == []


def test_sidebar_order_version_and_theme_in_settings(server):
    """TC-4.1..4.3: menu theo thứ tự mới (Văn phòng cuối, chỉ khi bật chế độ vui), chân thanh bên có số phiên bản và không còn
    nút sáng / tối (đổi ở Cài đặt); thu gọn thì nút ngôn ngữ còn một, bấm là đổi VI <-> EN."""
    boot = boot_n(1)
    boot["settings"]["theme"] = "light"
    with app_page(server, boot, init="localStorage.setItem('sideCollapsed', 'true');") as (pg, errors):
        order = pg.evaluate("[...document.querySelectorAll('#nav [data-page]')].map((a) => a.dataset.page)")
        assert order == ["dashboard", "profiles", "history", "log", "settings", "guide", "office"], order
        assert pg.locator(".side .theme-switch").count() == 0
        assert pg.locator("#side-version").inner_text().strip() == "v" + boot["app"]["version"]
        assert pg.locator("#nav [data-page=history]").get_attribute("title") == "Lịch sử"
        seq = []
        for _ in range(3):
            pg.locator(".lang-switch button.active").click()
            seq.append(pg.evaluate("S.settings.language"))
        assert seq == ["en", "vi", "en"], seq
        assert pg.get_attribute(".lang-switch button[data-set-lang=en]", "aria-checked") == "true"
        pg.locator(".lang-switch button.active").click()
        pg.evaluate("go('settings')")
        pg.click("#theme-choice label:has(input[value=dark])")
        assert pg.evaluate("document.documentElement.dataset.bsTheme") == "dark"
        assert pg.evaluate("window.__calls.filter((c) => c[0] === 'save_settings').map((c) => c[1])")[-1] == {"theme": "dark"}
        pg.click("#theme-choice label:has(input[value=light])")
        assert pg.evaluate("document.documentElement.dataset.bsTheme") == "light"
        assert errors == []


def test_settings_groups_validation_history_and_log_search(server):
    """Cài đặt chia nhóm (có 3 cài đặt mới, ô số ngoài khoảng thì báo lỗi, không lưu); Lịch sử có 4 ô tổng kết và chọn
    khoảng ngày; Nhật ký lọc theo từ khóa; dòng streak dùng chung lưới nên cột thanh 7 ngày thẳng hàng."""
    boot = boot_data()
    with app_page(server, boot, viewport={"width": 1320, "height": 900}) as (pg, errors):
        pg.evaluate("go('settings')")
        assert pg.locator("#settings-form .card").count() == 5
        for k in ("stall_after", "visual_max_tries", "log_keep_days", "search_click_pct"):
            assert pg.locator(f"#set-{k}").is_visible(), k
        assert pg.locator("#set-search-browse").is_checked() and pg.locator("#set-bypass-proxy").is_checked()
        pg.fill("#set-stall_after", "99")
        pg.click("#btn-save-settings")
        assert pg.locator("#error-banner").is_visible() and "3 đến 30" in pg.locator("#error-text").inner_text()
        assert pg.evaluate("window.__B.settings.stall_after") == 6  # không lưu giá trị sai
        pg.fill("#set-stall_after", "8"); pg.uncheck("#set-search-browse")
        pg.click("#btn-save-settings")
        assert pg.evaluate("[window.__B.settings.stall_after, window.__B.settings.search_browse]") == [8, False]
        # lịch sử: 4 ô tổng kết; khoảng 7 ngày bỏ các ngày cũ của dữ liệu mẫu
        pg.evaluate("""(() => { const h = S.history[Object.keys(S.history)[0]], today = new Date().toISOString().slice(0, 10);
            h[today] = {today: 120, pc: 90, pc_max: 90, mobile: 60, mobile_max: 60, offers: 10, missing: []}; })()""")
        pg.evaluate("go('history')")
        assert pg.locator("#history-kpis .kpi").count() == 4
        n30 = pg.locator("#history-table tbody tr").count()
        pg.select_option("#history-range", "7")
        assert 1 <= pg.locator("#history-table tbody tr").count() < n30
        assert "1/1" in pg.locator("#history-kpis").inner_text()  # 1 ngày đủ điểm search trên 1 ngày có số liệu
        assert pg.locator("#history-table .hs-bar.full").count() == 2
        # nhật ký: ô tìm lọc theo từ khóa, không khớp thì có khối trạng thái riêng
        pg.evaluate("go('log')")
        pg.evaluate("window.onEvents(" + json.dumps([{"type": "log", "name": "a", "msg": m, "time": "10:00:00"}
                                                     for m in ("Search PC 1/30", "Visual Search: xong", "Daily Set chưa xong")]) + ")")
        pg.fill("#log-search", "visual")
        assert pg.locator("#logbox .l").count() == 1
        pg.fill("#log-search", "khongcodongnao")
        assert pg.locator("#logbox .l").count() == 0 and pg.locator("#logbox .state-block").is_visible()
        pg.fill("#log-search", "")
        assert pg.locator("#logbox .l").count() == 3
        # streak: cột thanh 7 ngày bắt đầu cùng một x ở mọi dòng
        pg.evaluate("go('dashboard')"); pg.wait_for_timeout(300)
        xs = pg.evaluate("Array.from(document.querySelectorAll('#streak-list .srow .segbar'), (e) => Math.round(e.getBoundingClientRect().left))")
        assert len(xs) >= 2 and len(set(xs)) == 1, xs
        assert not errors, errors


def test_accessibility_focus_ring_chart_labels_and_esc(server):
    """TC-9.1..9.3: dùng phím Tab thì phần tử đang focus có viền; mọi [role=img] có aria-label (biểu đồ có câu tóm tắt);
    Esc đóng mọi hộp thoại."""
    boot = boot_data()
    with app_page(server, boot, viewport={"width": 1320, "height": 900}) as (pg, errors):
        assert poll(pg, "document.querySelectorAll('#chart-daily .apexcharts-canvas, #chart-balance .apexcharts-canvas').length === 2", 10000)
        # TC-9.2
        unlabeled = pg.evaluate("[...document.querySelectorAll('[role=img]')]"
                                ".filter((e) => !(e.getAttribute('aria-label') || '').trim()).map((e) => e.id || e.className)")
        assert unlabeled == [], unlabeled
        assert pg.get_attribute("#chart-daily", "role") == "img"
        assert "ngày gần nhất" in pg.get_attribute("#chart-daily", "aria-label")
        assert pg.get_attribute("#chart-balance", "aria-label").startswith("Số điểm trong")
        assert pg.get_attribute(".chip.active", "aria-pressed") == "true"
        # TC-9.1: 12 lần Tab, phần tử nào nhận focus cũng có viền
        pg.locator("body").click(position={"x": 5, "y": 5})
        seen = []
        for _ in range(12):
            pg.keyboard.press("Tab")
            seen.append(pg.evaluate("(() => { const e = document.activeElement; const cs = getComputedStyle(e);"
                                    " return [e.tagName + '.' + e.className, cs.outlineStyle, cs.outlineWidth]; })()"))
        bad = [s for s in seen if s[0].startswith("BODY") or s[1] == "none" or s[2] == "0px"]
        assert not bad, seen
        # TC-9.3
        name = pg.evaluate("S.profiles[0].name")
        for open_js, dlg in ((f"openProfileDialog(S.profiles[0])", "#profile-dialog"),
                             (f"openGoalDialog({json.dumps(name)})", "#goal-dialog"),
                             ("openSettingsDialog()", "#settings-dialog"),
                             ("confirmDialog({title: 'x', text: 'y'})", "#confirm-dialog"),
                             ("Welcome.open(1)", "#welcome-dialog"), ("openLoginHelp(S.profiles[0].name)", "#login-dialog")):
            pg.evaluate(f"void {open_js}")
            assert pg.evaluate(f"document.querySelector('{dlg}').open"), dlg
            pg.keyboard.press("Escape")
            assert poll(pg, f"!document.querySelector('{dlg}').open", 2000), dlg
        assert pg.locator("#settings-home #settings-cards").count() == 1  # Esc cũng trả khối cài đặt về trang
        pg.evaluate("setLanguage('en')")
        assert pg.get_attribute("#chart-daily", "aria-label").startswith("Points per day over the last")
        assert errors == []


VI_CHARS = re.compile("[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)
LEFTOVER_VI_JS = """(() => {
  const out = [], vis = (e) => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const skip = (e) => e.closest('#logbox, [data-no-i18n], script, style, code, pre');
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) {
    const t = n.nodeValue.trim(), e = n.parentElement;
    if (t && e && !skip(e) && vis(e)) out.push(t);
  }
  for (const e of document.querySelectorAll('[title], [placeholder], [aria-label]')) {
    if (skip(e) || !vis(e)) continue;
    for (const a of ['title', 'placeholder', 'aria-label']) { const v = e.getAttribute(a); if (v) out.push(v); }
  }
  return out;
})()"""


def test_english_has_no_vietnamese_left(server):
    """TC-6.1: ở chế độ English, mọi trang và hộp thoại không còn chữ tiếng Việt (trừ nhật ký bot, tên riêng có data-no-i18n)."""
    boot = boot_data()
    boot["settings"]["language"] = "en"
    import datetime as dt
    first = boot["profiles"][0]["name"]
    for k in range(1, 8):  # 7 ngày gần đây: trang Lịch sử hiện đủ thứ trong tuần (T2..T7, CN)
        boot["history"][first][(dt.date.today() - dt.timedelta(days=k)).isoformat()] = {
            "available": 4000 + k, "pc": 90, "mobile": 60, "offers": 30, "today": 180, "pc_max": 90, "mobile_max": 60}
    with app_page(server, boot, viewport={"width": 1400, "height": 1000}) as (pg, errors):
        assert poll(pg, "document.querySelectorAll('.chip').length === 1")
        names = {p["name"] for p in boot["profiles"]}
        left = {}
        def collect(where):
            found = [t for t in pg.evaluate(LEFTOVER_VI_JS) if VI_CHARS.search(t) and t not in names]
            if found:
                left[where] = sorted(set(found))
        for page in ("dashboard", "profiles", "history", "log", "settings", "guide"):
            pg.evaluate(f"go('{page}')")
            pg.wait_for_timeout(250)
            collect(page)
        pg.evaluate("go('dashboard')")
        pg.click("#more-charts .more-toggle")
        pg.wait_for_timeout(400)
        collect("more-charts")
        name = json.dumps(sorted(names)[0])
        for open_js, dlg in (("openProfileDialog(null)", "#profile-dialog"), ("openProfileDialog(S.profiles[0])", "#profile-dialog"),
                             (f"openGoalDialog({name})", "#goal-dialog"), ("openSettingsDialog()", "#settings-dialog"),
                             ("Welcome.open(1)", "#welcome-dialog"), ("Welcome.open(2)", "#welcome-dialog"),
                             ("Welcome.open(3)", "#welcome-dialog"), ("openLoginHelp(S.profiles[0].name)", "#login-dialog")):
            pg.evaluate(f"void {open_js}")
            pg.wait_for_timeout(200)
            collect(open_js)
            pg.evaluate(f"document.querySelector('{dlg}').close()")
        pg.evaluate("go('profiles')")
        pg.locator("#profile-table .btn-more").first.click()
        collect("row-menu")
        assert left == {}, json.dumps(left, ensure_ascii=False, indent=1)
        assert errors == []


def test_welcome_risk_gate_and_login_helper(server):
    """TC-7.1: onboarded=false thì màn hình chào tự mở; "Tiếp tục" ở bước rủi ro bị khóa đến khi tích ô đồng ý; xong thì lưu
    risk_ack + onboarded. TC-7.2: chưa đồng ý thì Chạy mở lại bước rủi ro, không gọi start. TC-7.4: Đăng nhập mở hộp 3 bước,
    nút Kiểm tra gọi start([tên], "check")."""
    boot = boot_n(1)
    boot["settings"].update(onboarded=False, risk_ack="")
    with app_page(server, boot) as (pg, errors):
        assert poll(pg, "document.querySelector('#welcome-dialog').open")
        assert pg.locator("#wd-step").inner_text() == "Bước 1/3"
        pg.click("[data-wd-lang=en]")
        assert pg.evaluate("S.settings.language") == "en" and pg.locator("#wd-next").inner_text().strip() == "Continue"
        pg.click("[data-wd-lang=vi]")
        pg.click("#wd-next")
        assert pg.locator("#wd-step").inner_text() == "Bước 2/3" and pg.locator("#wd-next").is_disabled()
        pg.keyboard.press("Escape")  # đóng giữa chừng: chưa lưu gì
        assert not pg.evaluate("document.querySelector('#welcome-dialog').open")
        assert pg.evaluate("S.settings.risk_ack") == ""
        # TC-7.2
        pg.evaluate("go('profiles')")
        pg.click("#profile-table button[data-act=run]")
        assert pg.evaluate("document.querySelector('#welcome-dialog').open")
        assert pg.locator("#wd-step").inner_text() == "Bước 2/3"
        assert pg.evaluate("window.__calls.filter((c) => c[0] === 'start').length") == 0
        pg.check("#wd-ack")
        pg.click("#wd-next")
        assert pg.evaluate("S.settings.risk_ack") == boot["app"]["version"]
        assert pg.locator("#wd-step").inner_text() == "Bước 3/3"  # chưa xong màn hình chào: còn bước thêm tài khoản
        pg.click("#wd-next")
        assert not pg.evaluate("document.querySelector('#welcome-dialog').open")
        assert pg.evaluate("S.settings.onboarded") is True
        saved = pg.evaluate("window.__calls.filter((c) => c[0] === 'save_settings').map((c) => c[1])")
        assert {"risk_ack": boot["app"]["version"]} in saved and saved[-1] == {"onboarded": True}
        pg.click("#profile-table button[data-act=run]")
        assert pg.evaluate("window.__calls.filter((c) => c[0] === 'start').map((c) => c[2])") == ["run"]
        # TC-7.4
        name = pg.evaluate("S.profiles[0].name")
        pg.locator("#profile-table .btn-more").first.click()
        pg.click("#profile-table .dropdown-item[data-act=login]")
        assert poll(pg, "document.querySelector('#login-dialog').open")
        assert name in pg.locator("#ld-who").inner_text()
        pg.click("#ld-check")
        assert not pg.evaluate("document.querySelector('#login-dialog').open") and pg.evaluate("S.page") == "log"
        assert pg.evaluate("window.__calls.filter((c) => c[0] === 'start').map((c) => [c[1], c[2]])")[-2:] == \
            [[[name], "login"], [[name], "check"]]
        # Cài đặt: mở lại màn hình chào
        pg.evaluate("go('settings')")
        pg.click("#btn-welcome-again")
        assert pg.evaluate("document.querySelector('#welcome-dialog').open") and pg.locator("#wd-step").inner_text() == "Bước 1/3"
        assert errors == []


def test_branding_about_card_and_log_folder(server):
    """TC-8.1..8.3 (giao diện): tên PrixAuto ở tiêu đề, thanh bên và thẻ Giới thiệu; danh sách giấy phép; nút mở thư mục
    nhật ký gọi open_log_folder không kèm tham số; không còn thanh / cài đặt cập nhật."""
    boot = boot_data()
    boot["app"]["data_dir"] = r"C:\PrixAuto\data"
    with app_page(server, boot) as (pg, errors):
        assert poll(pg, "document.querySelectorAll('.chip').length === 1")
        assert pg.title() == "PrixAuto" and pg.locator(".brand strong").inner_text() == "PrixAuto"
        assert pg.locator("#update-bar, #set-check-updates, #btn-check-update").count() == 0
        pg.evaluate("go('settings')")
        card = pg.locator("#about-card")
        assert "PrixAuto" in card.inner_text() and pg.locator("#about-data").inner_text() == r"C:\PrixAuto\data"
        pg.click("#about-card summary")
        lic = pg.locator("#about-card .about-lic ul").inner_text()
        for n in ("Tabler", "Tabler Icons", "ApexCharts", "Fluent Emoji", "Chakra Petch", "Playwright", "pywebview"):
            assert n in lic, n
        pg.click("#btn-open-logs-about")
        pg.evaluate("go('log')")
        pg.click("#btn-open-logs")
        assert pg.evaluate("window.__calls.filter((c) => c[0] === 'open_log_folder')") == [["open_log_folder"], ["open_log_folder"]]
        assert errors == []
