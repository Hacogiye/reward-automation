"use strict";
// Giao diện PrixAuto (Tabler + ApexCharts). Mọi dữ liệu đến từ Python (window.pywebview.api) và sự kiện window.onEvents.

const S = { settings: {}, profiles: [], pstate: {}, history: {}, running: new Set(),
            logs: [], unreadErr: 0, selected: null, page: "dashboard" };
const api = () => window.pywebview.api;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => (n === null || n === undefined || n === "" ? "—" : Number(n).toLocaleString("en-US"));
// màu dãy biểu đồ lấy từ biến CSS --rb-series-N (đổi theo sáng/tối); đọc lại mỗi lần vẽ nên đổi theme là có màu mới
const SERIES = [["pc", "Search PC", "--rb-series-1"], ["mobile", "Search Mobile", "--rb-series-2"], ["offers", "Offers", "--rb-series-3"]];
const cssVar = (n, fb) => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || fb;
// bảng màu biểu đồ của giao diện Cyberpunk (cyan / hồng / vàng neon)
const CYBER_COLORS = { pc: "#05d9e8", mobile: "#ff2a6d", offers: "#fcee0a", balance: "#fcee0a" };
const isCyber = () => document.documentElement.getAttribute("data-skin") === "cyberpunk";
const seriesColor = (k) => (isCyber() ? CYBER_COLORS[k] : cssVar((SERIES.find((x) => x[0] === k) || [, , "--rb-series-1"])[2], "#2563eb"));
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
// chế độ vui tắt (mặc định): chỉ icon nét Tabler. Bật: thêm ảnh 3D / SVG (CSS chọn 1 bản theo giao diện)
const isFun = () => !!S.settings.fun_mode;
const icon = (name, cls = "") => (isFun()
  ? `<span class="tico ${cls}" data-icon="${name}"><img src="${iconSrc(name)}" alt="" draggable="false"><i class="ti ${LINE_ICONS[name] || "ti-point"}"></i></span>`
  : `<span class="tico tico-line ${cls}" data-icon="${name}"><i class="ti ${LINE_ICONS[name] || "ti-point"}"></i></span>`);
const taskIcon = (t, cls = "") => icon(iconName(t), cls);
// icon riêng của app cho streak (ngọn lửa) và điểm (chồng xu): chỉ ở chế độ vui; còn lại là icon nét / không có gì
const STREAK_IMG = (cls = "") => (isFun() ? `<img class="ico-streak ${cls}" src="assets/flame.png" alt="" draggable="false">`
  : `<i class="ti ti-flame ico-streak ${cls}"></i>`);
const POINT_IMG = (cls = "") => (isFun() ? `<img class="ico-point ${cls}" src="assets/point.svg" alt="" draggable="false">` : "");

// ảnh lỗi -> ẩn đi (CSP không cho onerror nội tuyến nên bắt chung ở document)
document.addEventListener("error", (e) => { if (e.target.tagName === "IMG") e.target.classList.add("broken"); }, true);

// ===================================================================== khởi động
window.addEventListener("pywebviewready", async () => {
  const b = await api().bootstrap();
  Object.assign(S, b, { running: new Set(b.running) });
  $$(".src-only").forEach((e) => (e.hidden = !!S.app?.frozen));  // bản exe: ẩn hướng dẫn dành cho người chạy từ mã nguồn
  S.selected = S.profiles[0]?.name ?? null;
  bindStatic();
  window.Office?.init();
  applyFun(false);  // đặt chế độ vui + giao diện trước khi vẽ lần đầu
  applyLanguage();
  renderAll();
  if (!S.settings.onboarded) Welcome.open(1);
});

// ===================================================================== màn hình chào + đồng ý rủi ro
// Lần đầu mở app: chọn ngôn ngữ -> đọc và đồng ý phần rủi ro -> thêm tài khoản đầu tiên. Chưa đồng ý (risk_ack rỗng) thì
// bấm Chạy sẽ mở lại bước 2 thay vì chạy. Chỉ chặn giao diện: lệnh --run-all (Task Scheduler) vẫn chạy như cũ.
const riskOk = () => !!S.settings.risk_ack;
const Welcome = {
  step: 1,
  open(step = 1) {
    this.step = step;
    $("#wd-ack").checked = riskOk();
    this.show();
    const dlg = $("#welcome-dialog");
    if (!dlg.open) dlg.showModal();
    $("#wd-next").focus();
  },
  show() {
    $$("#welcome-dialog .wd-pane").forEach((p) => (p.hidden = +p.dataset.step !== this.step));
    $("#wd-step").textContent = `Bước ${this.step}/3`;
    $("#wd-back").hidden = this.step === 1;
    $("#wd-next").textContent = this.step === 3 ? "Xong" : "Tiếp tục";
    $("#wd-next").disabled = this.step === 2 && !$("#wd-ack").checked;
    const lang = S.settings.language === "en" ? "en" : "vi";
    $$("[data-wd-lang]").forEach((b) => {
      const on = b.dataset.wdLang === lang;
      b.classList.toggle("active", on); b.setAttribute("aria-checked", String(on));
    });
  },
  async next() {
    if (this.step === 2) {
      if (!$("#wd-ack").checked) return;
      if (!riskOk() && !(await saveSettings({ risk_ack: S.app?.version || "0.0.0" }))) return;
      if (S.settings.onboarded && S.profiles.length) { $("#welcome-dialog").close(); return; }  // mở từ nút Chạy: xong là đóng
    }
    if (this.step < 3) { this.step++; this.show(); $("#wd-next").focus(); return; }
    if (await saveSettings({ onboarded: true })) $("#welcome-dialog").close();
  },
  bind() {
    $("#wd-next").onclick = () => this.next();
    $("#wd-back").onclick = () => { this.step = Math.max(1, this.step - 1); this.show(); };
    $("#wd-ack").onchange = () => this.show();
    $$("[data-wd-lang]").forEach((b) => (b.onclick = async () => { await setLanguage(b.dataset.wdLang); this.show(); }));
    $("#wd-add").onclick = async () => {
      if (!(await saveSettings({ onboarded: true }))) return;
      $("#welcome-dialog").close();
      addFirstProfile();
    };
    $("#btn-welcome-again").onclick = () => {
      if ($("#settings-dialog").open) $("#settings-dialog").close();
      this.open(1);
    };
  },
};

// sau khi mở cửa sổ đăng nhập: nhắc 3 bước, rồi Kiểm tra (không search) và mở trang Nhật ký để xem kết quả
function openLoginHelp(name) {
  const dlg = $("#login-dialog");
  dlg.dataset.name = name;
  $("#ld-who").textContent = `Đăng nhập cho tài khoản ${name}`;
  dlg.showModal();
}
function bindLoginHelp() {
  const dlg = $("#login-dialog");
  $("#ld-check").onclick = () => {
    const name = dlg.dataset.name;
    dlg.close();
    S.selected = name; $("#log-filter").value = ""; go("log");
    start([name], "check");
  };
}

// thư mục nhật ký: Python mở data/logs bằng trình quản lý file (đường dẫn cố định, không gửi gì từ giao diện)
async function openLogFolder() {
  const r = await api().open_log_folder();
  if (r && r.ok === false) showError(r.error);
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
// lỗi của một thao tác: thanh đỏ ở đầu vùng nội dung, nằm đó đến khi người dùng đóng (toast chỉ dành cho báo thành công)
function showError(msg) {
  $("#error-text").textContent = String(msg || "Có lỗi xảy ra");
  $("#error-banner").hidden = false;
}
// khối trạng thái rỗng dùng chung: icon, một câu, một nút chính. action = {label, icon, id}; người gọi gắn onclick vào #id
const stateBlock = ({ icon: ic = "ti-inbox", title = "", text = "", action = null, cls = "" }) => `
  <div class="state-block ${cls}"><span class="state-ic"><i class="ti ${ic}"></i></span>
    <b class="state-title">${esc(title)}</b>${text ? `<span class="state-text">${esc(text)}</span>` : ""}
    ${action ? `<button type="button" class="btn btn-primary" id="${action.id}">${action.icon ? `<i class="ti ${action.icon}"></i>` : ""}${esc(action.label)}</button>` : ""}
  </div>`;
const addFirstProfile = () => { go("profiles"); openProfileDialog(null); };
// hộp xác nhận có style (thay hộp xác nhận mặc định của trình duyệt): trả về Promise<boolean>; Esc / Hủy = false
function confirmDialog({ title, text, names = [], okLabel = "Xóa" }) {
  const dlg = $("#confirm-dialog");
  $("#cd-title").textContent = title;
  $("#cd-text").textContent = text || "";
  $("#cd-names").innerHTML = names.map((n) => `<li>${esc(n)}</li>`).join("");
  $("#cd-ok").textContent = okLabel;
  dlg.returnValue = "";
  return new Promise((resolve) => {
    dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
    dlg.showModal();
    $("#cd-cancel").focus();  // mặc định rơi vào Hủy: Enter nhầm không xóa gì
  });
}

// ===================================================================== sáng / tối
const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
const isDark = () => document.documentElement.getAttribute("data-bs-theme") === "dark";
function applyTheme() {
  const mode = S.settings.theme || "system";
  // Cyberpunk chỉ có ở chế độ vui (nền tối + lớp giao diện riêng cyberpunk.css); tắt chế độ vui thì hiện như "Tối"
  // mà không ghi đè giá trị đã lưu, bật lại là có skin trở lại
  const cyber = mode === "cyberpunk" && isFun();
  const shown = mode === "cyberpunk" && !cyber ? "dark" : mode;
  const dark = cyber || shown === "dark" || (shown === "system" && darkQuery.matches);
  const changed = isDark() !== dark || isCyber() !== cyber;
  document.documentElement.setAttribute("data-bs-theme", dark ? "dark" : "light");
  if (cyber) document.documentElement.setAttribute("data-skin", "cyberpunk");
  else document.documentElement.removeAttribute("data-skin");
  $$("#theme-choice input").forEach((i) => (i.checked = i.value === shown));
  if (changed && S.page === "dashboard") { Charts.reset(); renderDashboard(); }
}
async function setFunMode(on) {
  S.settings.fun_mode = on; applyFun();  // đổi ngay, lưu sau
  await saveSettings({ fun_mode: on });
}
async function setTheme(mode) {
  S.settings.theme = mode; applyTheme();  // đổi ngay, lưu sau
  await saveSettings({ theme: mode });
}
darkQuery.addEventListener("change", () => (S.settings.theme || "system") === "system" && applyTheme());

// ===================================================================== chế độ vui
// Tắt (mặc định): giao diện gọn, icon nét, không có trang Văn phòng và skin Cyberpunk. Đổi là áp ngay, không cần tải lại.
function applyFun(rerender = true) {
  const fun = isFun();
  document.documentElement.setAttribute("data-fun", fun ? "on" : "off");
  $$("[data-fun-only]").forEach((e) => (e.hidden = !fun));
  $("#set-fun-mode").checked = fun;
  window.Office?.setFun(fun);  // tắt chế độ vui thì dừng nhạc lofi
  // tắt chế độ vui: Lịch nhiệt + Nguồn điểm vào mục "Thêm biểu đồ" gập sẵn; bật lại thì về vị trí cũ trong lưới
  const heat = $("#heat-col"), src = $("#sources-col"), more = $("#more-charts-body > .row");
  if (fun) $("#compare-panel").before(heat, src); else more.append(heat, src);
  $("#more-charts").hidden = fun;
  applyTheme();
  if (!rerender) return;
  if (!fun) {
    const sd = $("#settings-dialog");
    if (sd.open) sd.close();  // hộp Cài đặt mở từ trang Văn phòng: đóng (sự kiện close trả khối cài đặt về trang Cài đặt)
  }
  if (!fun && S.page === "office") { go("dashboard"); return; }
  Charts.reset();
  renderAll();
}

// ===================================================================== điều hướng + nút cố định
// ===================================================================== ngôn ngữ (i18n.js dịch giao diện sang English)
function applyLanguage() {
  const lang = S.settings.language === "en" ? "en" : "vi";
  I18N.apply(lang);
  $$(".lang-switch button").forEach((b) => {
    b.classList.toggle("active", b.dataset.setLang === lang);
    b.setAttribute("aria-checked", String(b.dataset.setLang === lang));
  });
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
  $("#btn-open-logs").onclick = $("#btn-open-logs-about").onclick = openLogFolder;
  $$("#nav [data-page]").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); go(b.dataset.page); }));
  $("#side-toggle").onclick = () => setSideCollapsed(!document.documentElement.classList.contains("side-collapsed"));
  syncSide();
  // nội dung rộng / hẹp theo thanh bên: báo cho biểu đồ ApexCharts (chỉ tự co giãn khi cửa sổ đổi cỡ)
  $(".page-wrapper").addEventListener("transitionend", (e) => {
    if (e.target === e.currentTarget && e.propertyName === "margin-left") window.dispatchEvent(new Event("resize"));
  });
  $$("#theme-choice input").forEach((i) => (i.onchange = () => setTheme(i.value)));
  $("#set-fun-mode").onchange = (e) => setFunMode(e.target.checked);
  $("#error-dismiss").onclick = () => ($("#error-banner").hidden = true);
  $("#more-charts-body").addEventListener("shown.bs.collapse", () => { Charts.reset(); renderDashboard(); });  // biểu đồ trong khối đang gập chưa có kích thước thật
  document.addEventListener("hidden.bs.dropdown", () => { if (renderProfiles._defer) { renderProfiles._defer = false; if (S.page === "profiles") renderProfiles(); } });
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
  bindSettingsDialog();
  $("#max-parallel").onchange = (e) => saveSettings({ max_parallel: Math.max(1, +e.target.value || 1) });
  bindProfileDialog();
  bindGoalDialog();
  Welcome.bind();
  bindLoginHelp();
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
  const all = [...b.parentElement.querySelectorAll("button:not([hidden])")];  // bỏ nút đang ẩn (Cyberpunk khi tắt chế độ vui)
  return all[(all.indexOf(b) + 1) % all.length].dataset[key];
}
function syncSide() {
  const on = document.documentElement.classList.contains("side-collapsed"), t = $("#side-toggle");
  const label = on ? "Mở rộng thanh bên" : "Thu gọn thanh bên";
  t.title = on ? label : ""; t.setAttribute("aria-label", label); t.setAttribute("aria-expanded", String(!on));
  $$(".lang-switch button").forEach((b) => {  // gợi ý "bấm để đổi" khi chỉ còn 1 nút
    if (!b.dataset.tip) b.dataset.tip = b.title || b.textContent.trim();
    b.title = on ? `${b.dataset.tip} (bấm để đổi)` : b.dataset.tip;
  });
  t.querySelector("i").className = "ti " + (on ? "ti-layout-sidebar-left-expand" : "ti-layout-sidebar-left-collapse");
  $$("#nav .nav-link").forEach((a) => { a.title = on ? a.querySelector(".nav-link-title").textContent.trim() : ""; });
  $("#run-state").title = on ? $("#run-state span:last-child").textContent : "";
}

function go(page) {
  if (page === "office" && !isFun()) page = "dashboard";  // trang Văn phòng chỉ có ở chế độ vui
  S.page = page;
  $$("#nav [data-page]").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  $$(".view").forEach((p) => (p.hidden = p.id !== "page-" + page));
  if (page === "log") S.unreadErr = 0;
  if (page === "dashboard") Charts.reset();  // vẽ lại theo kích thước thật sau khi trang hiện ra
  renderAll();
  window.scrollTo(0, 0);
}

async function start(names, action) {
  if ((action === "run" || action === "everything") && !riskOk()) { Welcome.open(2); return; }
  const r = await api().start(names, action);
  if (r.ok === false) { showError(r.error); return; }
  if (action === "login" && names?.length === 1) openLoginHelp(names[0]);
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
  $("#side-version").textContent = S.app?.version ? "v" + S.app.version : "";
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
  const none = !S.profiles.length;
  $("#dash-main").hidden = none;
  $("#dash-empty").hidden = !none;
  if (none) {  // chưa có tài khoản: một khối hướng dẫn thay cho cả trang toàn dấu gạch
    chips.innerHTML = "";
    for (const id of ["#btn-run-one", "#btn-refresh"]) $(id).disabled = true;
    Charts.reset();
    $("#dash-empty").innerHTML = stateBlock({ icon: "ti-user-plus", title: "Chưa có tài khoản",
      text: "Thêm một tài khoản Microsoft, đăng nhập một lần rồi bot sẽ làm việc thay bạn.",
      action: { id: "btn-first-profile", icon: "ti-user-plus", label: "Thêm tài khoản đầu tiên" } });
    $("#btn-first-profile").onclick = addFirstProfile;
    return;
  }
  chips.innerHTML = S.profiles.map((p) => `
      <button type="button" class="chip ${p.name === S.selected ? "active" : ""}" data-name="${esc(p.name)}" aria-pressed="${p.name === S.selected}">
        ${avatarHtml(p.name, `avatar-sm rounded-circle ${S.running.has(p.name) ? "run" : ""}`)}
        <span>${esc(p.name)}</span><span class="pts">${POINT_IMG()}${fmt(st(p.name).points)}</span>
      </button>`).join("");
  $$(".chip", chips).forEach((c) => (c.onclick = () => { S.selected = c.dataset.name; Charts.reset(); renderDashboard(); }));
  const name = S.selected;
  const s = st(name);
  const stats = s.stats || {};
  const heroUrl = name && (S.avatars || {})[name];
  $("#hero-avatar").textContent = name && !heroUrl ? initials(name) : "";
  $("#hero-avatar").style.backgroundImage = heroUrl ? `url('${heroUrl}')` : "";
  $("#hero-avatar").classList.toggle("has-img", !!heroUrl);
  $("#hero-coin").innerHTML = POINT_IMG("hero-coin-img");
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
  const box = $("#stamps"), fun = isFun();
  $("#stamp-title").innerHTML = fun ? `<i class="ti ti-rosette-discount-check me-2 text-yellow"></i>Thẻ đóng dấu hôm nay`
    : `<i class="ti ti-checklist me-2"></i>Tiến độ hôm nay`;
  box.className = fun ? "stamps" : "plist";
  if (!tasks.length) {
    box.innerHTML = `<p class="empty-note w-100">Chưa có dữ liệu. Bấm <b>Làm mới</b> để đọc task hôm nay từ Rewards.</p>`;
    $("#stamp-count").textContent = "";
    return;
  }
  if (!fun) {
    // gọn: mỗi việc một dòng (icon, tên, +điểm, dấu xong hoặc N/M). Search PC / Mobile đã có thanh tiến độ ngay bên dưới nên không lặp
    const list = tasks.filter((t) => t.group !== "Tìm kiếm");
    $("#stamp-count").textContent = `${list.filter((t) => t.done).length}/${list.length} xong`;
    box.innerHTML = list.map((t) => `
      <div class="prow ${t.done ? "done" : ""}" title="${esc(t.title)}">
        <span class="ticon">${taskIcon(t)}</span><span class="pname">${esc(t.title)}</span>
        <span class="pts">+${fmt(t.max)} điểm</span>
        <span class="pstat">${t.done ? '<i class="ti ti-circle-check" aria-label="Đã xong"></i>' : `${fmt(t.progress)}/${fmt(t.max)}`}</span>
      </div>`).join("");
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
  const left = Math.max(0, max - have), fun = isFun();
  $("#streak-title").innerHTML = `${STREAK_IMG("me-2")}Streak &amp; Stamp bonus`;
  $("#streak-panel").classList.toggle("streak-plain", !fun);
  const grid = $("#stamp-grid");
  grid.classList.toggle("stampbar", !fun);
  if (!fun) {
    // gọn: một dòng daily streak, một thanh "x/12" cho Stamp bonus, mỗi streak một dòng với thanh 7 đoạn
    $("#streak-sub").textContent = "";
    $("#daily-streak").innerHTML = info.daily_streak != null
      ? `<i class="ti ti-flame"></i><span class="ds-label">Daily streak liên tiếp</span><b>${fmt(info.daily_streak)} ngày</b>` : "";
    grid.setAttribute("role", "progressbar");
    grid.setAttribute("aria-valuemin", "0"); grid.setAttribute("aria-valuemax", String(max)); grid.setAttribute("aria-valuenow", String(have));
    grid.setAttribute("aria-label", "Stamp bonus");
    grid.innerHTML = `<div class="sbonus-head"><span>Stamp bonus</span><b>${have}/${max}</b></div>${bar(max ? (have / max) * 100 : 0)}`;
  } else {
    $("#streak-sub").textContent = stamps ? `${have}/${max} dấu` : "";
    $("#daily-streak").innerHTML = info.daily_streak != null
      ? `<span class="flame">${STREAK_IMG()}</span><div><b>${fmt(info.daily_streak)} ngày</b><span>Daily streak liên tiếp</span></div>` : "";
    grid.setAttribute("role", "img");
    for (const a of ["aria-valuemin", "aria-valuemax", "aria-valuenow"]) grid.removeAttribute(a);
    grid.setAttribute("aria-label", `${have} trên ${max} dấu`);
    grid.innerHTML = Array.from({ length: max }, (_, i) =>
      `<span class="sdot ${i < have ? "on" : i === have ? "next" : ""}"><i class="ti ${i < have ? "ti-star-filled" : "ti-star"}"></i></span>`).join("");
  }
  $("#streak-hint").innerHTML = !stamps ? "Chưa đọc được số dấu."
    : left ? `Còn <b>${left}</b> dấu nữa để nhận <b>+${fmt(bonus)}</b> điểm. Giữ các chuỗi streak bên cạnh mỗi ngày để nhận dấu.`
    : `Đã đủ ${max} dấu: vào Rewards để nhận <b>+${fmt(bonus)}</b> điểm.`;
  $("#streak-list").innerHTML = streaks.map((r) => {
    if (!fun) {
      const n = r.of || 7, day = Math.max(0, Math.min(r.day, n)), todayIdx = r.today_done ? day - 1 : day;
      const segs = Array.from({ length: n }, (_, i) => `<span class="seg ${i < day ? "on" : ""} ${i === todayIdx ? "today" : ""}"></span>`).join("");
      const status = r.today_done ? `<span class="badge bg-green-lt">Hôm nay xong</span>`
        : `<span class="badge bg-yellow-lt">Hôm nay chưa${r.today ? " · " + esc(r.today) : ""}</span>`;
      return `<div class="srow" title="${esc(r.title)}${r.next ? ` · ngày tới +${r.next} điểm` : ""}">${taskIcon(r)}
        <span class="sname">${esc(r.title)}</span><span class="sub">Ngày ${r.day}/${n}</span>
        <span class="segbar" role="img" aria-label="${day} trên ${n} ngày">${segs}</span>${status}</div>`;
    }
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
  const el = $("#" + id);
  el.innerHTML = `<div class="empty">${msg}</div>`;
  el.removeAttribute("role"); el.removeAttribute("aria-label");
}
// biểu đồ là hình: trình đọc màn hình đọc câu tóm tắt này thay cho các cột / đường bên trong
function chartLabel(id, text) {
  const el = $("#" + id);
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", text);
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
  if (d14.length) {
    const total = d14.reduce((a, d) => a + SERIES.reduce((b, [k]) => b + (hist[d][k] || 0), 0), 0);
    chartLabel("chart-daily", `Điểm mỗi ngày trong ${d14.length} ngày gần nhất, tổng ${fmt(total)} điểm`);
  }
  const d30 = days.slice(-30).filter((d) => hist[d].available != null);
  if (d30.length) chartLabel("chart-balance", `Số điểm trong ${d30.length} ngày: từ ${fmt(hist[d30[0]].available)} đến ${fmt(hist[d30[d30.length - 1]].available)}`);
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
    tile(isFun() ? POINT_IMG() : "ti-coin", "Hôm nay", s.today != null ? "+" + fmt(s.today) : "—", pcLine),
    tile("ti-chart-line", "Trung bình 7 ngày", k.avg7 != null ? fmt(k.avg7) : "—",
      k.avgDays ? `điểm/ngày, tính trên ${k.avgDays} ngày có số liệu` : "chưa có lịch sử"),
    tile(isFun() ? STREAK_IMG() : "ti-flame", "Chuỗi đủ điểm search", `${k.streak} ngày`, searchFull(h) ? "hôm nay đã đủ PC + Mobile" : "hôm nay chưa đủ PC + Mobile",
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
  if (sums.some(Boolean)) chartLabel("chart-sources", `Nguồn điểm 30 ngày, tổng ${fmt(sums.reduce((a, b) => a + b, 0))} điểm`);
  if (!$("#chart-sources").clientWidth) { /* khối đang gập: vẽ khi mở ra (shown.bs.collapse) */ }
  else if (!sums.some(Boolean)) emptyChart("chart-sources", "Chưa có số liệu điểm search / thẻ.");
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
    const palette = isCyber() ? ["#05d9e8", "#fcee0a", "#ff2a6d", "#b892ff", "#3dff9a"] : [1, 2, 3, 4, 5].map((i) => cssVar("--rb-series-" + i, "#2563eb"));
    chartLabel("chart-compare", `So sánh điểm mỗi ngày của ${names.length} tài khoản trong 14 ngày`);
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
  if ($(".dropdown-menu.show", tb)) { renderProfiles._defer = true; return; }  // đang mở menu thao tác: vẽ lại sau khi đóng
  if (!S.profiles.length) {
    tb.innerHTML = `<tr><td colspan="8">${stateBlock({ icon: "ti-users", title: "Chưa có tài khoản",
      text: "Thêm tài khoản, bấm Đăng nhập một lần rồi chạy.",
      action: { id: "btn-empty-add", icon: "ti-user-plus", label: "Thêm tài khoản" } })}</td></tr>`;
    $("#btn-empty-add").onclick = () => openProfileDialog(null);
  } else {
    const ib = (act, icon, label, cls = "") => `<button class="btn btn-sm ${cls}" data-act="${act}" title="${label}"><i class="ti ${icon}"></i>${label}</button>`;
    const mi = (act, icon, label, cls = "") => `<li><button type="button" class="dropdown-item ${cls}" data-act="${act}"><i class="ti ${icon}"></i>${label}</button></li>`;
    // Chạy là nút chính; các thao tác còn lại nằm trong menu ba chấm (Bootstrap dropdown: Enter mở, mũi tên chọn, Esc đóng)
    const more = `<div class="dropdown"><button type="button" class="btn btn-sm btn-icon btn-more" data-bs-toggle="dropdown" data-bs-popper-config='{"strategy":"fixed"}'
        aria-expanded="false" aria-haspopup="true" aria-label="Thêm thao tác" title="Thêm thao tác"><i class="ti ti-dots-vertical"></i></button>
      <ul class="dropdown-menu dropdown-menu-end">${mi("check", "ti-stethoscope", "Kiểm tra") + mi("login", "ti-login", "Đăng nhập")
        + mi("edit", "ti-pencil", "Sửa") + `<li><hr class="dropdown-divider"></li>` + mi("del", "ti-trash", "Xóa", "text-danger")}</ul></div>`;
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
          ${run ? ib("stop", "ti-player-stop-filled", "Dừng", "btn-run btn-run-stop") : ib("run", "ti-player-play-filled", "Chạy", "btn-primary btn-run") + more}
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
      else if (act === "del") {
        const ok = await confirmDialog({ title: "Xóa tài khoản?", names: [name], okLabel: "Xóa",
          text: "Tài khoản sẽ bị xóa khỏi app. Phiên đăng nhập trong data/profiles vẫn được giữ." });
        if (!ok) return;
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
    ["do_checkin", "Check-in app điện thoại", "Check-in app điện thoại mỗi ngày (Bing App Streak), gọi thẳng API của app", "mobile"],
    ["do_read_earn", "Read to Earn", "Đọc tối đa 10 bài báo mỗi ngày (3 điểm/bài), gọi thẳng API của app", "news"],
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
  if (!r.ok) showError(r.error);
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
  $("#history-range").onchange = renderHistory;
  const range = parseInt($("#history-range").value, 10) || 30;
  const rows = [];
  for (const [name, days] of Object.entries(S.history || {})) {
    if (cur && name !== cur) continue;
    for (const [day, h] of Object.entries(days || {})) rows.push({ name, day, h: h || {} });
  }
  rows.sort((a, b) => b.day.localeCompare(a.day) || a.name.localeCompare(b.name));
  const cutoff = new Date(Date.now() - range * 864e5).toISOString().slice(0, 10);
  const shown = rows.filter((r) => r.day >= cutoff);
  $("#history-sub").textContent = `${range} ngày gần nhất`;
  renderHistoryKpis(shown);
  const tb = $("#history-table tbody");
  if (!shown.length) {
    tb.innerHTML = `<tr><td colspan="7">${stateBlock({ icon: "ti-calendar-stats", title: "Chưa có lịch sử",
      text: "Mỗi lần chạy hoặc làm mới sẽ ghi lại số liệu của ngày đó.",
      action: { id: "btn-history-go", icon: "ti-users", label: "Đến trang Tài khoản" } })}</td></tr>`;
    $("#btn-history-go").onclick = () => go("profiles");
    return;
  }
  // ô search: số + thanh mảnh; xanh khi đủ, vàng khi thiếu
  const search = (p, m) => (m ? `<div class="hs-cell"><span class="hs ${p >= m ? "full" : "short"}">${fmt(p)}/${fmt(m)}</span>`
    + `<span class="hs-bar ${p >= m ? "full" : "short"}"><span style="width:${Math.min(100, (100 * (p || 0)) / m).toFixed(0)}%"></span></span></div>`
    : `<span class="text-secondary">—</span>`);
  tb.innerHTML = shown.map(({ name, day, h }) => {
    const d = new Date(day + "T00:00:00");
    const miss = (h.missing || []).filter((x) => x.g !== "Tìm kiếm");  // PC/Mobile đã có cột riêng
    const missCell = h.missing == null ? `<span class="text-secondary">—</span>`
      : miss.length ? miss.map((x) => `<span class="badge bg-yellow-lt me-1 mb-1" title="${esc(x.g)}">${esc(x.t)}${x.m ? ` ${fmt(x.p ?? 0)}/${fmt(x.m)}` : ""}</span>`).join("")
      : `<span class="badge bg-green-lt">Đủ hết</span>`;
    return `<tr>
      <td class="text-nowrap"><b>${day.slice(8, 10)}/${day.slice(5, 7)}</b> <span class="text-secondary">${WEEKDAYS[d.getDay()]}</span></td>
      <td><span class="d-inline-flex align-items-center gap-2">${avatarHtml(name, "avatar-xs rounded-circle")}<span class="fw-medium">${esc(name)}</span></span></td>
      <td class="text-end"><b>${h.today != null ? "+" + fmt(h.today) : "—"}</b></td>
      <td>${search(h.pc, h.pc_max)}</td>
      <td>${search(h.mobile, h.mobile_max)}</td>
      <td class="text-end">${h.offers != null ? "+" + fmt(h.offers) : "—"}</td>
      <td class="history-miss">${missCell}</td></tr>`;
  }).join("");
}

// 4 ô tổng kết trên bảng lịch sử, theo tài khoản và khoảng ngày đang chọn
function renderHistoryKpis(rows) {
  const days = new Set(rows.map((r) => r.day)).size;
  const total = rows.reduce((a, r) => a + (r.h.today || 0), 0);
  const withPts = rows.filter((r) => r.h.today != null);
  const avg = withPts.length ? Math.round(total / withPts.length) : null;
  const full = rows.filter((r) => r.h.pc_max && r.h.pc >= r.h.pc_max && (!r.h.mobile_max || r.h.mobile >= r.h.mobile_max)).length;
  const withSearch = rows.filter((r) => r.h.pc_max).length;
  const kpi = (ic, label, val, sub) => `<div class="kpi"><span class="kpi-ic"><i class="ti ${ic}"></i></span>
    <div class="min-w-0"><div class="kpi-label">${label}</div><div class="kpi-value">${val}</div>${sub ? `<div class="kpi-sub">${sub}</div>` : ""}</div></div>`;
  $("#history-kpis").innerHTML = kpi("ti-calendar", "Ngày có số liệu", fmt(days), "")
    + kpi("ti-sum", "Tổng điểm kiếm được", total ? "+" + fmt(total) : "—", "")
    + kpi("ti-chart-line", "Trung bình mỗi tài khoản/ngày", avg != null ? "+" + fmt(avg) : "—", "")
    + kpi("ti-circle-check", "Ngày đủ điểm search", withSearch ? `${fmt(full)}/${fmt(withSearch)}` : "—", "PC và Mobile");
}

// ===================================================================== nhật ký
const logFilter = () => $("#log-filter").value;
const LOG_LEVELS = [["", "Tất cả", "ti-list"], ["er", "Lỗi", "ti-alert-octagon"], ["warn", "Cảnh báo", "ti-alert-triangle"],
                    ["ok", "Xong", "ti-circle-check"]];
const logEmpty = () => stateBlock({ cls: "log-empty", icon: "ti-terminal-2", title: "Chưa có nhật ký",
  text: "Chạy hoặc kiểm tra một tài khoản, từng bước bot làm sẽ hiện ở đây.",
  action: { id: "btn-log-go", icon: "ti-users", label: "Đến trang Tài khoản" } });
function renderLog() {
  const sel = $("#log-filter"), cur = sel.value || "";
  sel.innerHTML = `<option value="">Tất cả tài khoản</option>` + S.profiles.map((p) => `<option ${p.name === cur ? "selected" : ""}>${esc(p.name)}</option>`).join("");
  $("#log-search").oninput = (ev) => { S.logQuery = ev.target.value.trim().toLowerCase(); renderLog(); };
  const box = $("#logbox"); box.innerHTML = "";
  S.logs.filter((l) => !cur || l.name === cur).slice(-1500).forEach((l) => appendLog(l, false));
  if (!box.children.length) {
    if (S.logQuery || S.logLevel) box.innerHTML = stateBlock({ cls: "log-empty", icon: "ti-search-off", title: "Không có dòng nào khớp",
      text: "Thử từ khóa khác hoặc chọn lại mức lọc." });
    else { box.innerHTML = logEmpty(); $("#btn-log-go").onclick = () => go("profiles"); }
  }
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
  if (S.logQuery && !`${e.name} ${e.msg}`.toLowerCase().includes(S.logQuery)) { if (count) logCount(); return; }
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
// Mỗi nhóm là một card; mỗi dòng: [khóa, nhãn, đơn vị, giải thích, min, max] cho ô số,
// {sw: khóa, label, hint} cho công tắc, {select: "browser"} cho ô chọn trình duyệt.
// Khóa nào có ở đây thì saveSettingsForm gửi đi (phải có trong SETTING_SCHEMA của webapp.py).
const SETTING_GROUPS = [
  ["Search", "ti-search", [
    ["search_delay_min", "Nghỉ ít nhất giữa 2 lượt search", "giây", "Bot chờ một khoảng ngẫu nhiên giữa mức ít nhất và nhiều nhất.", 1, 600],
    ["search_delay_max", "Nghỉ nhiều nhất giữa 2 lượt search", "giây", "", 1, 600],
    ["extra_searches", "Số lượt search thêm", "lượt", "Search thêm vài lượt sau khi đủ điểm, phòng khi Rewards cập nhật chậm.", 0, 20],
    ["stall_after", "Dừng khi không được cộng điểm sau", "lượt", "Số lượt liên tiếp không lên điểm thì dừng loại search đó và ghi lý do vào nhật ký.", 3, 30],
    ["history_days", "Không lặp lại câu search trong", "ngày", "Câu đã dùng không được dùng lại trong khoảng này, ở mọi tài khoản.", 0, 365],
  ]],
  ["Hành vi giống người dùng", "ti-hand-click", [
    { sw: "search_browse", label: "Lướt trang kết quả trong lúc chờ", hint: "Cuộn đọc trang kết quả và thỉnh thoảng mở một kết quả, trong đúng thời gian nghỉ giữa 2 lượt search." },
    ["search_click_pct", "Tỉ lệ lượt search có mở một kết quả", "%", "Bỏ qua quảng cáo và link tải file.", 0, 100],
  ]],
  ["Task", "ti-checklist", [
    ["browse_minutes", "Thời gian Browse tối đa", "phút", "Thời gian lướt web cho Edge – Minutes trong một lượt chạy.", 1, 240],
    ["visual_max_tries", "Số lần thử Visual Search mỗi ngày", "lần", "Bing chặn khi một tài khoản thử quá nhiều lần trong ngày.", 1, 10],
  ]],
  ["Trình duyệt", "ti-browser", [
    { select: "browser" },
    { sw: "bypass_proxy", label: "Không đi qua proxy hệ thống", hint: "Chặn proxy chen giữa. Tắt nếu mạng của bạn bắt buộc đi qua proxy." },
  ]],
  ["Dữ liệu", "ti-database", [
    ["log_keep_days", "Giữ file nhật ký", "ngày", "File cũ hơn trong data/logs tự xóa khi bot chạy.", 1, 90],
  ]],
];
const BROWSERS = [["msedge", "Microsoft Edge"], ["chrome", "Google Chrome"], ["", "Chromium"]];
function settingRow(f) {
  const v = S.settings;
  const text = (id, label, hint) => `<div class="set-text"><label class="set-label" for="${id}">${label}</label>${hint ? `<div class="set-hint">${hint}</div>` : ""}</div>`;
  if (f.sw) {
    const id = "set-" + f.sw.replace(/_/g, "-");
    return `<div class="set-row">${text(id, f.label, f.hint)}<div class="set-ctl"><label class="form-check form-switch m-0">
      <input class="form-check-input" type="checkbox" id="${id}" data-sw="${f.sw}" ${v[f.sw] !== false ? "checked" : ""}></label></div></div>`;
  }
  if (f.select) {
    return `<div class="set-row">${text("set-browser", "Trình duyệt cho cửa sổ riêng", "Trình duyệt bot mở cho mỗi tài khoản. Nên dùng Edge.")}
      <div class="set-ctl"><select id="set-browser" class="form-select">${BROWSERS.map(([val, t]) =>
        `<option value="${val}" ${v.browser_channel === val ? "selected" : ""}>${t}</option>`).join("")}</select></div></div>`;
  }
  const [k, label, unit, hint, min, max] = f;
  return `<div class="set-row">${text("set-" + k, label, hint)}<div class="set-ctl"><div class="input-group">
    <input type="number" class="form-control" id="set-${k}" data-key="${k}" min="${min}" max="${max}" value="${esc(v[k] ?? "")}">
    <span class="input-group-text">${unit}</span></div></div></div>`;
}
function renderSettings() {
  $("#settings-form").innerHTML = SETTING_GROUPS.map(([title, ic, rows]) =>
    `<div class="card"><div class="card-header"><h3 class="card-title"><i class="ti ${ic} me-2"></i>${title}</h3></div>
      <div class="set-list">${rows.map(settingRow).join("")}</div></div>`).join("");
  const th = S.settings.theme || "system";
  $$("#theme-choice input").forEach((i) => (i.checked = i.value === (th === "cyberpunk" && !isFun() ? "dark" : th)));
  $("#set-fun-mode").checked = isFun();
  $$("#lang-choice input").forEach((i) => (i.checked = i.value === (S.settings.language === "en" ? "en" : "vi")));
  const app = S.app || {};
  $("#app-version").textContent = `Phiên bản ${app.version || "?"}${app.frozen ? "" : " (mã nguồn)"}`;
  $("#about-data").textContent = app.data_dir || "data";
}
async function saveSettingsForm() {
  const partial = { browser_channel: $("#set-browser").value };
  for (const i of $$("#settings-form input[data-key]")) {
    const v = parseInt(i.value, 10), min = +i.min, max = +i.max;
    if (Number.isNaN(v) || v < min || v > max) {
      const label = i.closest(".set-row")?.querySelector(".set-label")?.textContent || i.dataset.key;
      showError(`“${label}” cần là số từ ${min} đến ${max}`); i.focus(); return false;
    }
    partial[i.dataset.key] = v;
  }
  for (const c of $$("#settings-form input[data-sw]")) partial[c.dataset.sw] = c.checked;
  const ok = await saveSettings(partial);
  renderSettings();
  if (ok) toast("Đã lưu cài đặt");
  return ok;
}
// Cài đặt ngay trên trang Văn phòng: mượn nguyên khối cài đặt (#settings-cards) đặt vào hộp thoại, đóng thì trả về trang Cài đặt.
// Không nhân đôi form nên mọi id / sự kiện (giao diện, ngôn ngữ, cập nhật) vẫn là một.
function openSettingsDialog() {
  const dlg = $("#settings-dialog");
  $("#sd-body").appendChild($("#settings-cards"));
  renderSettings();
  dlg.showModal();
}
function bindSettingsDialog() {
  const dlg = $("#settings-dialog");
  $("#office-settings").onclick = openSettingsDialog;
  $("#sd-close").onclick = $("#sd-cancel").onclick = () => dlg.close();
  $("#sd-save").onclick = async () => { if (await saveSettingsForm()) dlg.close(); };
  dlg.addEventListener("close", () => $("#settings-home").appendChild($("#settings-cards")));
}
