"use strict";
// Giao diện Rewards Bot (Tabler + ApexCharts). Mọi dữ liệu đến từ Python (window.pywebview.api) và sự kiện window.onEvents.

const S = { settings: {}, profiles: [], pstate: {}, history: {}, running: new Set(),
            logs: [], unreadErr: 0, selected: null, page: "dashboard" };
const api = () => window.pywebview.api;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => (n === null || n === undefined || n === "" ? "—" : Number(n).toLocaleString("en-US"));
const SERIES = [["pc", "Search PC", "#2a78d6"], ["mobile", "Search Mobile", "#eb6834"], ["offers", "Offers", "#1baf7a"]];
// bảng màu biểu đồ của giao diện Cyberpunk (cyan / hồng / vàng neon)
const CYBER_COLORS = { pc: "#05d9e8", mobile: "#ff2a6d", offers: "#fcee0a", balance: "#fcee0a" };
const isCyber = () => document.documentElement.getAttribute("data-skin") === "cyberpunk";
const seriesColor = (k) => (isCyber() ? CYBER_COLORS[k] : (SERIES.find((x) => x[0] === k) || [, , "#2a78d6"])[2]);
const RUN_STATES = ["Đang chạy", "Đang chờ", "Đang làm mới", "Đang đăng nhập", "Đang kiểm tra"];
const GROUP_ORDER = ["Tìm kiếm", "Daily Set", "Keep earning", "Quests", "Hoạt động", "Task thêm"];
// Icon task: bộ PNG 3D Fluent Emoji (MIT, vendor/fluent-emoji) thay cho ảnh thumbnail lộn xộn của Rewards.
// Đoán loại task theo tiêu đề, không ra thì theo tên ảnh gốc (id=OMR.food.jpg...), rồi theo nhóm.
// Luật đầu tiên khớp thắng nên luật cụ thể đặt trước.
const ICON_RULES = [
  [/visual|camera|bằng ảnh/, "camera"],
  [/streak|chuỗi/, "fire"],
  [/search pc|desktop|máy tính/, "pc"],
  [/mobile|điện thoại|phone|check-?in/, "mobile"],
  [/quiz|answer|trả lời|question|trivia|câu đố/, "quiz"],
  [/poll|vote|bình chọn|this or that/, "poll"],
  [/food|recipe|burger|cook|pizza|món ăn/, "food"],
  [/travel|\btrip|flight|reef|island|beach|tokyo|du lịch/, "travel"],
  [/news|tin tức/, "news"],
  [/shop|\bdeals?\b|mua sắm/, "shopping"],
  [/\bgames?\b|xbox/, "game"],
  [/music|song|âm nhạc/, "music"],
  [/movie|film|phim/, "movie"],
  [/weather|thời tiết/, "weather"],
  [/sport|football|soccer|\bnba\b|\bnfl\b|thể thao/, "sport"],
  [/\bedge\b|browse|lướt web/, "globe"],
  [/gift|redeem|quà/, "gift"],
  [/punch ?card|trophy|level/, "trophy"],
  [/learn|study|học/, "learn"],
  [/money|finance|stock|tiền/, "money"],
  [/pencil|write|viết/, "pencil"],
  [/autumn|\bfall|leaf/, "leaf"],
  [/spring|flower|bloom/, "flower"],
  [/wallpaper|photo|picture/, "picture"],
  [/bing|search|tìm/, "search"],
];
const GROUP_ICONS = { "Tìm kiếm": "search", "Daily Set": "calendar", "Keep earning": "gem", "Quests": "trophy", "Hoạt động": "bolt",
                      "Task thêm": "sparkles" };
const matchIcon = (text) => ICON_RULES.find(([re]) => re.test(String(text || "").toLowerCase()))?.[1];
const iconName = (t) => matchIcon(t.title) || matchIcon(t.img) || GROUP_ICONS[t.group] || "sparkles";
// Mỗi icon có 2 bản: ảnh 3D Fluent Emoji (theme Sáng / Tối) và icon nét Tabler (theme Cyberpunk: nét neon phát sáng,
// hợp kiểu HUD hơn ảnh 3D nhiều màu). CSS chỉ hiện 1 bản theo theme.
const LINE_ICONS = {
  search: "ti-search", pc: "ti-device-desktop", mobile: "ti-device-mobile", calendar: "ti-calendar-event", gem: "ti-diamond",
  bolt: "ti-bolt", camera: "ti-camera", quiz: "ti-brain", question: "ti-help-hexagon", poll: "ti-chart-bar",
  food: "ti-tools-kitchen-2", travel: "ti-plane", globe: "ti-world", news: "ti-news", shopping: "ti-shopping-bag",
  game: "ti-device-gamepad-2", music: "ti-music", movie: "ti-movie", weather: "ti-sun", sport: "ti-ball-football",
  check: "ti-circle-check", fire: "ti-flame", trophy: "ti-trophy", gift: "ti-gift", sparkles: "ti-sparkles", learn: "ti-school",
  money: "ti-coin", pencil: "ti-pencil", picture: "ti-photo", leaf: "ti-leaf", flower: "ti-flower", target: "ti-target-arrow",
  rocket: "ti-rocket", key: "ti-key", robot: "ti-robot",
};
// icon SVG riêng của app (assets/icons) thay cho ảnh Fluent Emoji ở theme Sáng / Tối; Cyberpunk vẫn dùng icon nét
const ASSET_ICONS = { search: "bing.svg", camera: "visual.svg", mobile: "mobile.svg", calendar: "daily-set.svg" };
const iconSrc = (name) => (ASSET_ICONS[name] ? `assets/icons/${ASSET_ICONS[name]}` : `vendor/fluent-emoji/${name}.png`);
const icon = (name, cls = "") => `<span class="tico ${cls}" data-icon="${name}">`
  + `<img src="${iconSrc(name)}" alt="" draggable="false"><i class="ti ${LINE_ICONS[name] || "ti-point"}"></i></span>`;
const taskIcon = (t, cls = "") => icon(iconName(t), cls);
// icon riêng của app cho streak (ngọn lửa) và điểm (chồng xu), dùng ở mọi theme
const STREAK_IMG = (cls = "") => `<img class="ico-streak ${cls}" src="assets/flame.png" alt="" draggable="false">`;
const POINT_IMG = (cls = "") => `<img class="ico-point ${cls}" src="assets/point.svg" alt="" draggable="false">`;

// ảnh lỗi -> ẩn đi (CSP không cho onerror nội tuyến nên bắt chung ở document)
document.addEventListener("error", (e) => { if (e.target.tagName === "IMG") e.target.classList.add("broken"); }, true);

// ===================================================================== khởi động
window.addEventListener("pywebviewready", async () => {
  const b = await api().bootstrap();
  Object.assign(S, b, { running: new Set(b.running) });
  S.selected = S.profiles[0]?.name ?? null;
  bindStatic();
  window.Office?.init();
  applyTheme();
  applyLanguage();
  renderAll();
  if (S.settings.check_updates !== false) checkUpdate(false);
});

// ===================================================================== cập nhật
function showUpdateBar(text, actions = "") {
  $("#update-text").innerHTML = text;
  $("#update-actions").innerHTML = actions;
  $("#update-bar").hidden = false;
  $("#btn-upd-notes")?.addEventListener("click", () => api().open_releases());
  $("#btn-upd-get")?.addEventListener("click", downloadUpdate);
  $("#btn-upd-apply")?.addEventListener("click", applyUpdate);
}
// manual = bấm "Kiểm tra ngay": báo cả khi không có bản mới / lỗi; tự kiểm tra lúc mở app thì im lặng
async function checkUpdate(manual) {
  const res = $("#update-result");
  if (manual && res) res.textContent = "Đang kiểm tra...";
  const r = await api().check_update();
  const msg = !r.ok ? r.error : r.newer ? `Có bản mới ${r.latest}` : `Đang dùng bản mới nhất (${r.current})`;
  if (res) res.textContent = msg;
  if (!r.ok || !r.newer) { if (manual) toast(msg); return; }
  const notes = `<button type="button" class="btn btn-sm" id="btn-upd-notes">Xem thay đổi</button>`;
  showUpdateBar(`Có bản mới <b>${esc(r.latest)}</b> (đang dùng ${esc(r.current)})`,
    r.can_install ? notes + `<button type="button" class="btn btn-sm btn-primary" id="btn-upd-get">Tải và cập nhật</button>`
      : notes + (S.app?.frozen ? "" : `<span class="small">Bản mã nguồn: cập nhật bằng <code>git pull</code></span>`));
}
async function downloadUpdate() {
  const r = await api().download_update();
  if (!r.ok) { toast(r.error); return; }
  showUpdateBar("Đang tải bản cập nhật...");
}
async function applyUpdate() {
  const r = await api().apply_update();
  if (!r.ok) { toast(r.error); return; }
  showUpdateBar("Đang cập nhật, app sẽ tự mở lại sau vài giây...");
}
function onUpdateEvent(e) {
  if (e.state === "downloading") {
    showUpdateBar(`Đang tải bản cập nhật... ${e.total ? Math.round((e.done / e.total) * 100) + "%" : fmt(Math.round(e.done / 1048576)) + " MB"}`);
  } else if (e.state === "ready") {
    showUpdateBar(`Đã tải xong bản <b>${esc(e.version)}</b>. Dữ liệu và phiên đăng nhập được giữ nguyên.`,
      `<button type="button" class="btn btn-sm btn-primary" id="btn-upd-apply">Khởi động lại để cập nhật</button>`);
  } else if (e.state === "error") {
    showUpdateBar(`Cập nhật lỗi: ${esc(e.error)}`, `<button type="button" class="btn btn-sm" id="btn-upd-notes">Mở trang tải về</button>`);
  }
}

window.onEvents = (batch) => {
  let dirty = false;
  for (const e of batch) {
    if (e.type === "log") {
      S.logs.push(e);
      if (/^\s*(lỗi|cảnh báo)/i.test(e.msg)) S.unreadErr++;
      if (S.page === "log") appendLog(e);
      window.Office?.onLog(e);
    } else if (e.type === "status") {
      const st = (S.pstate[e.name] ||= {});
      Object.assign(st, e.data);
      if (e.history) S.history[e.name] = e.history;
      if (RUN_STATES.includes(e.data.state)) S.running.add(e.name);
      dirty = true;
    } else if (e.type === "done") {
      S.running.delete(e.name); dirty = true;
    } else if (e.type === "update") {
      onUpdateEvent(e);
    }
  }
  if (S.logs.length > 4000) S.logs = S.logs.slice(-3000);
  if (dirty) { renderSide(); if (S.page === "dashboard") renderDashboard(); if (S.page === "profiles") renderProfiles(); window.Office?.render(); }
  renderLogBadge();
};

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), 2600);
}

// ===================================================================== sáng / tối
const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
const isDark = () => document.documentElement.getAttribute("data-bs-theme") === "dark";
function applyTheme() {
  const mode = S.settings.theme || "system";
  const cyber = mode === "cyberpunk";  // Cyberpunk luôn là nền tối + lớp giao diện riêng (cyberpunk.css)
  const dark = cyber || mode === "dark" || (mode === "system" && darkQuery.matches);
  const changed = isDark() !== dark || isCyber() !== cyber;
  document.documentElement.setAttribute("data-bs-theme", dark ? "dark" : "light");
  if (cyber) document.documentElement.setAttribute("data-skin", "cyberpunk");
  else document.documentElement.removeAttribute("data-skin");
  $$(".theme-switch button").forEach((b) => b.classList.toggle("active", b.dataset.theme === mode));
  $$("#theme-choice input").forEach((i) => (i.checked = i.value === mode));
  if (changed && S.page === "dashboard") { Charts.reset(); renderDashboard(); }
}
async function setTheme(mode) {
  S.settings.theme = mode; applyTheme();  // đổi ngay, lưu sau
  await saveSettings({ theme: mode });
}
darkQuery.addEventListener("change", () => (S.settings.theme || "system") === "system" && applyTheme());

// ===================================================================== điều hướng + nút cố định
// ===================================================================== ngôn ngữ (i18n.js dịch giao diện sang English)
function applyLanguage() {
  const lang = S.settings.language === "en" ? "en" : "vi";
  I18N.apply(lang);
  $$(".lang-switch button").forEach((b) => b.classList.toggle("active", b.dataset.setLang === lang));
  $$("#lang-choice input").forEach((i) => (i.checked = i.value === lang));
}
async function setLanguage(lang) {
  S.settings.language = lang;
  applyLanguage();
  Charts.reset();
  renderAll();  // vẽ lại từ chữ gốc (về tiếng Việt thì các nút đã dịch được thay mới)
  await saveSettings({ language: lang });
}

function bindStatic() {
  $$(".lang-switch button").forEach((b) => (b.onclick = () => setLanguage(sideCycle(b, "setLang"))));
  $$("#lang-choice input").forEach((i) => (i.onchange = () => setLanguage(i.value)));
  $("#tasks-hide-done").onchange = (e) => { pref.set("hideDoneTasks", e.target.checked); renderTasks(st(S.selected)); };
  $("#update-dismiss").onclick = () => ($("#update-bar").hidden = true);
  $("#btn-check-update").onclick = () => checkUpdate(true);
  $$("#nav [data-page]").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); go(b.dataset.page); }));
  $("#side-toggle").onclick = () => setSideCollapsed(!document.documentElement.classList.contains("side-collapsed"));
  syncSide();
  // nội dung rộng / hẹp theo thanh bên: báo cho biểu đồ ApexCharts (chỉ tự co giãn khi cửa sổ đổi cỡ)
  $(".page-wrapper").addEventListener("transitionend", (e) => {
    if (e.target === e.currentTarget && e.propertyName === "margin-left") window.dispatchEvent(new Event("resize"));
  });
  $$(".theme-switch button").forEach((b) => (b.onclick = () => setTheme(sideCycle(b, "theme"))));
  $$("#theme-choice input").forEach((i) => (i.onchange = () => setTheme(i.value)));
  $("#btn-refresh").onclick = () => S.selected && start([S.selected], "refresh");
  $("#btn-run-one").onclick = () => S.selected && start([S.selected], "run");
  $("#btn-run-all").onclick = () => start(null, "run");
  $("#btn-do-everything").onclick = () => start(null, "everything");
  $("#btn-stop-all").onclick = async () => { await api().stop(null); toast("Đã gửi lệnh dừng"); };
  $("#btn-add").onclick = () => openProfileDialog(null);
  $("#btn-clear-log").onclick = () => { S.logs = []; S.unreadErr = 0; renderLog(); renderLogBadge(); };
  $("#btn-copy-log").onclick = copyLog;
  $("#log-filter").onchange = renderLog;
  $("#btn-save-settings").onclick = saveSettingsForm;
  $("#max-parallel").onchange = (e) => saveSettings({ max_parallel: Math.max(1, +e.target.value || 1) });
  bindProfileDialog();
  bindGoalDialog();
}

// thanh bên thu gọn: chỉ còn icon; tên trang hiện khi di chuột (title). Nhớ lựa chọn trong localStorage
function setSideCollapsed(on) {
  document.documentElement.classList.toggle("side-collapsed", on);
  pref.set("sideCollapsed", on);
  syncSide();
}
// thanh bên thu gọn chỉ hiện nút đang chọn: bấm nó thì lấy lựa chọn kế tiếp trong nhóm
function sideCycle(b, key) {
  if (!document.documentElement.classList.contains("side-collapsed") || !b.classList.contains("active")) return b.dataset[key];
  const all = [...b.parentElement.querySelectorAll("button")];
  return all[(all.indexOf(b) + 1) % all.length].dataset[key];
}
function syncSide() {
  const on = document.documentElement.classList.contains("side-collapsed"), t = $("#side-toggle");
  const label = on ? "Mở rộng thanh bên" : "Thu gọn thanh bên";
  t.title = on ? label : ""; t.setAttribute("aria-label", label); t.setAttribute("aria-expanded", String(!on));
  $$(".theme-switch button, .lang-switch button").forEach((b) => {  // gợi ý "bấm để đổi" khi chỉ còn 1 nút
    if (!b.dataset.tip) b.dataset.tip = b.title || b.textContent.trim();
    b.title = on ? `${b.dataset.tip} (bấm để đổi)` : b.dataset.tip;
  });
  t.querySelector("i").className = "ti " + (on ? "ti-layout-sidebar-left-expand" : "ti-layout-sidebar-left-collapse");
  $$("#nav .nav-link").forEach((a) => { a.title = on ? a.querySelector(".nav-link-title").textContent.trim() : ""; });
  $("#run-state").title = on ? $("#run-state span:last-child").textContent : "";
}

function go(page) {
  S.page = page;
  $$("#nav [data-page]").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  $$(".view").forEach((p) => (p.hidden = p.id !== "page-" + page));
  if (page === "log") S.unreadErr = 0;
  if (page === "dashboard") Charts.reset();  // vẽ lại theo kích thước thật sau khi trang hiện ra
  renderAll();
  window.scrollTo(0, 0);
}

async function start(names, action) {
  const r = await api().start(names, action);
  if (r.ok === false) { toast(r.error); return; }
  r.running.forEach((n) => S.running.add(n));
  renderSide(); renderDashboard(); renderProfiles();
  toast({ run: "Bắt đầu chạy", everything: "Bắt đầu làm tất cả các việc", refresh: "Đang làm mới điểm", login: "Đã mở cửa sổ đăng nhập",
          check: "Đang kiểm tra (không search)" }[action]);
}

function renderAll() {
  renderSide();
  if (S.page === "dashboard") renderDashboard();
  if (S.page === "profiles") renderProfiles();
  if (S.page === "log") renderLog();
  if (S.page === "history") renderHistory();
  if (S.page === "settings") renderSettings();
  window.Office?.render();  // tự dừng vẽ khi không ở trang Văn phòng
  renderLogBadge();
}

function renderSide() {
  $("#brand-sub").textContent = `${S.profiles.length} tài khoản`;
  const on = S.running.size > 0;
  $("#run-state").classList.toggle("on", on);
  $("#run-state span:last-child").textContent = on ? `Đang chạy ${S.running.size} tài khoản` : "Đang nghỉ";
  if (document.documentElement.classList.contains("side-collapsed")) $("#run-state").title = $("#run-state span:last-child").textContent;
}

function renderLogBadge() {
  const b = $("#log-badge");
  b.hidden = !S.unreadErr || S.page === "log";
  b.textContent = S.unreadErr;
}

// ảnh đại diện (data URL do Python trả về) hoặc chữ viết tắt; cls = các lớp avatar của Tabler
const avatarHtml = (name, cls = "avatar-sm") => {
  const url = (S.avatars || {})[name];
  return url ? `<span class="avatar ${cls} has-img" style="background-image:url('${url}')"></span>`
    : `<span class="avatar ${cls}">${esc(initials(name))}</span>`;
};
const initials = (n) => n.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
const st = (name) => S.pstate[name] || {};

function statePill(name) {
  const s = st(name).state || "Sẵn sàng";
  const cls = RUN_STATES.includes(s) ? "bg-blue-lt" : s === "Hoàn thành" ? "bg-green-lt"
    : ["Lỗi", "Chưa đăng nhập"].includes(s) ? "bg-red-lt" : "bg-secondary-lt";
  return `<span class="badge ${cls}">${esc(s)}</span>`;
}
const doneBadge = (done) => `<span class="badge ${done ? "bg-green-lt" : "bg-yellow-lt"}">${done ? "Xong" : "Chưa xong"}</span>`;
const bar = (pct, color) => `<div class="progress"><div class="progress-bar" style="width:${Math.min(100, Math.max(0, pct))}%${color ? `;background:${color}` : ""}"></div></div>`;

// ===================================================================== tổng quan
function renderDashboard() {
  const chips = $("#profile-chips");
  if (!S.profiles.length) {
    chips.innerHTML = `<button class="btn btn-primary" id="btn-first-profile"><i class="ti ti-user-plus"></i>Thêm tài khoản đầu tiên</button>`;
    $("#btn-first-profile").addEventListener("click", () => { go("profiles"); openProfileDialog(null); });
  } else {
    chips.innerHTML = S.profiles.map((p) => `
      <button class="chip ${p.name === S.selected ? "active" : ""}" data-name="${esc(p.name)}">
        ${avatarHtml(p.name, `avatar-sm rounded-circle ${S.running.has(p.name) ? "run" : ""}`)}
        <span>${esc(p.name)}</span><span class="pts">${POINT_IMG()}${fmt(st(p.name).points)}</span>
      </button>`).join("");
    $$(".chip", chips).forEach((c) => (c.onclick = () => { S.selected = c.dataset.name; Charts.reset(); renderDashboard(); }));
  }
  const name = S.selected;
  const s = st(name);
  const stats = s.stats || {};
  const heroUrl = name && (S.avatars || {})[name];
  $("#hero-avatar").textContent = name && !heroUrl ? initials(name) : "";
  $("#hero-avatar").style.backgroundImage = heroUrl ? `url('${heroUrl}')` : "";
  $("#hero-avatar").classList.toggle("has-img", !!heroUrl);
  $("#hero-name").textContent = name || "Chưa có tài khoản";
  $("#hero-state").textContent = name ? `${s.state || "Sẵn sàng"}${s.progress ? " · " + s.progress : ""}` : "";
  $("#hero-points").textContent = fmt(s.points);
  $("#hero-today").textContent = s.today != null ? "+" + fmt(s.today) : "—";
  $("#hero-month").textContent = fmt(stats.month);
  $("#hero-life").textContent = fmt(stats.lifetime);
  for (const id of ["#btn-run-one", "#btn-refresh"]) $(id).disabled = !name || S.running.has(name);
  renderGoal(name, s);
  $("#tasks-updated").textContent = s.updated ? "Cập nhật " + s.updated : "";
  renderStamps(s);
  renderStreak(s);
  renderMeters(s);
  renderTasks(s);
  renderCharts(name);
  renderStats(name, s);
}

// ===================================================================== mục tiêu đổi quà
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
// còn bao nhiêu điểm, trung bình điểm/ngày (14 ngày gần nhất có số liệu, bỏ hôm nay vì chưa hết ngày), dự kiến bao lâu
function goalEstimate(points, target, hist, today = isoDay(new Date())) {
  const left = Math.max(0, target - (points || 0));
  const days = Object.keys(hist || {}).filter((d) => d < today && hist[d]?.today > 0).sort().slice(-14);
  const avg = days.length ? days.reduce((a, d) => a + hist[d].today, 0) / days.length : 0;
  const need = left && avg ? Math.ceil(left / avg) : 0;
  const eta = need ? new Date(new Date(today + "T00:00:00").getTime() + need * 864e5) : null;
  return { left, avg: Math.round(avg), samples: days.length, days: need, eta };
}
function renderGoal(name, s) {
  const box = $("#hero-goal");
  if (!name) { box.innerHTML = ""; return; }
  const g = (S.goals || {})[name];
  if (!g) {
    box.innerHTML = `<button class="goal-set" type="button" id="btn-goal"><i class="ti ti-target-arrow"></i>Đặt mục tiêu đổi quà</button>`;
  } else {
    const e = goalEstimate(s.points, g.points, S.history[name]);
    const pct = Math.min(100, ((s.points || 0) / g.points) * 100);
    const when = !e.left ? `<b class="goal-done">Đủ điểm rồi, vào trang Redeem để đổi</b>`
      : e.avg ? `còn <b>${fmt(e.left)}</b> điểm · khoảng <b>${e.days} ngày</b> (${e.eta.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" })}), trung bình ${fmt(e.avg)}/ngày`
      : `còn <b>${fmt(e.left)}</b> điểm · chưa đủ lịch sử để dự đoán`;
    box.innerHTML = `<div class="goal-head"><span class="goal-title" title="${esc(g.title)}"><i class="ti ti-target-arrow"></i>${esc(g.title)}</span>
        <button class="goal-edit" type="button" id="btn-goal" title="Sửa mục tiêu"><i class="ti ti-pencil"></i></button>
        <span class="goal-num">${fmt(s.points)} / ${fmt(g.points)}</span></div>
      <div class="goal-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${g.points}" aria-valuenow="${s.points || 0}"><span style="width:${pct.toFixed(1)}%"></span></div>
      <div class="goal-eta">${when}</div>`;
  }
  $("#btn-goal").onclick = () => openGoalDialog(name);
}
function openGoalDialog(name) {
  const dlg = $("#goal-dialog"), g = (S.goals || {})[name];
  dlg.dataset.name = name;
  $("#gd-who").textContent = `Tài khoản ${name}: hiện có ${fmt(st(name).points)} điểm.`;
  $("#gd-title").value = g ? g.title : "";
  $("#gd-points").value = g ? g.points : "";
  $("#gd-clear").hidden = !g;
  $("#gd-error").textContent = "";
  dlg.showModal(); $("#gd-title").focus();
}
function bindGoalDialog() {
  const dlg = $("#goal-dialog");
  $("#goal-form").onsubmit = async (e) => {
    const act = e.submitter?.value;
    if (act !== "ok" && act !== "clear") return;
    e.preventDefault();
    const pts = act === "clear" ? 0 : Number($("#gd-points").value);
    if (act === "ok" && !(Number.isInteger(pts) && pts > 0)) { $("#gd-error").textContent = "Nhập số điểm cần (số nguyên lớn hơn 0)."; return; }
    const r = await api().set_goal(dlg.dataset.name, $("#gd-title").value, pts);
    if (!r.ok) { $("#gd-error").textContent = r.error; return; }
    S.goals = r.goals; dlg.close(); renderDashboard();
    toast(act === "clear" ? "Đã xóa mục tiêu" : "Đã lưu mục tiêu");
  };
}

function renderStamps(s) {
  // mỗi task có điểm của hôm nay là 1 con dấu: search PC/Mobile, Daily Set, Keep earning
  const tasks = (s.tasks || []).filter((t) => ["Tìm kiếm", "Daily Set", "Keep earning"].includes(t.group));
  const box = $("#stamps");
  if (!tasks.length) {
    box.innerHTML = `<p class="empty-note w-100">Chưa có dữ liệu. Bấm <b>Làm mới</b> để đọc task hôm nay từ Rewards.</p>`;
    $("#stamp-count").textContent = "";
    return;
  }
  const done = tasks.filter((t) => t.done).length;
  $("#stamp-count").textContent = `${done}/${tasks.length} dấu`;
  box.innerHTML = tasks.map((t) => `
    <div class="stamp ${t.done ? "done" : ""}" title="${esc(t.title)} · ${t.done ? "Đã xong" : "Chưa làm"} · +${t.max} điểm">
      <div class="stamp-wrap"><div class="disc">${taskIcon(t)}</div>
      <span class="check"><i class="ti ti-check"></i></span></div>
      <span class="pts">${POINT_IMG()}+${t.max}</span>
    </div>`).join("");
}

function renderStreak(s) {
  // Stamp bonus của Rewards: đủ 12 dấu (từ các chuỗi streak) thì được thưởng (thường +1.000 điểm)
  const info = s.streak || {};
  const stamps = info.stamps, streaks = info.streaks || [];
  const panel = $("#streak-panel");
  if (!stamps && !streaks.length) { panel.hidden = true; return; }
  panel.hidden = false;
  const have = stamps?.progress ?? 0, max = stamps?.max || 12, bonus = stamps?.bonus || 1000;
  const left = Math.max(0, max - have);
  $("#streak-sub").textContent = stamps ? `${have}/${max} dấu` : "";
  $("#daily-streak").innerHTML = info.daily_streak != null
    ? `<span class="flame">${STREAK_IMG()}</span><div><b>${fmt(info.daily_streak)} ngày</b><span>Daily streak liên tiếp</span></div>` : "";
  $("#stamp-grid").setAttribute("aria-label", `${have} trên ${max} dấu`);
  $("#stamp-grid").innerHTML = Array.from({ length: max }, (_, i) =>
    `<span class="sdot ${i < have ? "on" : i === have ? "next" : ""}"><i class="ti ${i < have ? "ti-star-filled" : "ti-star"}"></i></span>`).join("");
  $("#streak-hint").innerHTML = !stamps ? "Chưa đọc được số dấu."
    : left ? `Còn <b>${left}</b> dấu nữa để nhận <b>+${fmt(bonus)}</b> điểm. Giữ các chuỗi streak bên cạnh mỗi ngày để nhận dấu.`
    : `Đã đủ ${max} dấu: vào Rewards để nhận <b>+${fmt(bonus)}</b> điểm.`;
  $("#streak-list").innerHTML = streaks.map((r) => {
    // giống trang Rewards: 7 ô cho 7 ngày; ô đã xong tô vàng, ô hôm nay viền nổi
    const n = r.of || 7, day = Math.min(r.day, n);
    const todayIdx = r.today_done ? day - 1 : day;
    const days = Array.from({ length: n }, (_, i) =>
      `<span class="sday ${i < day ? "on" : ""} ${i === todayIdx ? "today" : ""}" title="Ngày ${i + 1}">${i < day ? '<i class="ti ti-check"></i>' : i + 1}</span>`).join("");
    const status = r.today_done ? `<span class="badge bg-green-lt">Hôm nay xong</span>`
      : `<span class="badge bg-yellow-lt">Hôm nay chưa${r.today ? " · " + esc(r.today) : ""}</span>`;
    return `<div class="streak-row">${taskIcon(r)}
      <div class="min-w-0"><div class="t text-truncate">${esc(r.title)}</div>
        <div class="sub">Ngày ${r.day}/${n}${r.next ? ` · ngày tới +${r.next} điểm` : ""}</div></div>
      ${status}
      <div class="days">${days}</div></div>`;
  }).join("");
}

function renderMeters(s) {
  const stats = s.stats || {};
  const rows = [["pc", "Search PC"], ["mobile", "Search Mobile"]];
  $("#meters").innerHTML = rows.map(([k, label]) => {
    const p = stats[k], m = stats[k + "_max"], color = seriesColor(k);
    return `<div class="meter">${icon(k)}
      <span class="label">${label}</span><span class="val">${m ? `${p}/${m} điểm` : "chưa có dữ liệu"}</span>
      ${bar(m ? (p / m) * 100 : 0, color)}</div>`;
  }).join("");
}

// "Ẩn việc đã xong" chỉ là tiện ích của người xem, nhớ trong trình duyệt (lỗi đọc/ghi thì bỏ qua)
const pref = {
  get: (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* bỏ qua */ } },
};
// vòng tiến độ nhỏ cho tiêu đề nhóm (SVG, vẽ theo tỉ lệ thật)
const ring = (pct) => {
  const r = 7, c = 2 * Math.PI * r, p = Math.max(0, Math.min(1, pct));
  return `<svg class="ring" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="${r}" class="ring-bg"/>
    <circle cx="9" cy="9" r="${r}" class="ring-fg ${p >= 1 ? "full" : ""}" stroke-dasharray="${(c * p).toFixed(2)} ${c.toFixed(2)}" transform="rotate(-90 9 9)"/></svg>`;
};
function renderTasks(s) {
  // Search PC/Mobile đã có thanh tiến độ ngay bên trên (Thẻ đóng dấu) nên không lặp lại ở đây
  const tasks = (s.tasks || []).filter((t) => t.group !== "Tìm kiếm");
  const box = $("#task-groups");
  const hide = pref.get("hideDoneTasks", false);
  $("#tasks-hide-done").checked = hide;
  if (!tasks.length) { box.innerHTML = `<p class="empty-note">Chưa có dữ liệu task cho tài khoản này.</p>`; return; }
  const groups = {};
  tasks.forEach((t) => (groups[t.group] ||= []).push(t));
  box.innerHTML = Object.keys(groups)
    .sort((a, b) => (GROUP_ORDER.indexOf(a) + 99) % 99 - (GROUP_ORDER.indexOf(b) + 99) % 99)
    .map((g) => {
      const items = groups[g], d = items.filter((t) => t.done).length;
      // việc chưa xong lên trước, việc đã xong xuống cuối (giữ thứ tự gốc trong từng phần)
      const shown = [...items.filter((t) => !t.done), ...(hide ? [] : items.filter((t) => t.done))];
      const rows = shown.map((t) => {
        const unit = t.unit || "điểm";
        const note = t.bot ? ` · ${t.bot}` : "";
        return `<li class="trow ${t.done ? "done" : ""}" title="${esc(t.title)}${esc(note)}">
          <span class="ticon">${taskIcon(t)}</span>
          <span class="tname">${esc(t.title)}</span>
          <span class="tpill ${t.done ? "ok" : t.progress > 0 ? "part" : ""}">${t.done ? '<i class="ti ti-check"></i>' : ""}${fmt(t.progress)}/${fmt(t.max)}<small>${esc(unit)}</small></span>
        </li>`;
      }).join("");
      const allDone = hide && d === items.length;
      return `<section class="tgroup ${d === items.length ? "complete" : ""}">
        <h3>${icon(GROUP_ICONS[g] || "sparkles")}<span class="gname">${esc(g)}</span>${ring(items.length ? d / items.length : 0)}<span class="count">${d}/${items.length}</span></h3>
        ${allDone ? `<p class="tgroup-done"><i class="ti ti-circle-check"></i>Xong hết</p>` : `<ul class="tlist">${rows}</ul>`}
      </section>`;
    }).join("");
}

// ===================================================================== biểu đồ (ApexCharts)
const Charts = {
  inst: {}, keys: {},
  reset() { for (const k in this.inst) { this.inst[k].destroy(); } this.inst = {}; this.keys = {}; },
  // chỉ vẽ lại khi dữ liệu / theme đổi (sự kiện trạng thái đến liên tục khi bot chạy)
  draw(id, key, make) {
    const el = $("#" + id);
    if (this.keys[id] === key && this.inst[id]) return;
    if (this.inst[id]) { this.inst[id].destroy(); delete this.inst[id]; }
    this.keys[id] = key;
    const opts = make();
    if (!opts) return;
    el.innerHTML = "";
    this.inst[id] = new ApexCharts(el, opts);
    this.inst[id].render();
  },
};
function chartBase() {
  const dark = isDark(), cyber = isCyber();
  return {
    chart: { height: 250, toolbar: { show: false }, zoom: { enabled: false }, animations: { enabled: false },
             fontFamily: cyber ? '"Chakra Petch", Bahnschrift, sans-serif' : "inherit", background: "transparent",
             foreColor: cyber ? "#8b96c4" : dark ? "#9aa6b8" : "#6b7385" },
    theme: { mode: dark ? "dark" : "light" },
    grid: { borderColor: cyber ? "rgba(5,217,232,.14)" : dark ? "rgba(255,255,255,.07)" : "#eef0f5", strokeDashArray: cyber ? 2 : 3,
            xaxis: { lines: { show: false } }, padding: { left: 6, right: 6 } },
    dataLabels: { enabled: false },
    tooltip: { theme: dark ? "dark" : "light" },
    legend: { position: "top", horizontalAlign: "right", fontSize: "12px",
              markers: cyber ? { size: 6, shape: "square" } : { size: 5 }, itemMargin: { horizontal: 8 } },
  };
}
// cột rộng khoảng 28px dù có 2 hay 14 ngày (để % cố định thì ít ngày ra cột to như khối gạch)
const barWidth = (id, n) => `${Math.max(12, Math.min(60, Math.round((28 * n * 100) / Math.max(200, $("#" + id).clientWidth - 60))))}%`;
function emptyChart(id, msg) {
  if (Charts.inst[id]) { Charts.inst[id].destroy(); delete Charts.inst[id]; }
  Charts.keys[id] = "empty";
  $("#" + id).innerHTML = `<div class="empty">${msg}</div>`;
}
function renderCharts(name) {
  const hist = S.history[name] || {};
  const days = Object.keys(hist).sort();
  const lab = (d) => `${d.slice(8, 10)}/${d.slice(5, 7)}`;
  const theme = isCyber() ? "c" : isDark() ? "d" : "l";
  const d14 = days.slice(-14);
  if (!d14.length) emptyChart("chart-daily", "Chưa có lịch sử. Mỗi lần chạy hoặc làm mới sẽ ghi lại điểm của ngày đó.");
  const cyber = isCyber();
  const glow = (color) => ({ enabled: true, top: 0, left: 0, blur: 7, opacity: 0.55, color });
  if (!d14.length) emptyChart("chart-daily", "Chưa có lịch sử. Mỗi lần chạy hoặc làm mới sẽ ghi lại điểm của ngày đó.");
  else Charts.draw("chart-daily", theme + JSON.stringify(d14.map((d) => [d, hist[d].pc, hist[d].mobile, hist[d].offers])), () => {
    const colors = SERIES.map(([k]) => seriesColor(k));
    return {
      ...chartBase(),
      chart: { ...chartBase().chart, type: "bar", stacked: true, ...(cyber && { dropShadow: glow(colors) }) },
      colors,
      series: SERIES.map(([k, l]) => ({ name: l, data: d14.map((d) => hist[d][k] || 0) })),
      xaxis: { categories: d14.map(lab), axisBorder: { show: false }, axisTicks: { show: false } },
      yaxis: { labels: { formatter: (v) => fmt(Math.round(v)) } },
      plotOptions: { bar: { columnWidth: barWidth("chart-daily", d14.length),
                            ...(cyber ? { borderRadius: 0 } : { borderRadius: 4, borderRadiusApplication: "end", borderRadiusWhenStacked: "last" }) } },
      // Cyberpunk: khối đặc mờ dần xuống dưới + viền neon cùng màu, khe tối giữa các phần chồng nhau
      ...(cyber && {
        fill: { type: "gradient", gradient: { type: "vertical", shadeIntensity: 0, opacityFrom: 0.95, opacityTo: 0.45 } },
        stroke: { show: true, width: 2, colors: ["#121a33"] },
      }),
    };
  });
  const d30 = days.slice(-30).filter((d) => hist[d].available != null);
  if (!d30.length) emptyChart("chart-balance", "Chưa có lịch sử điểm.");
  else Charts.draw("chart-balance", theme + JSON.stringify(d30.map((d) => [d, hist[d].available])), () => {
    const color = seriesColor("balance"), last = d30.length - 1;
    return {
      ...chartBase(),
      chart: { ...chartBase().chart, type: "area", ...(cyber && { dropShadow: glow(color) }) },
      colors: [color],
      series: [{ name: "Điểm", data: d30.map((d) => hist[d].available) }],
      stroke: { width: cyber ? 2 : 2.5, curve: cyber ? "straight" : "smooth" },
      fill: cyber ? { type: "gradient", gradient: { shadeIntensity: 0, gradientToColors: ["#ff2a6d"], opacityFrom: 0.4, opacityTo: 0.02 } }
                  : { type: "gradient", gradient: { opacityFrom: 0.35, opacityTo: 0.02 } },
      markers: cyber
        ? { size: d30.length < 8 ? 4 : 0, shape: "square", strokeWidth: 0, hover: { size: 6 },
            discrete: [{ seriesIndex: 0, dataPointIndex: last, size: 6, fillColor: "#ff2a6d", strokeColor: color, shape: "square" }] }
        : { size: d30.length < 3 ? 5 : 0, hover: { size: 5 } },
      grid: { ...chartBase().grid, padding: { left: 6, right: 14 } },
      // nhãn ngày nằm ngang, tối đa ~6 nhãn (để mặc định thì 14-30 ngày bị xoay chéo, khó đọc)
      xaxis: { categories: d30.map(lab), axisBorder: { show: false }, axisTicks: { show: false },
               tickAmount: Math.min(6, d30.length - 1), labels: { rotate: 0, hideOverlappingLabels: true },
               ...(cyber && { crosshairs: { stroke: { color: "#05d9e8", width: 1, dashArray: 3 } } }) },
      yaxis: { labels: { formatter: (v) => fmt(Math.round(v)) } },
      legend: { show: false },
      // Cyberpunk: nhãn HUD số dư hiện tại trên đường ngang nét đứt
      ...(cyber && { annotations: { yaxis: [{ y: hist[d30[last]].available, borderColor: "rgba(252,238,10,.5)", strokeDashArray: 4,
        label: { text: fmt(hist[d30[last]].available), position: "left", textAnchor: "start", offsetX: 4, borderWidth: 0,
                 style: { background: "#fcee0a", color: "#0b1022", fontSize: "11px", fontWeight: 700, padding: { left: 6, right: 6, top: 2, bottom: 2 } } } }] } }),
    };
  });
}
// ===================================================================== số liệu (ô KPI, lịch nhiệt, nguồn điểm, so sánh)
const addDays = (iso, n) => isoDay(new Date(new Date(iso + "T00:00:00").getTime() + n * 864e5));
const searchFull = (h) => h && h.pc_max > 0 && h.mobile_max > 0 && h.pc >= h.pc_max && h.mobile >= h.mobile_max;
// các con số cho 4 ô KPI, tính từ lịch sử điểm theo ngày (hàm thuần để test được)
function computeKpis(hist, today = isoDay(new Date())) {
  hist = hist || {};
  const weekAgo = addDays(today, -7);  // 7 ngày lịch trước hôm nay (ngày không mở app thì không tính)
  const before = Object.keys(hist).filter((d) => d >= weekAgo && d < today && hist[d]?.today > 0);
  const avg7 = before.length ? Math.round(before.reduce((a, d) => a + hist[d].today, 0) / before.length) : null;
  // chuỗi ngày liên tiếp đủ điểm search PC + Mobile: tính từ hôm qua lùi lại (+ hôm nay nếu đã đủ)
  let streak = searchFull(hist[today]) ? 1 : 0;
  for (let d = addDays(today, -1); searchFull(hist[d]); d = addDays(d, -1)) streak++;
  // tháng này so với cùng khoảng ngày của tháng trước
  const ym = today.slice(0, 7), dom = today.slice(8, 10);
  const prev = isoDay(new Date(+today.slice(0, 4), +today.slice(5, 7) - 2, 1)).slice(0, 7);
  const sum = (pre, upto) => Object.keys(hist).filter((d) => d.startsWith(pre) && d.slice(8, 10) <= upto)
    .reduce((a, d) => a + (hist[d]?.today || 0), 0);
  const thisMonth = sum(ym, dom), prevDays = Object.keys(hist).filter((d) => d.startsWith(prev)).length;
  const lastMonth = sum(prev, dom);
  return { avg7, avgDays: before.length, streak, thisMonth, lastMonth,
           change: prevDays && lastMonth ? Math.round(((thisMonth - lastMonth) / lastMonth) * 100) : null };
}
// lịch nhiệt: 12 cột (tuần, thứ Hai đầu tuần) x 7 hàng; mức 0-4 theo điểm trong ngày so với ngày cao nhất
function heatCells(hist, today = isoDay(new Date()), weeks = 12) {
  hist = hist || {};
  const dow = (new Date(today + "T00:00:00").getDay() + 6) % 7;  // 0 = thứ Hai
  const start = addDays(today, -dow - (weeks - 1) * 7);
  const days = Array.from({ length: weeks * 7 }, (_, i) => addDays(start, i));
  const max = Math.max(0, ...days.map((d) => hist[d]?.today || 0));
  return days.map((d) => {
    const v = hist[d]?.today;
    const level = d > today ? -1 : v == null ? null : !v || !max ? 0 : Math.min(4, Math.ceil((v / max) * 4));
    return { day: d, value: v, level };
  });
}
function renderStats(name, s) {
  const hist = S.history[name] || {}, today = isoDay(new Date()), h = hist[today] || {};
  const k = computeKpis(hist, today);
  const stats = s.stats || {};
  // ic: tên icon Tabler ("ti-...") hoặc HTML ảnh sẵn (STREAK_IMG / POINT_IMG)
  const tile = (ic, label, value, sub, cls = "") => `<div class="kpi ${cls}"><span class="kpi-ic">${ic.startsWith("<") ? ic : `<i class="ti ${ic}"></i>`}</span>
    <div class="min-w-0"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-sub">${sub}</div></div></div>`;
  const pcLine = stats.pc_max ? `PC ${fmt(stats.pc)}/${fmt(stats.pc_max)} · Mobile ${fmt(stats.mobile)}/${fmt(stats.mobile_max)}` : "chưa đọc được điểm search";
  $("#kpis").innerHTML = name ? [
    tile(POINT_IMG(), "Hôm nay", s.today != null ? "+" + fmt(s.today) : "—", pcLine),
    tile("ti-chart-line", "Trung bình 7 ngày", k.avg7 != null ? fmt(k.avg7) : "—",
      k.avgDays ? `điểm/ngày, tính trên ${k.avgDays} ngày có số liệu` : "chưa có lịch sử"),
    tile(STREAK_IMG(), "Chuỗi đủ điểm search", `${k.streak} ngày`, searchFull(h) ? "hôm nay đã đủ PC + Mobile" : "hôm nay chưa đủ PC + Mobile",
      k.streak >= 7 ? "good" : ""),
    tile(k.change == null || k.change >= 0 ? "ti-trending-up" : "ti-trending-down", "Tháng này",
      fmt(stats.month ?? k.thisMonth),
      k.change == null ? "chưa có số liệu tháng trước để so" : `${k.change >= 0 ? "+" : ""}${k.change}% so với cùng kỳ tháng trước`,
      k.change == null ? "" : k.change >= 0 ? "good" : "bad"),
  ].join("") : "";

  // lịch nhiệt
  const cells = heatCells(hist, today);
  const fmtD = (d) => `${d.slice(8, 10)}/${d.slice(5, 7)}`;
  $("#heatmap").innerHTML = ["T2", "", "T4", "", "T6", "", "CN"].map((l) => `<span class="hm-day">${l}</span>`).join("")
    + cells.map((c) => `<span class="hm ${c.level === -1 ? "future" : c.level === null ? "none" : "l" + c.level}"
        title="${fmtD(c.day)}: ${c.level === null ? "không có số liệu" : c.level === -1 ? "" : "+" + fmt(c.value || 0) + " điểm"}"></span>`).join("");
  const active = cells.filter((c) => c.level > 0).length, past = cells.filter((c) => c.level !== -1).length;
  $("#heat-summary").textContent = `${active}/${past} ngày có điểm`;
  $("#heatmap").setAttribute("aria-label", `${active} trên ${past} ngày có điểm trong 12 tuần`);

  // nguồn điểm 30 ngày
  const d30 = Object.keys(hist).filter((d) => d > addDays(today, -30)).sort();
  const sums = SERIES.map(([key]) => d30.reduce((a, d) => a + (hist[d]?.[key] || 0), 0));
  const theme = isCyber() ? "c" : isDark() ? "d" : "l";
  if (!sums.some(Boolean)) emptyChart("chart-sources", "Chưa có số liệu điểm search / thẻ.");
  else Charts.draw("chart-sources", theme + JSON.stringify(sums), () => ({
    ...chartBase(),
    chart: { ...chartBase().chart, type: "donut", height: 250 },
    colors: SERIES.map(([key]) => seriesColor(key)),
    series: sums, labels: SERIES.map(([, l]) => l),
    stroke: { width: isCyber() ? 2 : 1, colors: [isCyber() ? "#121a33" : isDark() ? "#182433" : "#fff"] },
    legend: { position: "bottom", fontSize: "12px", markers: isCyber() ? { size: 6, shape: "square" } : { size: 5 } },
    dataLabels: { enabled: true, formatter: (v) => Math.round(v) + "%", dropShadow: { enabled: false } },
    plotOptions: { pie: { donut: { size: "64%", labels: { show: true, total: { show: true, label: "30 ngày",
      formatter: () => fmt(sums.reduce((a, b) => a + b, 0)) } } } } },
    tooltip: { theme: isDark() ? "dark" : "light", y: { formatter: (v) => fmt(v) + " điểm" } },
  }));

  // so sánh tài khoản (chỉ khi có từ 2 tài khoản có lịch sử)
  const names = S.profiles.map((p) => p.name).filter((n) => Object.keys(S.history[n] || {}).length);
  $("#compare-panel").hidden = names.length < 2;
  if (names.length >= 2) {
    const d14 = Array.from({ length: 14 }, (_, i) => addDays(today, i - 13));
    const series = names.map((n) => ({ name: n, data: d14.map((d) => S.history[n]?.[d]?.today ?? null) }));
    const palette = isCyber() ? ["#05d9e8", "#fcee0a", "#ff2a6d", "#b892ff", "#3dff9a"] : ["#2a78d6", "#e9a400", "#d63939", "#ae3ec9", "#2fb344"];
    Charts.draw("chart-compare", theme + JSON.stringify(series), () => ({
      ...chartBase(),
      chart: { ...chartBase().chart, type: "line", height: 240 },
      colors: names.map((n) => palette[nameTone(n) % palette.length]),
      series, stroke: { width: 2.5, curve: isCyber() ? "straight" : "smooth" },
      markers: { size: 3, strokeWidth: 0, hover: { size: 5 } },
      xaxis: { categories: d14.map(fmtD), axisBorder: { show: false }, axisTicks: { show: false }, labels: { rotate: 0, hideOverlappingLabels: true } },
      yaxis: { labels: { formatter: (v) => fmt(Math.round(v)) } },
    }));
  }
}

window.addEventListener("resize", () => { clearTimeout(window._rz); window._rz = setTimeout(() => S.page === "dashboard" && (Charts.reset(), renderDashboard()), 200); });

// ===================================================================== tài khoản
function renderProfiles() {
  const tb = $("#profile-table tbody");
  if (!S.profiles.length) {
    tb.innerHTML = `<tr><td colspan="8" class="empty-note">Chưa có tài khoản. Bấm <b>Thêm tài khoản</b>, rồi <b>Đăng nhập</b> một lần.</td></tr>`;
  } else {
    const ib = (act, icon, label, cls = "") => `<button class="btn btn-sm ${cls}" data-act="${act}" title="${label}"><i class="ti ${icon}"></i>${label}</button>`;
    tb.innerHTML = S.profiles.map((p) => {
      const s = st(p.name), run = S.running.has(p.name);
      return `<tr data-name="${esc(p.name)}">
        <td>${avatarHtml(p.name, `avatar-sm rounded-circle ${run ? "run" : ""}`)}</td>
        <td><b>${esc(p.name)}</b>${savedEmail(p.name) ? ` <span class="badge bg-green-lt ms-1" title="Đã lưu mật khẩu (mã hóa) cho ${esc(savedEmail(p.name))}: phiên hết hạn thì bot tự đăng nhập lại"><i class="ti ti-key"></i> tự đăng nhập</span>` : ""}</td>
        <td class="text-secondary">${p.mode === "cdp" ? `Edge đang mở · cổng ${p.cdp_port}` : p.proxy ? `Cửa sổ riêng · proxy ${esc(p.proxy)}` : "Cửa sổ riêng"}</td>
        <td>${statePill(p.name)}</td>
        <td class="text-end">${fmt(s.points)}</td>
        <td class="text-end">${s.today != null ? "+" + fmt(s.today) : "—"}</td>
        <td class="text-secondary small">${esc(s.progress || "")}</td>
        <td><div class="row-actions">
          ${run ? ib("stop", "ti-player-stop", "Dừng", "btn-outline-danger")
                : ib("run", "ti-player-play", "Chạy", "btn-primary") + ib("check", "ti-stethoscope", "Kiểm tra")
                  + ib("login", "ti-login", "Đăng nhập") + ib("edit", "ti-pencil", "Sửa") + ib("del", "ti-trash", "Xóa", "btn-ghost-danger")}
        </div></td></tr>`;
    }).join("");
    $$("button[data-act]", tb).forEach((b) => (b.onclick = async () => {
      const name = b.closest("tr").dataset.name;
      const act = b.dataset.act;
      if (act === "run") start([name], "run");
      else if (act === "login") start([name], "login");
      else if (act === "check") {  // kết quả kiểm tra ghi vào nhật ký ([Kiểm tra] OK/WARN/FAIL) nên mở luôn trang đó
        S.selected = name; $("#log-filter").value = ""; go("log"); start([name], "check");
      }
      else if (act === "stop") { await api().stop([name]); toast("Đang dừng " + name); }
      else if (act === "edit") openProfileDialog(S.profiles.find((p) => p.name === name));
      else if (act === "del" && confirm(`Xóa tài khoản "${name}" khỏi app?\nPhiên đăng nhập trong data/profiles vẫn được giữ.`)) {
        const r = await api().delete_profiles([name]); S.profiles = r.profiles;
        if (S.selected === name) S.selected = S.profiles[0]?.name ?? null;
        renderAll();
      }
    }));
  }
  renderToggles();
  $("#max-parallel").value = S.settings.max_parallel;
}

function renderToggles() {
  // [khóa cài đặt, tiêu đề, mô tả, icon, mục cha (mục con chỉ bật được khi mục cha bật)]
  const items = [
    ["do_quests", "Daily Set, Keep earning", "Bấm từng thẻ task, làm quiz và poll", "calendar"],
    ["do_quest_tasks", "Quests", "Làm từng bước của các quest nhiều bước ở trang Earn (bước cần app điện thoại / app máy tính thì bỏ qua)", "trophy"],
    ["do_visual", "Visual Search", "Tìm bằng 1 ảnh qua nút camera của Bing (mỗi ngày 1 lượt)", "camera"],
    ["do_pc", "Search PC", "Tìm đến khi đủ điểm search máy tính", "pc"],
    ["do_mobile", "Search Mobile", "Giả lập điện thoại, tìm đến khi đủ điểm", "mobile"],
    ["custom_searches", "Tự chọn số lượt search",
      "Tắt thì search đến khi đủ điểm tối đa. Bật thì search đến đúng số lượt trong ngày ở dưới (3 điểm/lượt) rồi dừng", "target"],
    ["do_browse", "Browse", `Lướt web tối đa ${S.settings.browse_minutes} phút cho Edge – Minutes, đo số phút mỗi 10 phút`, "globe"],
    ["browse_auto_stop", "Tự dừng khi không được tính phút",
      `Edge – Minutes không tăng sau 20 phút thì dừng. Tắt để luôn lướt đủ ${S.settings.browse_minutes} phút`, "", "do_browse"],
    ["headless", "Chạy ẩn", "Không hiện cửa sổ trình duyệt", "robot"],
  ];
  // ô nhập số lượt search trong ngày, hiện ngay dưới "Tự chọn số lượt search" khi công tắc đó bật
  const countRow = () => `<div class="list-group-item toggle-item toggle-sub search-counts">
      <span class="sub-mark"><i class="ti ti-corner-down-right"></i></span>
      <div class="tt">Số lượt search trong ngày</div>
      <div class="count-inputs">${[["pc_searches", "PC"], ["mobile_searches", "Mobile"]].map(([k, l]) =>
        `<label>${l}<input type="number" class="form-control form-control-sm" min="0" max="50" data-count="${k}"
          value="${esc(S.settings[k] ?? 0)}"></label>`).join("")}</div></div>`;
  $("#task-toggles").innerHTML = items.map(([k, t, d, ic, parent]) => {
    const off = parent && !S.settings[parent];
    return `<label class="list-group-item toggle-item ${parent ? "toggle-sub" : ""} ${off ? "is-off" : ""}">
      ${parent ? `<span class="sub-mark"><i class="ti ti-corner-down-right"></i></span>` : `<span class="ico">${icon(ic)}</span>`}
      <div><div class="tt">${t}</div><div class="td">${d}</div></div>
      <span class="form-check form-switch"><input class="form-check-input" type="checkbox" data-key="${k}"
        ${S.settings[k] ? "checked" : ""} ${off ? "disabled" : ""}></span></label>`
      + (k === "custom_searches" && S.settings.custom_searches ? countRow() : "");
  }).join("");
  $$("#task-toggles input[data-key]").forEach((i) => (i.onchange = async () => {
    await saveSettings({ [i.dataset.key]: i.checked });
    // bật/tắt mục con "Tự dừng" theo Browse, hiện/ẩn ô số lượt theo "Tự chọn số lượt search"
    if (i.dataset.key === "do_browse" || i.dataset.key === "custom_searches") renderToggles();
  }));
  $$("#task-toggles input[data-count]").forEach((i) => (i.onchange = async () => {
    const v = parseInt(i.value, 10);
    if (Number.isNaN(v) || v < 0 || v > 50) { toast("Số lượt search cần từ 0 đến 50"); i.value = S.settings[i.dataset.count]; return; }
    if (await saveSettings({ [i.dataset.count]: v })) toast("Đã lưu số lượt search");
  }));
}

async function saveSettings(partial) {
  const r = await api().save_settings(partial);
  S.settings = r.settings;
  if (!r.ok) toast(r.error);
  return r.ok;
}

// email đã lưu mật khẩu (mã hóa) của tài khoản; giao diện không bao giờ có mật khẩu
const savedEmail = (name) => (S.credentials?.emails || {})[name] || "";

function bindProfileDialog() {
  const dlg = $("#profile-dialog"), f = $("#profile-form");
  const syncPort = () => {
    $("#pd-port").hidden = f.mode.value !== "cdp";
    $("#pd-proxy-wrap").hidden = f.mode.value === "cdp";  // Edge tự mở thì proxy do bạn đặt cho Edge đó
    $("#pd-cred").hidden = f.mode.value === "cdp" || !S.credentials?.supported;  // chế độ gắn vào Edge: tự đăng nhập trên Edge đó
  };
  $$("input[name=mode]", f).forEach((r) => (r.onchange = syncPort));
  f.onsubmit = async (e) => {
    if (e.submitter?.value !== "ok") return;
    e.preventDefault();
    const old = dlg.dataset.old || null, had = old ? savedEmail(old) : "";
    const email = $("#pd-email").value.trim(), pass = $("#pd-pass").value;
    if (!$("#pd-cred").hidden && !$("#pd-cred-del").checked && email !== had && (email || had) && !pass) {
      $("#pd-error").textContent = email ? "Nhập mật khẩu cho email này (hoặc xóa email để không tự đăng nhập)."
        : "Muốn bỏ tự đăng nhập thì tick \"Xóa mật khẩu đã lưu\".";
      return;
    }
    const r = await api().save_profile(old, { name: f.name.value, mode: f.mode.value, cdp_port: +f.cdp_port.value,
      proxy: f.proxy.value.trim() });
    if (!r.ok) { $("#pd-error").textContent = r.error; return; }
    const name = f.name.value.trim();
    dlg.dataset.old = name;  // tài khoản đã lưu: bấm Lưu lần nữa (sau lỗi mật khẩu) là sửa, không thêm mới
    if (S.selected === old || !S.selected) S.selected = name;
    S.profiles = r.profiles;
    if (dlg._avatar !== undefined) {
      const a = await api().set_avatar(name, dlg._avatar || null);
      if (!a.ok) { $("#pd-error").textContent = a.error; renderAll(); return; }
      S.avatars = a.avatars;
    }
    if (!$("#pd-cred").hidden) {
      let c = null;
      if ($("#pd-cred-del").checked) c = await api().delete_credentials(name);
      else if (pass) c = await api().save_credentials(name, email, pass);
      $("#pd-pass").value = "";  // không giữ mật khẩu trong ô nhập
      if (c && !c.ok) { $("#pd-error").textContent = c.error; renderAll(); return; }
      if (c) S.credentials = c.credentials;
    }
    dlg.close(); renderAll();
    toast(old ? "Đã lưu tài khoản" : "Đã thêm tài khoản. Bấm Đăng nhập để đăng nhập lần đầu.");
  };
  dlg.addEventListener("close", () => ($("#pd-pass").value = ""));
  $("#pd-avatar-file").onchange = async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try { dlg._avatar = await squareAvatar(file); setAvatarPreview(dlg._avatar, f.name.value); }
    catch { $("#pd-error").textContent = "Không đọc được ảnh này. Chọn file PNG, JPEG hoặc WebP."; }
  };
  $("#pd-avatar-clear").onclick = () => { dlg._avatar = ""; setAvatarPreview("", f.name.value); };
  dlg._sync = syncPort;
}

// cắt giữa thành hình vuông, thu về 128px, nén WebP (nhỏ, đủ nét cho avatar)
async function squareAvatar(file) {
  const img = await createImageBitmap(file);
  const side = Math.min(img.width, img.height), size = 128;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  c.getContext("2d").drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);
  return c.toDataURL("image/webp", 0.88);
}
function setAvatarPreview(url, name) {
  const pv = $("#pd-avatar");
  pv.style.backgroundImage = url ? `url('${url}')` : "";
  pv.textContent = url ? "" : initials(name || "?");
  pv.classList.toggle("has-img", !!url);
  $("#pd-avatar-clear").hidden = !url;
}

function openProfileDialog(p) {
  const dlg = $("#profile-dialog"), f = $("#profile-form");
  dlg.dataset.old = p ? p.name : "";
  $("#pd-title").textContent = p ? "Sửa tài khoản" : "Thêm tài khoản";
  f.name.value = p ? p.name : `Tài khoản ${S.profiles.length + 1}`;
  f.mode.value = p ? p.mode : "managed";
  f.cdp_port.value = p ? p.cdp_port : 9222 + S.profiles.length;
  f.proxy.value = (p && p.proxy) || "";
  dlg._avatar = undefined;  // undefined = không đổi, "" = xóa, data URL = ảnh mới
  setAvatarPreview(p ? (S.avatars || {})[p.name] : "", f.name.value);
  const saved = p ? savedEmail(p.name) : "";
  $("#pd-email").value = saved;
  $("#pd-pass").value = "";
  $("#pd-pass").placeholder = saved ? "Đã lưu (để trống = giữ nguyên)" : "Mật khẩu";
  $("#pd-cred-del").checked = false;
  $("#pd-cred-del-wrap").hidden = !saved;
  $("#pd-error").textContent = "";
  dlg._sync(); dlg.showModal(); f.name.select();
}
window.openProfileDialog = openProfileDialog; window.go = go;

// ===================================================================== lịch sử
const WEEKDAYS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
function renderHistory() {
  const sel = $("#history-filter"), cur = sel.value || "";
  sel.innerHTML = `<option value="">Tất cả tài khoản</option>` + S.profiles.map((p) => `<option ${p.name === cur ? "selected" : ""}>${esc(p.name)}</option>`).join("");
  sel.onchange = renderHistory;
  const rows = [];
  for (const [name, days] of Object.entries(S.history || {})) {
    if (cur && name !== cur) continue;
    for (const [day, h] of Object.entries(days || {})) rows.push({ name, day, h: h || {} });
  }
  rows.sort((a, b) => b.day.localeCompare(a.day) || a.name.localeCompare(b.name));
  const cutoff = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
  const shown = rows.filter((r) => r.day >= cutoff);
  const tb = $("#history-table tbody");
  if (!shown.length) {
    tb.innerHTML = `<tr><td colspan="7" class="empty-note">Chưa có lịch sử. Mỗi lần chạy hoặc làm mới sẽ ghi lại số liệu của ngày đó.</td></tr>`;
    return;
  }
  // ô search: xanh khi đủ, vàng khi thiếu
  const search = (p, m) => (m ? `<span class="hs ${p >= m ? "full" : "short"}">${fmt(p)}/${fmt(m)}</span>` : `<span class="text-secondary">—</span>`);
  tb.innerHTML = shown.map(({ name, day, h }) => {
    const d = new Date(day + "T00:00:00");
    const miss = (h.missing || []).filter((x) => x.g !== "Tìm kiếm");  // PC/Mobile đã có cột riêng
    const missCell = h.missing == null ? `<span class="text-secondary">—</span>`
      : miss.length ? miss.map((x) => `<span class="badge bg-yellow-lt me-1 mb-1" title="${esc(x.g)}">${esc(x.t)}${x.m ? ` ${fmt(x.p ?? 0)}/${fmt(x.m)}` : ""}</span>`).join("")
      : `<span class="badge bg-green-lt">Đủ hết</span>`;
    return `<tr>
      <td class="text-nowrap"><b>${day.slice(8, 10)}/${day.slice(5, 7)}</b> <span class="text-secondary">${WEEKDAYS[d.getDay()]}</span></td>
      <td><span class="nm-tag tone-${nameTone(name)}">${esc(name)}</span></td>
      <td class="text-end"><b>${h.today != null ? "+" + fmt(h.today) : "—"}</b></td>
      <td>${search(h.pc, h.pc_max)}</td>
      <td>${search(h.mobile, h.mobile_max)}</td>
      <td class="text-end">${h.offers != null ? "+" + fmt(h.offers) : "—"}</td>
      <td class="history-miss">${missCell}</td></tr>`;
  }).join("");
}

// ===================================================================== nhật ký
const logFilter = () => $("#log-filter").value;
const LOG_LEVELS = [["", "Tất cả", "ti-list"], ["er", "Lỗi", "ti-alert-octagon"], ["warn", "Cảnh báo", "ti-alert-triangle"],
                    ["ok", "Xong", "ti-circle-check"]];
const LOG_EMPTY = `<div class="log-empty"><span class="log-empty-ic"><i class="ti ti-terminal-2"></i></span>
  <b>Chưa có nhật ký</b><span>Bấm <em>Chạy</em> hoặc <em>Kiểm tra</em> một tài khoản, từng bước bot làm sẽ hiện ở đây.</span></div>`;
function renderLog() {
  const sel = $("#log-filter"), cur = sel.value || "";
  sel.innerHTML = `<option value="">Tất cả tài khoản</option>` + S.profiles.map((p) => `<option ${p.name === cur ? "selected" : ""}>${esc(p.name)}</option>`).join("");
  const box = $("#logbox"); box.innerHTML = "";
  S.logs.filter((l) => !cur || l.name === cur).slice(-1500).forEach((l) => appendLog(l, false));
  if (!box.children.length) box.innerHTML = LOG_EMPTY;
  logCount();
}
// mức của 1 dòng: lỗi / cảnh báo / xong (dòng [Kiểm tra] ghi OK / WARN / FAIL)
const logLevel = (m) => (/^\s*lỗi|\bFAIL\b|traceback|exception/i.test(m) ? "er"
  : /^\s*cảnh báo|\bWARN\b/i.test(m) ? "warn"
  : /\bOK\b|(?<!chưa )xong|hoàn tất|thành công/i.test(m) ? "ok" : "");
// mỗi tài khoản 1 màu nhãn cố định (băm tên)
const nameTone = (n) => [...String(n)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % 5;
// loại việc của 1 dòng -> icon (search, thẻ, quest, ảnh, browse, kiểm tra, đăng nhập, điểm)
const LOG_KINDS = [
  [/^\s*\[kiểm tra\]/i, "ti-stethoscope"], [/quest/i, "ti-trophy"], [/visual search/i, "ti-camera"],
  [/browse|edge – minutes/i, "ti-world"], [/daily set|keep earning|thẻ/i, "ti-cards"],
  [/search (pc|mobile)|\[search|lượt search/i, "ti-search"], [/đăng nhập|phiên/i, "ti-login"],
  [/điểm hiện tại|xong!|đã cập nhật|điểm/i, "ti-coin"],
];
const logKind = (m) => (LOG_KINDS.find(([re]) => re.test(m)) || [, "ti-point"])[1];
// dòng mở đầu 1 lượt chạy / kiểm tra -> vạch ngăn để các lượt không lẫn vào nhau
const isRunStart = (m) => /^điểm hiện tại:/i.test(m) || /^\[kiểm tra\] \w+ – proxy/i.test(m);
function logCount() {
  const cur = logFilter(), lines = S.logs.filter((l) => !cur || l.name === cur);
  const n = { "": lines.length, er: 0, warn: 0, ok: 0 };
  lines.forEach((l) => { const v = logLevel(l.msg); if (v) n[v]++; });
  const active = S.logLevel || "";
  $("#log-levels").innerHTML = LOG_LEVELS.map(([v, label, ic]) =>
    `<button type="button" class="lvl lvl-${v || "all"} ${active === v ? "active" : ""}" data-level="${v}">
      <i class="ti ${ic}"></i>${label}<b>${fmt(n[v])}</b></button>`).join("");
  $$("#log-levels .lvl").forEach((b) => (b.onclick = () => { S.logLevel = b.dataset.level; renderLog(); }));
}
function appendLog(e, count = true) {
  const cur = logFilter(), lvl = logLevel(e.msg);
  if (cur && e.name !== cur) return;
  if (S.logLevel && lvl !== S.logLevel) { if (count) logCount(); return; }
  const box = $("#logbox"), atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.querySelector(".log-empty")?.remove();
  if (isRunStart(e.msg) && !S.logLevel) {
    const sep = document.createElement("div");
    sep.className = "lsep";
    sep.innerHTML = `<span>${avatarHtml(e.name, "avatar-xs rounded-circle")}${esc(e.name)} · ${/kiểm tra/i.test(e.msg) ? "kiểm tra" : "lượt chạy"} ${esc(e.time.slice(0, 5))}</span>`;
    box.appendChild(sep);
  }
  const d = document.createElement("div");
  d.className = `l ${lvl}`;
  const url = (S.avatars || {})[e.name];
  d.innerHTML = `<span class="tm">${esc(e.time)}</span><i class="ti ${logKind(e.msg)} lk"></i>`
    + `<span class="nm tone-${nameTone(e.name)}">${url ? `<span class="nm-av" style="background-image:url('${url}')"></span>` : ""}${esc(e.name)}</span>`
    + `<span class="msg">${esc(e.msg)}</span>`;
  box.appendChild(d);
  if (atBottom) box.scrollTop = box.scrollHeight;
  if (count) logCount();
}
async function copyLog() {
  const cur = logFilter();
  const text = S.logs.filter((l) => !cur || l.name === cur).map((l) => `${l.time} [${l.name}] ${l.msg}`).join("\n");
  if (!text) { toast("Nhật ký đang trống"); return; }
  try { await navigator.clipboard.writeText(text); toast("Đã sao chép nhật ký"); }
  catch { // dự phòng khi clipboard API bị chặn: chọn sẵn chữ để Ctrl+C
    const r = document.createRange(); r.selectNodeContents($("#logbox"));
    const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
    toast("Đã chọn toàn bộ nhật ký, bấm Ctrl+C để sao chép");
  }
}

// ===================================================================== cài đặt
const SETTING_FIELDS = [
  ["search_delay_min", "Nghỉ ít nhất giữa 2 lượt search (giây)"],
  ["search_delay_max", "Nghỉ nhiều nhất giữa 2 lượt search (giây)"],
  ["extra_searches", "Số lượt search thêm cho chắc đủ điểm"],
  ["browse_minutes", "Thời gian browse (phút)"],
  ["history_days", "Không lặp lại câu search đã dùng trong (ngày)"],
];
function renderSettings() {
  $("#settings-form").innerHTML = `<div class="settings-grid">` + SETTING_FIELDS.map(([k, l]) =>
    `<label for="set-${k}" class="form-label m-0">${l}</label><input type="number" class="form-control" min="0" id="set-${k}" data-key="${k}" value="${esc(S.settings[k])}">`).join("")
    + `<label for="set-browser" class="form-label m-0">Trình duyệt cho cửa sổ riêng</label>
       <select id="set-browser" class="form-select">${[["msedge", "Microsoft Edge"], ["chrome", "Google Chrome"], ["", "Chromium"]]
        .map(([v, t]) => `<option value="${v}" ${S.settings.browser_channel === v ? "selected" : ""}>${t}</option>`).join("")}</select>
       </div>
       <label class="form-check form-switch mt-4 mb-0">
         <input class="form-check-input" type="checkbox" id="set-bypass-proxy" ${S.settings.bypass_proxy !== false ? "checked" : ""}>
         <span class="form-check-label">Không đi qua proxy hệ thống (chặn proxy chen giữa)</span></label>`;
  $$("#theme-choice input").forEach((i) => (i.checked = i.value === (S.settings.theme || "system")));
  $$("#lang-choice input").forEach((i) => (i.checked = i.value === (S.settings.language === "en" ? "en" : "vi")));
  const app = S.app || {};
  $("#app-version").textContent = `Phiên bản ${app.version || "?"}${app.frozen ? "" : " (mã nguồn)"}`;
  $("#set-check-updates").checked = S.settings.check_updates !== false;
}
async function saveSettingsForm() {
  const partial = { browser_channel: $("#set-browser").value };
  for (const i of $$("#settings-form input[data-key]")) {
    const v = parseInt(i.value, 10);
    if (Number.isNaN(v) || v < 0) { toast("Ô “" + i.previousElementSibling.textContent + "” cần là số không âm"); i.focus(); return; }
    partial[i.dataset.key] = v;
  }
  partial.bypass_proxy = $("#set-bypass-proxy").checked;
  partial.check_updates = $("#set-check-updates").checked;
  const ok = await saveSettings(partial);
  renderSettings();
  if (ok) toast("Đã lưu cài đặt");
}
