"use strict";
// Trang "Văn phòng": mỗi tài khoản là một con robot có bàn làm việc riêng. Robot làm gì là theo trạng thái thật của bot
// (S.pstate / S.running trong app.js): search PC thì gõ phím, Mobile thì cầm điện thoại, xong thì ra sofa uống cà phê...
// Mọi hình đều vẽ pixel bằng canvas, nhạc lofi tự sinh bằng Web Audio: không có file ảnh / nhạc ngoài (CSP chỉ cho 'self').

// ===================================================================== nhạc lofi tự sinh
const Lofi = (() => {
  const BPM = 72, BEAT = 60 / BPM, STEP = BEAT / 4;  // 1 step = nốt móc kép
  // [nốt bass, các nốt hợp âm] theo số MIDI; vòng hòa âm jazz nhẹ kiểu lofi
  const PROGS = [
    [[38, [53, 57, 60, 64]], [43, [53, 59, 62, 65]], [36, [52, 55, 59, 62]], [45, [55, 60, 64, 67]]],  // Dm9 G7 Cmaj9 Am7
    [[41, [52, 57, 60, 64]], [40, [50, 55, 59, 62]], [38, [53, 57, 60, 64]], [43, [53, 57, 59, 64]]],  // Fmaj7 Em7 Dm9 G13
    [[45, [55, 59, 60, 64]], [41, [55, 57, 60, 64]], [36, [52, 55, 59, 62]], [43, [50, 55, 57, 62]]],  // Am9 Fmaj9 Cmaj7 G6/9
  ];
  const MELODY = [72, 74, 76, 79, 81, 84];  // ngũ cung Đô trưởng
  const hz = (m) => 440 * 2 ** ((m - 69) / 12);
  let ctx = null, master, music, drums, wow, rainGain, crackleGain, noiseBuf, timer = 0;
  let on = false, rain = false, vol = 0.6, step = 0, bar = 0, nextTime = 0, t0 = 0, prog = PROGS[0], lastNote = 2;

  function buffer(seconds, fill) {
    const b = ctx.createBuffer(1, Math.floor(ctx.sampleRate * seconds), ctx.sampleRate), d = b.getChannelData(0);
    fill(d);
    return b;
  }
  function loop(buf, ...chain) {
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true;
    let node = src;
    for (const n of chain) { node.connect(n); node = n; }
    src.start();
    return node;
  }
  function filter(type, freq, q = 0.7) {
    const f = ctx.createBiquadFilter();
    f.type = type; f.frequency.value = freq; f.Q.value = q;
    return f;
  }
  function gain(v) { const g = ctx.createGain(); g.gain.value = v; return g; }

  function init() {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = gain(0);
    const comp = ctx.createDynamicsCompressor();
    master.connect(filter("lowpass", 5200)).connect(comp).connect(ctx.destination);
    music = gain(0.8); music.connect(master);
    drums = gain(0.9); drums.connect(filter("lowpass", 3400)).connect(master);  // trống "bụi" kiểu băng cassette
    const lfo = ctx.createOscillator();  // băng cassette chạy hơi lệch tốc độ (wow) -> phím đàn hơi chao
    lfo.frequency.value = 0.33; wow = gain(6); lfo.connect(wow); lfo.start();
    noiseBuf = buffer(2, (d) => { for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; });
    const crackle = buffer(5, (d) => {  // tiếng lách tách của đĩa than + chút xì nền
      for (let i = 0; i < d.length; i++) d[i] = Math.random() < 0.0005 ? (Math.random() * 2 - 1) * 0.8 : (Math.random() * 2 - 1) * 0.01;
    });
    crackleGain = gain(0.35);
    loop(crackle, filter("highpass", 900), crackleGain).connect(master);
    const brown = buffer(6, (d) => {  // tiếng mưa: nhiễu nâu lọc dải
      let b = 0;
      for (let i = 0; i < d.length; i++) { b = (b + 0.02 * (Math.random() * 2 - 1)) / 1.02; d[i] = b * 3.5; }
    });
    rainGain = gain(rain ? 0.5 : 0);
    loop(brown, filter("highpass", 250), filter("lowpass", 1600), rainGain).connect(master);
  }

  function keys(m, t, dur, vel) {  // tiếng phím điện (Rhodes giả): tam giác + sin lệch nhẹ, lọc thấp dần
    const a = ctx.createOscillator(), b = ctx.createOscillator(), g = ctx.createGain(), f = ctx.createBiquadFilter();
    a.type = "triangle"; b.type = "sine";
    a.frequency.value = b.frequency.value = hz(m); b.detune.value = 7;
    wow.connect(a.detune); wow.connect(b.detune);
    f.type = "lowpass";
    f.frequency.setValueAtTime(2400, t); f.frequency.exponentialRampToValueAtTime(600, t + dur + 0.3);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(vel, t + 0.012);
    g.gain.exponentialRampToValueAtTime(vel * 0.3, t + Math.max(0.25, dur * 0.6));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur + 0.5);
    a.connect(f); b.connect(f); f.connect(g); g.connect(music);
    for (const o of [a, b]) { o.start(t); o.stop(t + dur + 0.6); }
    a.onended = () => { try { wow.disconnect(a.detune); wow.disconnect(b.detune); } catch { /* đã tách */ } };
  }
  function bass(m, t, dur, vel) {
    const o = ctx.createOscillator(), g = ctx.createGain(), f = filter("lowpass", 420);
    o.type = "triangle"; o.frequency.value = hz(m);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vel, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(f).connect(g).connect(music);
    o.start(t); o.stop(t + dur + 0.05);
  }
  function lead(m, t, dur, vel) {  // giai điệu: sin có rung nhẹ, như tiếng sáo xa
    const o = ctx.createOscillator(), g = ctx.createGain(), vib = ctx.createOscillator(), vg = gain(9);
    o.type = "sine"; o.frequency.value = hz(m);
    vib.frequency.value = 5; vib.connect(vg).connect(o.detune);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vel, t + 0.06);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(music);
    for (const x of [o, vib]) { x.start(t); x.stop(t + dur + 0.05); }
  }
  function noise(t, dur, vel, type, freq) {
    const src = ctx.createBufferSource(), g = ctx.createGain();
    src.buffer = noiseBuf;
    g.gain.setValueAtTime(vel, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(filter(type, freq, type === "bandpass" ? 0.9 : 0.7)).connect(g).connect(drums);
    src.start(t, Math.random()); src.stop(t + dur + 0.02);
  }
  function kick(t, vel) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.setValueAtTime(115, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.13);
    g.gain.setValueAtTime(vel, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.38);
    o.connect(g).connect(drums);
    o.start(t); o.stop(t + 0.4);
  }
  function snare(t, vel) {
    noise(t, 0.2, vel, "bandpass", 1700);
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = 185;
    g.gain.setValueAtTime(vel * 0.5, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.09);
    o.connect(g).connect(drums); o.start(t); o.stop(t + 0.1);
  }

  function schedule(s, t) {
    const pos = s % 16;
    if (pos === 0) {
      bar++;
      if (bar % 8 === 0 && Math.random() < 0.6) prog = PROGS[Math.floor(Math.random() * PROGS.length)];
    }
    if (pos % 4 === 2) t += STEP * 0.3;  // swing cho nốt móc đơn phách nghịch
    const [root, chord] = prog[bar % 4];
    const hum = () => 0.85 + Math.random() * 0.3;  // lực đánh không đều như người chơi
    if (pos === 0) chord.forEach((m, i) => keys(m, t + i * 0.012, STEP * 9, 0.07 * hum()));  // rải nhẹ
    if (pos === 10 && Math.random() < 0.55) chord.slice(1).forEach((m) => keys(m, t, STEP * 5, 0.045 * hum()));
    if (pos === 0) bass(root, t, STEP * 7, 0.32);
    if (pos === 10) bass(Math.random() < 0.6 ? root : root + 7, t, STEP * 4, 0.24);
    if (pos === 0 || pos === 10 || (pos === 7 && Math.random() < 0.3)) kick(t, 0.75 * hum());
    if (pos === 4 || pos === 12) snare(t, 0.32 * hum());
    if (pos % 2 === 0 && Math.random() < 0.9) noise(t, 0.045, (pos % 4 === 0 ? 0.09 : 0.05) * hum(), "highpass", 7500);
    if (pos % 2 === 0 && bar % 4 !== 3 && Math.random() < 0.2) {  // giai điệu thưa, đi bậc liền
      lastNote = Math.max(0, Math.min(MELODY.length - 1, lastNote + [-2, -1, -1, 1, 1, 2][Math.floor(Math.random() * 6)]));
      lead(MELODY[lastNote], t, STEP * (2 + Math.floor(Math.random() * 3)), 0.05);
    }
  }
  // xếp lịch trước ~1,5 giây: cửa sổ bị thu nhỏ thì setInterval chạy chậm (1 lần/giây) mà nhạc vẫn liền
  function tick() {
    while (nextTime < ctx.currentTime + 1.5) { schedule(step, nextTime); nextTime += STEP; step++; }
  }

  async function start() {
    if (on) return;
    on = true;  // bật ngay để nút đổi trạng thái liền; nhạc bắt đầu khi âm thanh sẵn sàng
    try {
      if (!ctx) init();
      await ctx.resume();
    } catch { on = false; return; }  // máy không có thiết bị âm thanh: bỏ qua, cảnh vẫn chạy
    if (!on) return;
    nextTime = ctx.currentTime + 0.12; t0 = nextTime; step = 0; bar = -1;
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setTargetAtTime(vol, ctx.currentTime, 0.4);
    tick();
    timer = setInterval(tick, 250);
  }
  function stop() {
    if (!on) return;
    on = false;
    clearInterval(timer);
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setTargetAtTime(0, ctx.currentTime, 0.15);
    setTimeout(() => { if (!on) ctx.suspend(); }, 700);  // các nốt đã xếp lịch tắt theo, không kêu tiếp
  }
  return {
    start, stop,
    toggle() { return on ? (stop(), false) : (start(), true); },
    get on() { return on; },
    get rain() { return rain; },
    setRain(v) { rain = !!v; if (rainGain) rainGain.gain.setTargetAtTime(rain ? 0.5 : 0, ctx.currentTime, 0.5); },
    setVolume(v) { vol = Math.max(0, Math.min(1, v)); if (ctx && on) master.gain.setTargetAtTime(vol, ctx.currentTime, 0.1); },
    beat() { return on && ctx ? (ctx.currentTime - t0) / BEAT : null; },  // số phách đã chơi, để robot nhún theo nhạc
    BPM,
  };
})();

// ===================================================================== cảnh văn phòng
const Office = (() => {
  const W = 400, CELL = 100, COLS = 4, WALL = 74, ROW = 80, LOUNGE = 84;
  const SPEED = 34;  // px thế giới / giây
  const BODY = ["#6c9cf0", "#f07a8e", "#8fcf6a", "#e9b45f", "#b096f0", "#5fc9e8", "#f09a5f", "#7fd6b5"];
  const tr = (s) => (typeof I18N !== "undefined" && I18N.lang === "en" && I18N.tr(s)) || s;
  let cv = null, g = null, layer = null, stage = null, inner = null;
  let H = WALL + ROW + LOUNGE, rows = 1, k = 1, raf = 0, lastT = 0, visible = false, layoutKey = "";
  const bots = new Map();  // tên tài khoản -> robot
  const fx = [];           // hạt hiệu ứng: khói, pháo giấy, "+điểm", nốt nhạc, zzz

  const loungeTop = () => WALL + rows * ROW;
  const corridorY = () => loungeTop() + 12;
  const cellOf = (i) => ({ col: i % COLS, row: Math.floor(i / COLS) });
  const deskTop = (row) => WALL + row * ROW + 40;
  const seat = (i) => { const { col, row } = cellOf(i); return { x: col * CELL + 64, y: deskTop(row) + 5 }; };
  const gapX = (col) => (col === 0 ? 7 : col * CELL);
  const LOUNGE_SPOTS = () => {
    const y = loungeTop();
    return [
      { x: 36, y: y + 58, pose: "sit", what: "sofa" }, { x: 62, y: y + 58, pose: "sit", what: "sofa" },
      { x: 132, y: y + 62, pose: "stand", what: "coffee" }, { x: 178, y: y + 62, pose: "stand", what: "water" },
      { x: 206, y: y + 70, pose: "stand", what: "plant" }, { x: 352, y: y + 64, pose: "stand", what: "arcade" },
      { x: 286, y: y + 74, pose: "stand", what: "rug" }, { x: 252, y: y + 52, pose: "stand", what: "rug" },
    ];
  };
  const hash = (s) => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);

  // ------------------------------------------------------------ bảng màu theo giao diện
  function palette() {
    const cyber = document.documentElement.getAttribute("data-skin") === "cyberpunk";
    const dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
    if (cyber) return { cyber, dark: true, wall: "#140c2c", wall2: "#1d1240", base: "#05d9e8", floor: "#120a26", floor2: "#170e30",
      grid: "rgba(5,217,232,.16)", desk: "#25184a", deskTop: "#33246a", deskEdge: "#05d9e8", leg: "#0d0820",
      mon: "#0b0f1f", monEdge: "#ff2a6d", sofa: "#5a1846", sofa2: "#7a2160", rug: "#2a1150", rug2: "#ff2a6d",
      text: "#fcee0a", sign: "#ff2a6d", shadow: "rgba(0,0,0,.45)", outline: "#05030d", plant: "#05d9e8", pot: "#3a2470" };
    if (dark) return { cyber, dark, wall: "#2b3042", wall2: "#323850", base: "#1d2130", floor: "#3a3546", floor2: "#36313f",
      grid: null, desk: "#5a3e2e", deskTop: "#76523b", deskEdge: "#8d6448", leg: "#2c1f17",
      mon: "#1a1d26", monEdge: "#444b5e", sofa: "#4a5d8a", sofa2: "#5c71a3", rug: "#4b3a52", rug2: "#6a5470",
      text: "#e6e8f0", sign: "#f4c14f", shadow: "rgba(0,0,0,.35)", outline: "#12141b", plant: "#4f9a5c", pot: "#8a5a44" };
    return { cyber, dark, wall: "#ece6da", wall2: "#e2dacb", base: "#b9a98f", floor: "#d6c4a6", floor2: "#cfbc9d",
      grid: null, desk: "#93603f", deskTop: "#b07a52", deskEdge: "#c48c61", leg: "#5e3d28",
      mon: "#2a2e38", monEdge: "#4a5060", sofa: "#5b7cc4", sofa2: "#7393d6", rug: "#c97f6a", rug2: "#e0a08d",
      text: "#2b2f3a", sign: "#2a78d6", shadow: "rgba(60,40,20,.18)", outline: "#2a2420", plant: "#4f9a5c", pot: "#b5694a" };
  }

  // ------------------------------------------------------------ bot đang làm gì (theo trạng thái thật)
  function activity(name) {
    const s = st(name), state = s.state || "Sẵn sàng", p = s.progress || "", running = S.running.has(name);
    const desk = (screen, face = "focus", extra = {}) => ({ at: "desk", pose: "sit", screen, face, ...extra });
    if (state === "Hoàn thành") return { at: "lounge", pose: "stand", screen: "done", face: "happy", prop: "mug" };
    if (state === "Đã dừng") return { at: "lounge", pose: "stand", screen: "off", face: "idle" };
    if (state === "Lỗi") return desk("error", "sad", { fx: "smoke", say: p || "Lỗi" });
    if (state === "Chưa đăng nhập") return desk("lock", "confused", { say: "Chưa đăng nhập" });
    if (state === "Đang đăng nhập") return desk("key", "focus", { say: "Đang đăng nhập" });
    if (state === "Đang kiểm tra") return desk("check", "focus", { say: "Đang kiểm tra" });
    if (state === "Đang làm mới") return desk("refresh", "focus", { say: "Đang làm mới" });
    if (state === "Đang chờ" || /^Chờ lượt/.test(p)) return { at: "wait", pose: "stand", screen: "off", face: "bored", say: "Chờ lượt chạy" };
    if (running || state === "Đang chạy") {
      if (/^Search PC/.test(p)) return desk("search", "focus", { say: p, typing: true });
      if (/^Search Mobile/.test(p)) return desk("phone", "focus", { say: p, prop: "phone" });
      if (/^Visual Search/.test(p)) return desk("visual", "wow", { say: p, fx: "flash" });
      if (/^Browse/.test(p)) return desk("web", "focus", { say: p, typing: true, slow: true });
      if (/^Quest/.test(p)) return desk("quest", "focus", { say: p, typing: true });
      if (/^(Daily Set|Keep earning)/.test(p)) return desk("cards", "focus", { say: p, typing: true });
      return desk("boot", "focus", { say: p || "Khởi động" });
    }
    return { at: "lounge", pose: "stand", screen: "off", face: "idle" };
  }

  // ------------------------------------------------------------ robot
  function sync() {
    const names = S.profiles.map((p) => p.name);
    rows = Math.max(1, Math.ceil(names.length / COLS));
    H = WALL + rows * ROW + LOUNGE;
    for (const n of [...bots.keys()]) if (!names.includes(n)) { bots.get(n).el.remove(); bots.delete(n); }
    names.forEach((name, i) => {
      let b = bots.get(name);
      if (!b) {
        b = { name, x: 0, y: 0, path: [], where: null, pose: "stand", act: null, spot: null, until: 0, color: BODY[hash(name) % BODY.length],
              blink: 0, say: "", sayUntil: 0, log: "", logUntil: 0, celebrate: 0, today: st(name).today, el: document.createElement("div") };
        b.el.className = "ob";
        b.el.innerHTML = `<div class="ob-bubble" data-no-i18n></div><button type="button" class="ob-tag"></button>`;
        b.el.querySelector(".ob-tag").onclick = () => { S.selected = name; go("dashboard"); };
        layer.appendChild(b.el);
        bots.set(name, b);
      }
      b.index = i;
    });
    const key = names.join("\n") + "|" + rows;
    if (key !== layoutKey) {  // đổi danh sách tài khoản: dựng lại kích thước, đặt robot thẳng vào chỗ (không đi bộ)
      layoutKey = key;
      resize();
      for (const b of bots.values()) { b.act = null; b.path = []; b.where = null; }
    }
    for (const b of bots.values()) update(b);
  }

  function place(b, to) { b.x = to.x; b.y = to.y; b.path = []; b.where = to; b.pose = to.pose; }
  function walk(b, to) {  // đi theo lối đi: ra khe giữa các bàn, xuống hành lang, rồi mới tới chỗ mới
    const pts = [], cy = corridorY(), from = b.where;
    if (from && from.kind === "desk" && to.kind === "desk" && from.col === to.col && from.row === to.row) { pts.push(to); }
    else {
      if (from && from.kind === "desk") pts.push({ x: gapX(from.col), y: b.y }, { x: gapX(from.col), y: cy });
      else if (to.kind === "desk") pts.push({ x: b.x, y: cy });
      if (to.kind === "desk") pts.push({ x: gapX(to.col), y: cy }, { x: gapX(to.col), y: to.y });
      pts.push(to);
    }
    b.path = pts; b.where = to; b.pose = "stand";
  }
  function target(b, act) {
    const { col, row } = cellOf(b.index), s = seat(b.index);
    if (act.at === "desk") return { kind: "desk", col, row, x: s.x, y: s.y, pose: "sit" };
    if (act.at === "wait") return { kind: "desk", col, row, x: col * CELL + (col === COLS - 1 ? 5 : 95), y: s.y + 2, pose: "stand" };
    return pickSpot(b);
  }
  function pickSpot(b) {
    const taken = new Set([...bots.values()].filter((o) => o !== b && o.spot).map((o) => o.spot.what + o.spot.x));
    const free = LOUNGE_SPOTS().filter((s) => !taken.has(s.what + s.x));
    const lt = loungeTop();
    const s = free.length ? free[Math.floor(Math.random() * free.length)]
      : { x: 100 + Math.random() * 200, y: lt + 40 + Math.random() * 34, pose: "stand", what: "rug" };
    b.spot = s;
    b.until = performance.now() + 8000 + Math.random() * 12000;
    return { kind: "lounge", ...s };
  }
  function update(b) {
    const act = activity(b.name), prev = b.act;
    const sig = (a) => a && a.at + a.screen;
    if (prev && prev.face !== "happy" && act.face === "happy") {  // vừa chạy xong: ăn mừng tại bàn một lúc rồi mới đi nghỉ
      b.celebrate = performance.now() + 4500;
      burst(b.x, b.y - 26, "confetti", 26);
    }
    const s = st(b.name);
    if (typeof s.today === "number" && typeof b.today === "number" && s.today > b.today) floatText(b, `+${s.today - b.today}`);
    b.today = s.today;
    b.act = act;
    if (sig(prev) === sig(act) && b.where) return;
    const to = act.at === "lounge" && b.celebrate > performance.now() ? null : target(b, act);
    if (!to) return;
    if (act.at !== "lounge") b.spot = null;
    if (!b.where) place(b, to); else walk(b, to);
  }

  // ------------------------------------------------------------ hiệu ứng
  function burst(x, y, kind, n) {
    const cols = ["#ff5d73", "#ffd23f", "#4fd1c5", "#7aa2ff", "#b28dff", "#8fd16a"];
    for (let i = 0; i < n; i++) {
      fx.push({ kind, x, y, vx: (Math.random() - 0.5) * 60, vy: -30 - Math.random() * 50, life: 1.4 + Math.random(), age: 0,
                c: cols[i % cols.length] });
    }
  }
  function floatText(b, text) { fx.push({ kind: "text", text, x: b.x, y: b.y - 34, vx: 0, vy: -10, life: 2.2, age: 0 }); }
  function onLog(e) {
    const b = bots.get(e.name);
    if (!b || !e.msg) return;
    b.log = e.msg.length > 70 ? e.msg.slice(0, 68) + "…" : e.msg;
    b.logUntil = performance.now() + 3500;
  }

  // ------------------------------------------------------------ vẽ
  function R(x, y, w, h, c) { g.fillStyle = c; g.fillRect(Math.round(x), Math.round(y), w, h); }
  function txt(s, x, y, c, size = 7, align = "center", weight = "bold") {
    g.font = `${weight} ${size}px ui-monospace, Consolas, monospace`;
    g.textAlign = align; g.textBaseline = "alphabetic"; g.fillStyle = c; g.fillText(s, x, y);
  }

  function drawRoom(t, P) {
    R(0, 0, W, WALL, P.wall);
    for (let x = 0; x < W; x += 16) R(x, 0, 8, WALL, P.wall2);  // giấy dán tường sọc
    R(0, WALL - 5, W, 5, P.base);
    const lt = loungeTop();
    for (let y = WALL; y < H; y += 10) for (let x = 0; x < W; x += 10) R(x, y, 10, 10, ((x + y) / 10) % 2 ? P.floor : P.floor2);
    if (P.grid) { g.fillStyle = P.grid; for (let x = 0; x < W; x += 20) g.fillRect(x, WALL, 1, H - WALL); for (let y = WALL; y < H; y += 20) g.fillRect(0, y, W, 1); }
    R(0, lt, W, 2, P.base);  // vạch ngăn khu nghỉ

    // biển tên công ty
    R(10, 14, 104, 26, P.cyber ? "#0b0617" : P.outline);
    R(12, 16, 100, 22, P.cyber ? "#1a0b33" : (P.dark ? "#23283a" : "#fdfbf6"));
    const flick = P.cyber && Math.sin(t * 13) > 0.97 ? 0.35 : 1;
    g.globalAlpha = flick;
    if (P.cyber) { g.shadowColor = P.sign; g.shadowBlur = 6 * k; }
    txt("REWARDS HQ", 62, 31, P.sign, 10);
    g.shadowBlur = 0; g.globalAlpha = 1;
    txt(tr("Văn phòng bot"), 62, 50, P.text, 6, "center", "normal");

    // cửa sổ: trời theo giờ thật; mưa khi bật tiếng mưa
    const hr = new Date().getHours() + new Date().getMinutes() / 60, day = hr >= 6 && hr < 18, dusk = (hr >= 17 && hr < 19) || (hr >= 5 && hr < 7);
    [[134, 12], [204, 12]].forEach(([wx, wy], wi) => {
      const WW = 54, WH = 40, frame = P.cyber ? "#05d9e8" : P.outline;
      const sky = P.cyber ? "#1b0838" : dusk ? "#f4a06a" : day ? "#8fd0f5" : "#141a3a";
      // mọi thứ bên trong ô kính bị cắt theo khung, khung vẽ sau cùng nên không bao giờ bị đè
      g.save(); g.beginPath(); g.rect(wx, wy, WW, WH); g.clip();
      R(wx, wy, WW, WH, sky);
      if (P.cyber || !day) {
        for (let i = 0; i < 9; i++) { const sx = wx + ((i * 37 + wi * 13) % 52), sy = wy + ((i * 23) % 22); if (Math.sin(t * 2 + i) > -0.3) R(sx, sy, 1, 1, "#fff"); }
        if (!P.cyber && wi === 1) { R(wx + 38, wy + 6, 7, 7, "#f3efd6"); R(wx + 40, wy + 6, 5, 5, sky); }
      } else {
        const cx = wx + ((t * 4 + wi * 30) % 70) - 12;  // mây trôi
        R(cx, wy + 8, 14, 4, "#fff"); R(cx + 3, wy + 5, 8, 3, "#fff");
        if (wi === 0) R(wx + 6, wy + 5, 6, 6, "#ffe27a");
      }
      // nhà phía xa
      const city = P.cyber ? ["#2b0f55", "#ff2a6d", "#05d9e8"] : day ? ["#7d93a8", "#c6d6e4", "#fff3b0"] : ["#232a52", "#2f3868", "#ffd56a"];
      for (let i = 0; i < 6; i++) {
        const bw = 7 + ((i * 5 + wi * 3) % 5), bh = 10 + ((i * 7 + wi * 11) % 16), bx = wx + i * 9;
        R(bx, wy + WH - bh, bw, bh, city[0]);
        for (let yy = wy + WH + 2 - bh; yy < wy + WH - 2; yy += 4) if ((yy + i) % 3) R(bx + 2, yy, 1, 1, i % 2 ? city[2] : city[1]);
      }
      if (S.officeRain) {
        g.fillStyle = "rgba(200,220,255,.55)";
        for (let i = 0; i < 14; i++) { const rx = wx + ((i * 17 + Math.floor(t * 60) * 3) % WW), ry = wy + ((i * 29 + Math.floor(t * 120)) % (WH - 2)); g.fillRect(rx, ry, 1, 3); }
      }
      g.restore();
      // khung 2px bốn cạnh + song cửa chữ thập + bậu cửa
      R(wx - 2, wy - 2, WW + 4, 2, frame); R(wx - 2, wy + WH, WW + 4, 2, frame);
      R(wx - 2, wy, 2, WH, frame); R(wx + WW, wy, 2, WH, frame);
      R(wx + WW / 2 - 1, wy, 2, WH, frame); R(wx, wy + WH / 2 - 1, WW, 2, frame);
      R(wx - 4, wy + WH + 2, WW + 8, 3, P.cyber ? "#ff2a6d" : P.base);
    });

    // đồng hồ số
    const now = new Date(), hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
    R(268, 14, 36, 16, P.outline); R(270, 16, 32, 12, "#0d1410");
    txt(`${hh}${now.getSeconds() % 2 ? ":" : " "}${mm}`, 286, 26, P.cyber ? "#fcee0a" : "#7dfc9a", 8);

    // bảng trắng: tổng điểm hôm nay của cả văn phòng
    const total = S.profiles.reduce((a, p) => a + (typeof st(p.name).today === "number" ? st(p.name).today : 0), 0);
    const working = [...bots.values()].filter(isWorking).length;
    R(312, 10, 80, 50, P.cyber ? "#05d9e8" : "#9aa0ac"); R(314, 12, 76, 46, P.cyber ? "#0b0f1f" : "#fbfcfe");
    txt(tr("Hôm nay"), 352, 22, P.cyber ? "#05d9e8" : "#5a6070", 6, "center", "normal");
    txt(`+${total.toLocaleString("en-US")}`, 352, 36, P.cyber ? "#fcee0a" : "#1f8f4e", 11);
    txt(`${working}/${S.profiles.length} ${tr("đang làm")}`, 352, 50, P.cyber ? "#ff2a6d" : "#5a6070", 6, "center", "normal");

    // khu nghỉ: thảm, sofa, máy cà phê, bình nước, cây, máy game
    R(240, lt + 44, 96, 36, P.rug); R(244, lt + 48, 88, 28, P.rug2); R(248, lt + 52, 80, 20, P.rug);
    R(16, lt + 36, 66, 14, P.sofa2); R(14, lt + 48, 70, 16, P.sofa); R(12, lt + 44, 6, 22, P.sofa2); R(80, lt + 44, 6, 22, P.sofa2);
    R(118, lt + 26, 22, 30, P.outline); R(120, lt + 28, 18, 26, P.cyber ? "#2b2050" : "#d9dde6");
    R(124, lt + 32, 10, 6, "#222"); R(125, lt + 33, 2, 2, Math.sin(t * 3) > 0 ? "#ff4d4d" : "#4dff88"); R(126, lt + 44, 6, 6, "#fff");
    if (Math.floor(t * 2) % 3 === 0) R(128, lt + 41, 1, 3, "rgba(255,255,255,.6)");  // hơi cà phê
    R(166, lt + 22, 16, 14, "#9fd3f5"); R(167, lt + 23, 14, 12, "#c7e8fb"); R(164, lt + 36, 20, 22, P.cyber ? "#33246a" : "#e6e9ef");
    R(222, lt + 48, 14, 12, P.pot); R(220, lt + 30, 18, 18, P.plant); R(224, lt + 24, 10, 8, P.plant); R(226, lt + 36, 2, 12, "#2f6b3a");
    R(340, lt + 20, 26, 40, P.cyber ? "#ff2a6d" : "#5a3fa0"); R(343, lt + 24, 20, 14, "#08080f");
    for (let i = 0; i < 3; i++) R(346 + i * 6, lt + 28 + ((Math.floor(t * 4) + i) % 3) * 3, 3, 3, ["#4dff88", "#ffd23f", "#4fd1c5"][i]);
    R(345, lt + 42, 4, 4, "#ffd23f"); R(355, lt + 42, 3, 3, "#ff5d73"); R(360, lt + 44, 3, 3, "#4fd1c5");
  }

  function drawDesk(i, P, t) {
    const { col, row } = cellOf(i), x = col * CELL, top = deskTop(row);
    R(x + 14, top, 74, 6, P.deskTop); R(x + 14, top + 6, 74, 10, P.desk); R(x + 14, top, 74, 1, P.deskEdge);
    R(x + 18, top + 16, 4, 8, P.leg); R(x + 80, top + 16, 4, 8, P.leg);
    R(x + 16, top + 26, 70, 2, P.shadow);
    // màn hình
    R(x + 18, top - 21, 30, 19, P.monEdge); R(x + 20, top - 19, 26, 15, P.mon); R(x + 31, top - 2, 4, 2, P.monEdge);
    const b = bots.get(S.profiles[i]?.name);
    drawScreen(b && b.act ? b.act.screen : "off", x + 20, top - 19, t + i, P, b);
    // bàn phím, cốc, cây nhỏ
    R(x + 54, top + 1, 18, 3, P.cyber ? "#05d9e8" : "#e8e8ec"); R(x + 79, top - 5, 5, 6, ["#e05d5d", "#5d8fe0", "#5dc08a", "#e0b85d"][i % 4]);
  }

  function drawChair(i, P) {  // ghế xoay sau lưng robot (robot ngồi quay mặt ra ngoài): lưng ghế thấp, bo góc
    const { col, row } = cellOf(i), x = col * CELL + 64, top = deskTop(row);
    const c = P.cyber ? "#3a1f66" : P.dark ? "#2f6f8f" : "#3f7fa8", hi = P.cyber ? "#ff2a6d" : P.dark ? "#4a8fb0" : "#62a2c8";
    R(x - 9, top - 15, 18, 1, P.outline); R(x - 10, top - 14, 20, 13, P.outline);
    R(x - 8, top - 14, 16, 12, c); R(x - 9, top - 13, 18, 10, c); R(x - 7, top - 13, 14, 2, hi);
    R(x - 1, top - 2, 2, 2, P.outline);
  }

  function drawScreen(kind, x, y, t, P, b) {
    const w = 26, h = 15, blinkOn = Math.floor(t * 2) % 2;
    const fill = (c) => R(x, y, w, h, c);
    switch (kind) {
      case "search": {  // Bing: ô tìm kiếm đang gõ + kết quả hiện dần
        fill("#f7f8fb");
        R(x + 2, y + 2, 3, 4, "#1aa1a1");
        const typed = Math.floor((t * 8) % 18);
        R(x + 7, y + 2, 17, 4, "#dde3ee"); R(x + 8, y + 3, typed % 15, 2, "#606878"); if (blinkOn) R(x + 8 + (typed % 15), y + 3, 1, 2, "#111");
        for (let i = 0; i < 3; i++) if (typed > 6 + i * 3) { R(x + 2, y + 8 + i * 2, 10, 1, "#3b6fd8"); R(x + 13, y + 8 + i * 2, 9 - i * 2, 1, "#9aa3b5"); }
        break;
      }
      case "phone": fill("#222838"); R(x + 10, y + 2, 7, 12, "#8892a8"); R(x + 11, y + 3, 5, 9, blinkOn ? "#5fc9e8" : "#4aa8c6"); break;
      case "visual": {
        fill("#9fd8f2"); R(x, y + 9, w, 6, "#5ea85c"); R(x + 6, y + 5, 7, 6, "#4b7f4a"); R(x + 18, y + 2, 4, 4, "#ffe27a");
        if (Math.floor(t * 1.5) % 4 === 0) { R(x, y, w, h, "rgba(255,255,255,.85)"); }  // đèn flash
        R(x + 1, y + 1, 4, 1, "#e33"); R(x + 1, y + 1, 1, 3, "#e33"); R(x + w - 5, y + h - 2, 4, 1, "#e33"); R(x + w - 2, y + h - 4, 1, 3, "#e33");
        break;
      }
      case "web": {
        fill("#fafafa"); R(x, y, w, 2, "#3b6fd8");
        const off = Math.floor(t * 6) % 8;
        for (let i = -1; i < 5; i++) { const yy = y + 3 + i * 3 + (8 - off) / 2.7; if (yy < y + 3 || yy > y + 13) continue; R(x + 2, yy, 8 + ((i * 5) % 12), 1, i % 2 ? "#9aa3b5" : "#606878"); if (i % 3 === 0) R(x + 18, yy, 6, 2, "#f0b35a"); }
        break;
      }
      case "cards": {
        fill("#eef1f7");
        const on = Math.floor(t * 1.2) % 3;
        for (let i = 0; i < 3; i++) { R(x + 2 + i * 8, y + 3, 6, 9, i === on ? "#2a78d6" : "#c8d0de"); if (i < on) R(x + 4 + i * 8, y + 7, 2, 2, "#1baf7a"); }
        break;
      }
      case "quest": fill("#2b2140"); R(x + 9, y + 2, 9, 6, "#ffd23f"); R(x + 7, y + 3, 2, 3, "#ffd23f"); R(x + 18, y + 3, 2, 3, "#ffd23f");
        R(x + 12, y + 8, 3, 3, "#e0a82e"); R(x + 9, y + 11, 9, 2, "#e0a82e"); if (blinkOn) R(x + 11, y + 3, 1, 1, "#fff"); break;
      case "lock": fill("#3a1f28"); R(x + 10, y + 3, 7, 4, "#c8c8d0"); R(x + 11, y + 4, 5, 3, "#3a1f28"); R(x + 9, y + 7, 9, 6, "#f0c14b"); R(x + 13, y + 9, 1, 2, "#3a1f28"); break;
      case "key": { fill("#1f2a3a"); const kx = x + 4 + Math.floor(t * 6) % 10; R(kx, y + 6, 4, 4, "#f0c14b"); R(kx + 4, y + 7, 7, 2, "#f0c14b"); R(kx + 9, y + 9, 2, 2, "#f0c14b"); break; }
      case "check": {
        fill("#f4f6fa");
        const n = Math.floor(t * 1.5) % 5;
        for (let i = 0; i < 4; i++) { R(x + 3, y + 2 + i * 3, 2, 2, i < n ? "#1baf7a" : "#c8d0de"); R(x + 7, y + 2 + i * 3, 14 - i * 2, 1, "#8a93a6"); }
        break;
      }
      case "refresh": { fill("#1d2433"); for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2 + t * 4; R(x + 12 + Math.cos(a) * 5, y + 7 + Math.sin(a) * 5, 1 + (i > 5), 1 + (i > 5), i > 5 ? "#5fc9e8" : "#3c4b66"); } break; }
      case "boot": fill("#0e1320"); R(x + 4, y + 9, 18, 3, "#2a3550"); R(x + 4, y + 9, Math.floor((t * 6) % 18), 3, "#5fc9e8"); R(x + 10, y + 3, 6, 4, "#2a78d6"); break;
      case "error": fill("#2456c8"); txt(":(", x + 7, y + 10, "#fff", 7); R(x + 15, y + 5, 8, 1, "#c8d6ff"); R(x + 15, y + 8, 6, 1, "#c8d6ff"); break;
      case "done": fill("#103a2a"); R(x + 8, y + 8, 3, 2, "#4dff88"); R(x + 10, y + 9, 3, 2, "#4dff88"); R(x + 12, y + 5, 2, 4, "#4dff88"); R(x + 14, y + 3, 2, 3, "#4dff88"); break;
      default: {  // tắt: màn hình chờ chấm nhảy
        fill(P.mon);
        if (b && b.act && b.act.at === "lounge") { const px = Math.abs(((t * 6) % 44) - 22), py = Math.abs(((t * 4) % 26) - 13); R(x + 1 + px, y + 1 + py, 2, 1, P.cyber ? "#ff2a6d" : "#3b4258"); }
      }
    }
    if (P.cyber && kind !== "off") { g.fillStyle = "rgba(0,0,0,.18)"; for (let yy = y; yy < y + h; yy += 2) g.fillRect(x, yy, w, 1); }
  }

  function drawBot(b, t, P) {
    const beat = Lofi.beat(), now = performance.now();
    const moving = b.path.length > 0, sit = !moving && b.pose === "sit";
    const cele = b.celebrate > now;
    let bob = 0;
    if (cele) bob = -Math.abs(Math.sin(t * 9)) * 6;
    else if (moving) bob = Math.floor(t * 8) % 2 ? -1 : 0;
    else if (beat !== null && b.act && b.act.at !== "desk") bob = Math.sin(beat * Math.PI) ** 2 > 0.6 ? -1 : 0;  // nhún theo nhạc
    const x = Math.round(b.x), y = Math.round(b.y + bob), base = sit ? y - 2 : y;
    const dark = shade(b.color, -0.35), light = shade(b.color, 0.25), O = P.outline;
    R(x - 7, b.y - 1, 14, 2, P.shadow);
    // chân
    if (!sit) {
      const sw = moving ? (Math.floor(t * 8) % 2 ? 1 : -1) : 0;
      R(x - 4, base - 5 + Math.max(0, sw), 3, 5 - Math.max(0, sw), O); R(x + 1, base - 5 + Math.max(0, -sw), 3, 5 - Math.max(0, -sw), O);
    }
    const bodyY = base - (sit ? 9 : 14);
    // thân + đèn ngực
    R(x - 7, bodyY - 1, 14, 11, O); R(x - 6, bodyY, 12, 9, b.color); R(x - 6, bodyY, 12, 2, light);
    const working = b.act && b.act.at === "desk" && b.act.screen !== "error";
    R(x - 1, bodyY + 4, 3, 3, working ? (Math.floor(t * 4) % 2 ? "#4dff88" : "#1f8f4e") : b.act && b.act.screen === "error" ? "#ff4d4d" : dark);
    // tay
    const act = b.act || {};
    if (sit && act.typing && !cele) {
      const a = Math.floor(t * (act.slow ? 3 : 10)) % 2;
      R(x - 9, bodyY + 3 + a, 3, 4, O); R(x + 6, bodyY + 4 - a, 3, 4, O);
    } else if (cele) {
      R(x - 10, bodyY - 5, 3, 6, O); R(x + 7, bodyY - 5, 3, 6, O);  // giơ tay ăn mừng
    } else {
      R(x - 9, bodyY + 2, 3, 6, O); R(x + 6, bodyY + 2, 3, 6, O);
    }
    if (act.prop === "phone" && !moving) { R(x + 4, bodyY - 3, 5, 8, "#2a2e38"); R(x + 5, bodyY - 2, 3, 5, Math.floor(t * 3) % 2 ? "#5fc9e8" : "#9fe6ff"); }
    if (act.prop === "mug" && !moving) { R(x + 6, bodyY + 1, 4, 4, "#f4f4f4"); R(x + 10, bodyY + 2, 1, 2, "#f4f4f4"); if (Math.floor(t * 2) % 2) R(x + 7, bodyY - 2, 1, 2, "rgba(255,255,255,.6)"); }
    // đầu + mặt màn hình
    const headY = bodyY - 11;
    R(x - 8, headY - 1, 16, 12, O); R(x - 7, headY, 14, 10, b.color); R(x - 7, headY, 14, 2, light);
    R(x - 5, headY + 2, 10, 6, "#10131c");
    drawFace(b, x, headY + 2, t, cele ? "happy" : sleeping(b) ? "sleep" : act.face || "idle");
    // ăng-ten
    R(x, headY - 4, 1, 3, O);
    const ant = working ? (Math.floor(t * 3) % 2 ? "#4dff88" : "#ffd23f") : act.screen === "error" ? (Math.floor(t * 4) % 2 ? "#ff4d4d" : "#7a1d1d") : light;
    R(x - 1, headY - 6, 3, 2, ant);
  }
  function isWorking(b) { return !!(b.act && b.act.at === "desk" && !["error", "lock"].includes(b.act.screen)); }
  function sleeping(b) {
    const h = new Date().getHours();
    return b.act && b.act.at === "lounge" && b.spot && b.spot.what === "sofa" && !b.path.length && (h >= 23 || h < 6);
  }
  function drawFace(b, x, y, t, face) {
    const now = performance.now();
    if (now > b.blink) b.blink = now + 2500 + Math.random() * 3000;
    const blink = b.blink - now < 120;
    const c = face === "sad" ? "#ff5d5d" : face === "happy" ? "#ffd23f" : "#6ff0ff";
    const eye = (ex) => {
      if (face === "sleep" || blink) R(ex, y + 3, 3, 1, c);
      else if (face === "happy") { R(ex, y + 2, 1, 1, c); R(ex + 1, y + 1, 1, 1, c); R(ex + 2, y + 2, 1, 1, c); }
      else if (face === "sad") { R(ex, y + 1, 1, 1, c); R(ex + 2, y + 1, 1, 1, c); R(ex + 1, y + 2, 1, 1, c); R(ex, y + 3, 1, 1, c); R(ex + 2, y + 3, 1, 1, c); }
      else if (face === "focus") R(ex, y + 2, 3, 2, c);
      else if (face === "wow") R(ex, y + 1, 3, 3, c);
      else if (face === "bored") R(ex, y + 3, 3, 1, c);
      else if (face === "confused") (ex < x ? R(ex, y + 2, 3, 2, c) : R(ex, y + 1, 3, 1, c));
      else R(ex, y + 1, 2, 3, c);
    };
    eye(x - 4); eye(x + 1);
    if (face === "happy") R(x - 1, y + 4, 2, 1, c);
  }
  function shade(hex, f) {
    const n = parseInt(hex.slice(1), 16), ch = [n >> 16, (n >> 8) & 255, n & 255].map((v) => Math.round(f < 0 ? v * (1 + f) : v + (255 - v) * f));
    return `rgb(${ch.join(",")})`;
  }

  function drawFx(dt, t) {
    for (let i = fx.length - 1; i >= 0; i--) {
      const p = fx[i];
      p.age += dt;
      if (p.age > p.life) { fx.splice(i, 1); continue; }
      p.x += p.vx * dt; p.y += p.vy * dt;
      const a = 1 - p.age / p.life;
      g.globalAlpha = Math.max(0, a);
      if (p.kind === "confetti") { p.vy += 90 * dt; R(p.x, p.y, 2, 2, p.c); }
      else if (p.kind === "smoke") R(p.x, p.y, 3 + p.age * 3, 3 + p.age * 3, "rgba(120,120,130,.55)");
      else if (p.kind === "note") txt("♪", p.x + Math.sin(p.age * 4) * 2, p.y, p.c, 8);
      else if (p.kind === "zzz") txt("z", p.x + Math.sin(p.age * 3) * 2, p.y, "#a9b4d6", 6 + p.age * 2);
      else if (p.kind === "text") { txt(p.text, p.x + 1, p.y + 1, "rgba(0,0,0,.5)", 8); txt(p.text, p.x, p.y, "#ffd23f", 8); }
      g.globalAlpha = 1;
    }
    for (const b of bots.values()) {  // hiệu ứng liên tục theo trạng thái
      if (!b.act || b.path.length) continue;
      if (b.act.fx === "smoke" && Math.random() < dt * 3) fx.push({ kind: "smoke", x: b.x - 2 + Math.random() * 4, y: b.y - 34, vx: (Math.random() - 0.5) * 6, vy: -12, life: 1.6, age: 0 });
      if (sleeping(b) && Math.random() < dt * 0.8) fx.push({ kind: "zzz", x: b.x + 6, y: b.y - 30, vx: 4, vy: -8, life: 2.2, age: 0 });
      if (Lofi.on && b.act.at === "lounge" && !sleeping(b) && Math.random() < dt * 0.35)
        fx.push({ kind: "note", x: b.x + 5, y: b.y - 30, vx: 3, vy: -9, life: 2.4, age: 0, c: ["#ffd23f", "#ff8fb1", "#7fe3ff"][Math.floor(Math.random() * 3)] });
    }
    if (fx.length > 300) fx.splice(0, fx.length - 300);
  }

  function step(dt) {
    const now = performance.now();
    for (const b of bots.values()) {
      if (b.path.length) {
        const p = b.path[0], dx = p.x - b.x, dy = p.y - b.y, d = Math.hypot(dx, dy), mv = SPEED * dt;
        if (d <= mv) { b.x = p.x; b.y = p.y; b.path.shift(); if (!b.path.length) b.pose = b.where.pose; }
        else { b.x += (dx / d) * mv; b.y += (dy / d) * mv; }
      } else if (b.act && b.act.at === "lounge") {
        if (b.celebrate && b.celebrate < now && b.where && b.where.kind === "desk") { b.celebrate = 0; walk(b, pickSpot(b)); }
        else if (b.where && b.where.kind === "lounge" && now > b.until && !sleeping(b)) walk(b, pickSpot(b));  // đổi chỗ chơi
      }
    }
  }

  function bubbleText(b) {
    const now = performance.now();
    if (b.logUntil > now && b.act && b.act.at === "desk") return { text: b.log, log: true };
    if (b.celebrate > now) return { text: tr("Xong việc rồi!") };
    const a = b.act;
    if (!a || !a.say) return null;  // đang đi tới bàn cũng nói luôn việc sắp làm
    return { text: tr(a.say) };
  }
  function drawLayer() {
    for (const b of bots.values()) {
      const s = st(b.name), { col, row } = cellOf(b.index);
      const tag = b.el.querySelector(".ob-tag"), bub = b.el.querySelector(".ob-bubble");
      const tagHtml = `${avatarHtml(b.name, "avatar-xs rounded-circle")}<span>${esc(b.name)}</span>`
        + `<b>${typeof s.points === "number" ? fmt(s.points) : ""}</b>`;
      if (tag._h !== tagHtml) { tag.innerHTML = tagHtml; tag._h = tagHtml; tag.title = "Xem tổng quan của tài khoản này"; }
      tag.style.left = ((col * CELL + 51) / W * 100) + "%";
      tag.style.top = ((deskTop(row) + 28) / H * 100) + "%";
      const bt = bubbleText(b);
      bub.hidden = !bt;
      if (bt) {
        if (bub.textContent !== bt.text) bub.textContent = bt.text;
        bub.classList.toggle("log", !!bt.log);
        bub.classList.toggle("err", !!(b.act && b.act.screen === "error"));
        bub.style.left = (b.x / W * 100) + "%";
        bub.style.top = ((b.y - (b.pose === "sit" && !b.path.length ? 26 : 31)) / H * 100) + "%";
      }
    }
  }

  function frame(ts) {
    raf = 0;
    if (!visible) return;
    const dt = Math.min(0.1, (ts - (lastT || ts)) / 1000);
    lastT = ts;
    const t = ts / 1000, P = palette();
    step(dt);
    g.setTransform(k, 0, 0, k, 0, 0);
    g.imageSmoothingEnabled = false;
    drawRoom(t, P);
    // vẽ theo chiều sâu: vật ở trên (y nhỏ) vẽ trước để vật ở dưới che lên
    const items = S.profiles.flatMap((p, i) => [{ y: deskTop(cellOf(i).row) - 30, draw: () => drawChair(i, P) },
                                                 { y: deskTop(cellOf(i).row) + 16, draw: () => drawDesk(i, P, t) }]);
    for (const b of bots.values()) items.push({ y: b.y, draw: () => drawBot(b, t, P) });
    items.sort((a, b) => a.y - b.y).forEach((it) => it.draw());
    for (const b of bots.values()) {
      if (b.act && b.act.fx === "flash" && !b.path.length && Math.floor(t * 1.5) % 4 === 0) {  // Visual Search: chớp sáng quanh bàn
        const fx0 = cellOf(b.index).col * CELL + 33, fy0 = deskTop(cellOf(b.index).row) - 12;
        const grad = g.createRadialGradient(fx0, fy0, 2, fx0, fy0, 40);
        grad.addColorStop(0, "rgba(255,255,255,.55)"); grad.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = grad; g.fillRect(fx0 - 40, fy0 - 40, 80, 80);
      }
    }
    drawFx(dt, t);
    drawLayer();
    raf = requestAnimationFrame(frame);
  }

  function resize() {
    if (!stage) return;
    const dpr = window.devicePixelRatio || 1, cssW = Math.max(200, stage.clientWidth);
    k = Math.max(1, Math.floor((cssW * dpr) / W));  // phóng to theo số nguyên lần -> pixel sắc nét
    if (cssW * dpr / W < 1.5) k = (cssW * dpr) / W;  // màn hình quá hẹp: chấp nhận co lẻ
    cv.width = Math.round(W * k); cv.height = Math.round(H * k);
    inner.style.width = cv.width / dpr + "px"; inner.style.height = cv.height / dpr + "px";
  }

  function bindControls() {
    const music = $("#office-music"), rain = $("#office-rain"), volume = $("#office-volume");
    const vol = pref.get("officeVolume", 0.6);
    volume.value = Math.round(vol * 100); Lofi.setVolume(vol);
    S.officeRain = pref.get("officeRain", false);
    Lofi.setRain(S.officeRain);
    const paint = () => {
      music.classList.toggle("active", Lofi.on);
      music.querySelector("i").className = "ti " + (Lofi.on ? "ti-player-pause" : "ti-player-play");
      music.querySelector("span").textContent = Lofi.on ? "Tắt nhạc lofi" : "Bật nhạc lofi";
      rain.classList.toggle("active", !!S.officeRain);
      $("#office-now").textContent = Lofi.on ? `Lofi tự sinh · ${Lofi.BPM} BPM${S.officeRain ? " · mưa" : ""}` : "Nhạc đang tắt";
    };
    music.onclick = () => { Lofi.toggle(); pref.set("officeMusic", Lofi.on); paint(); };
    rain.onclick = () => { S.officeRain = !S.officeRain; Lofi.setRain(S.officeRain); pref.set("officeRain", S.officeRain); paint(); };
    volume.oninput = () => { const v = +volume.value / 100; Lofi.setVolume(v); pref.set("officeVolume", v); };
    cv.addEventListener("click", (e) => {  // bấm vào robot -> mở tổng quan của tài khoản đó
      const r = cv.getBoundingClientRect(), wx = (e.clientX - r.left) / r.width * W, wy = (e.clientY - r.top) / r.height * H;
      const hit = [...bots.values()].find((b) => Math.abs(b.x - wx) < 9 && wy > b.y - 30 && wy < b.y + 2);
      if (hit) { S.selected = hit.name; go("dashboard"); }
    });
    paint();
    // lần trước để nhạc bật: bật lại ở lần bấm chuột đầu tiên (trình duyệt không cho tự phát tiếng khi chưa bấm gì)
    if (pref.get("officeMusic", false)) {
      const resume = (e) => {
        if (e.target.closest("#office-music")) return;  // bấm chính nút nhạc thì để nút tự xử lý
        document.removeEventListener("pointerdown", resume, true);
        if (!Lofi.on) { Lofi.start(); paint(); }
      };
      document.addEventListener("pointerdown", resume, true);
    }
  }

  return {
    init() {
      cv = $("#office-canvas"); stage = $("#office-stage"); inner = $("#office-inner"); layer = $("#office-layer");
      if (!cv) return;
      g = cv.getContext("2d");
      bindControls();
      new ResizeObserver(() => resize()).observe(stage);
      document.addEventListener("visibilitychange", () => this.render());
    },
    render() {  // gọi mỗi lần trạng thái đổi hoặc đổi trang
      if (!cv) return;
      const show = S.page === "office" && !document.hidden;
      sync();
      $("#office-empty").hidden = S.profiles.length > 0;
      const run = [...bots.values()].filter(isWorking).length;
      $("#office-sub").textContent = `${run} robot đang làm việc · ${S.profiles.length - run} đang nghỉ`;
      if (show && !visible) { visible = true; lastT = 0; resize(); }
      visible = show;
      if (visible && !raf) raf = requestAnimationFrame(frame);
    },
    onLog,
  };
})();
window.Office = Office;  // const ở cấp cao nhất không thành thuộc tính của window; app.js gọi qua window.Office
