"""Mở giao diện web trong Edge ẩn với API giả: không lỗi JS, CSP không chặn app.js, các trang render được."""
import functools
import http.server
import json
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
                     "headless": True, "max_parallel": 3, "history_days": 30, "do_quests": True, "do_pc": True,
                     "do_mobile": True, "do_visual": True, "do_browse": False,
                     "browse_minutes": 30, "bypass_proxy": True, "theme": "light"},
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


def test_pages_render_without_errors(server):
    boot = boot_data()
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
        pg.click(".theme-switch button[data-theme=dark]")
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
        pg.click(".theme-switch button[data-theme=cyberpunk]")  # giao diện Cyberpunk: nền tối + lớp riêng
        # Cyberpunk: icon task là icon nét neon (ẩn ảnh 3D); Sáng / Tối thì ngược lại
        assert pg.evaluate("getComputedStyle(document.querySelector('#meters .tico img')).display") == "none"
        assert pg.evaluate("getComputedStyle(document.querySelector('#meters .tico i')).display") == "block"
        assert pg.evaluate("document.querySelector('#meters .tico i').className") == "ti ti-device-desktop"
        assert pg.evaluate("[document.documentElement.dataset.bsTheme, document.documentElement.dataset.skin]") == ["dark", "cyberpunk"]
        assert pg.evaluate("getComputedStyle(document.body).fontFamily").lstrip('"').startswith("Bahnschrift")
        pg.click(".theme-switch button[data-theme=light]")
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
            pg.click(f".theme-switch button[data-theme={theme}]")
            pg.wait_for_timeout(600)
            assert pg.evaluate("document.querySelector('#office-canvas').width") > 0
        pg.click(".theme-switch button[data-theme=light]")
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
        assert pg.locator("#btn-do-everything").inner_text().strip() == "Do everything"
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
        # bản mới: thanh báo hiện nút tải; sự kiện tải xong đổi sang nút khởi động lại
        pg.evaluate("""(() => { const real = window.pywebview.api;
            window.pywebview.api = new Proxy({}, {get: (_, k) => k === "check_update"
              ? async () => ({ok: true, current: "1.2.0", latest: "1.3.0", newer: true, can_install: true}) : real[k]});
            return checkUpdate(false); })()""")
        pg.wait_for_selector("#update-bar:not([hidden]) #btn-upd-get", timeout=3000)
        assert "1.3.0" in pg.locator("#update-text").inner_text()
        pg.evaluate("window.onEvents([{type: 'update', state: 'ready', version: '1.3.0'}])")
        assert pg.locator("#btn-upd-apply").is_visible()
        pg.click("#update-dismiss")
        assert not pg.locator("#update-bar").is_visible()
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
        pg.click("#profile-table button[data-act=edit]")
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
