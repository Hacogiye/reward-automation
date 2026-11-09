"use strict";
// Trang "Văn phòng": mỗi tài khoản là một con robot có bàn làm việc riêng. Robot làm gì là theo trạng thái thật của bot
// (S.pstate / S.running trong app.js): search PC thì gõ phím, Mobile thì cầm điện thoại, xong thì ra sofa uống cà phê...
// Mọi hình đều vẽ pixel bằng canvas, nhạc lofi tự sinh bằng Web Audio: không có file ảnh / nhạc ngoài (CSP chỉ cho 'self').
//
// Góc nhìn isometric 2:1 (ô sàn 32 x 16 px): hai bức tường phía sau, cửa sổ ở tường trái, biển tên / đồng hồ / bảng điểm ở
// tường phải, khu nghỉ là dải gần người xem nhất. Hiệu năng: canvas chỉ to bằng "thế giới" (cỡ phụ thuộc số hàng bàn), GPU
// phóng to bằng CSS image-rendering: pixelated. Phần không có gì đứng sau (sàn, tường, thảm, đồ treo tường) vẽ sẵn vào
// canvas nền; đồ đạc vẽ sẵn thành sprite theo giao diện, rồi xếp cùng robot theo độ sâu. Khoảng 30 khung
// hình/giây khi có gì chuyển động, 6 khi tất cả đang nghỉ; dừng hẳn khi rời trang. Chữ tiếng Việt nằm ở lớp HTML phía
// trên (nét ở mọi cỡ), số vẽ bằng font pixel 3x5 tự làm.

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
  const CLOSE_AFTER = 3 * 60 * 1000;        // tắt nhạc quá 3 phút: đóng hẳn AudioContext để trả luồng âm thanh cho máy
  const hz = (m) => 440 * 2 ** ((m - 69) / 12);
  let ctx = null, master, music, drums, wow, rainGain, noiseBuf, hatBus, snareBus, timer = 0, closeTimer = 0;
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
    hatBus = filter("highpass", 7500); hatBus.connect(drums);                     // dùng chung, không tạo bộ lọc mỗi nhịp
    snareBus = filter("bandpass", 1700, 0.9); snareBus.connect(drums);
    const lfo = ctx.createOscillator();  // băng cassette chạy hơi lệch tốc độ (wow) -> phím đàn hơi chao
    lfo.frequency.value = 0.33; wow = gain(6); lfo.connect(wow); lfo.start();
    noiseBuf = buffer(2, (d) => { for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; });
    const crackle = buffer(5, (d) => {  // tiếng lách tách của đĩa than + chút xì nền
      for (let i = 0; i < d.length; i++) d[i] = Math.random() < 0.0005 ? (Math.random() * 2 - 1) * 0.8 : (Math.random() * 2 - 1) * 0.01;
    });
    loop(crackle, filter("highpass", 900), gain(0.35)).connect(master);
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
  function noise(t, dur, vel, bus) {
    const src = ctx.createBufferSource(), g = ctx.createGain();
    src.buffer = noiseBuf;
    g.gain.setValueAtTime(vel, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(g).connect(bus);
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
    noise(t, 0.2, vel, snareBus);
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
    if (pos % 2 === 0 && Math.random() < 0.9) noise(t, 0.045, (pos % 4 === 0 ? 0.09 : 0.05) * hum(), hatBus);
    if (pos % 2 === 0 && bar % 4 !== 3 && Math.random() < 0.2) {  // giai điệu thưa, đi bậc liền
      lastNote = Math.max(0, Math.min(MELODY.length - 1, lastNote + [-2, -1, -1, 1, 1, 2][Math.floor(Math.random() * 6)]));
      lead(MELODY[lastNote], t, STEP * (2 + Math.floor(Math.random() * 3)), 0.05);
    }
  }
  // xếp lịch trước 0,5 giây khi cửa sổ đang hiện (ít node âm thanh sống cùng lúc); cửa sổ bị ẩn / thu nhỏ thì
  // setInterval chỉ chạy khoảng 1 lần/giây, nên xếp trước 1,5 giây để nhạc vẫn liền
  function tick() {
    const ahead = document.hidden ? 1.5 : 0.5;
    while (nextTime < ctx.currentTime + ahead) { schedule(step, nextTime); nextTime += STEP; step++; }
  }

  async function start() {
    if (on) return;
    on = true;  // bật ngay để nút đổi trạng thái liền; nhạc bắt đầu khi âm thanh sẵn sàng
    clearTimeout(closeTimer);
    try {
      if (!ctx) init();
      await ctx.resume();
    } catch { on = false; return; }  // máy không có thiết bị âm thanh: bỏ qua, cảnh vẫn chạy
    if (!on) return;
    nextTime = ctx.currentTime + 0.12; t0 = nextTime; step = 0; bar = -1;
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setTargetAtTime(vol, ctx.currentTime, 0.4);
    tick();
    timer = setInterval(tick, 200);
  }
  function stop() {
    if (!on) return;
    on = false;
    clearInterval(timer);
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setTargetAtTime(0, ctx.currentTime, 0.15);
    setTimeout(() => { if (!on && ctx) ctx.suspend(); }, 700);  // các nốt đã xếp lịch tắt theo, không kêu tiếp
    closeTimer = setTimeout(() => { if (!on && ctx) { ctx.close(); ctx = null; } }, CLOSE_AFTER);
  }
  return {
    start, stop,
    toggle() { return on ? (stop(), false) : (start(), true); },
    get on() { return on; },
    get rain() { return rain; },
    setRain(v) { rain = !!v; if (ctx && rainGain) rainGain.gain.setTargetAtTime(rain ? 0.5 : 0, ctx.currentTime, 0.5); },
    setVolume(v) { vol = Math.max(0, Math.min(1, v)); if (ctx && on) master.gain.setTargetAtTime(vol, ctx.currentTime, 0.1); },
    beat() { return on && ctx ? (ctx.currentTime - t0) / BEAT : null; },  // số phách đã chơi, để robot nhún theo nhạc
    BPM,
  };
})();


// ===================================================================== cảnh văn phòng (isometric 2:1)
const Office = (() => {
  // Logic chạy trên tọa độ sàn (gx, gy) tính bằng ô; màn hình: x = OX + (gx - gy) * 16, y = OY + (gx + gy) * 8 - độ cao.
  // gx chạy xuống-phải, gy chạy xuống-trái; độ sâu = gx + gy (lớn = gần người xem, vẽ sau).
  const TW = 32, TH = 16, HW = TW / 2, HH = TH / 2;   // 1 ô sàn = hình thoi 32 x 16 px thế giới
  const COLS = 4, CW = 3.5, ROWD = 4.6, TOP = 2.0;          // bước cột (gx), bước hàng bàn (gy) và khoảng cách bàn hàng đầu tới tường phải (gy), tính bằng ô
  const WALLH = 84, LOUNGE_D = 3.3, GAP_L = 4.25;     // cao tường (px), bề sâu khu nghỉ, lối xuống khu nghỉ (giữa sofa và máy cà phê)
  const TAG_DX = 0.6, TAG_DY = 0.4;                   // bảng tên nằm dưới ghế / robot của chính bàn đó
  const SEAT_Z = 5.5;                                 // độ cao mặt ghế (px)
  const SPEED = 2.4;                                  // ô / giây (khoảng 34 px màn hình / giây như bản cũ)
  const FPS = 30, IDLE_FPS = 6;                       // có gì chuyển động / tất cả đang nghỉ
  const BODY = ["#6c9cf0", "#f07a8e", "#8fcf6a", "#e9b45f", "#b096f0", "#5fc9e8", "#f09a5f", "#7fd6b5"];
  const tr = (s) => (typeof I18N !== "undefined" && I18N.lang === "en" && I18N.tr(s)) || s;
  let cv = null, g = null, layer = null, stage = null, inner = null, wall = null, addBtn = null;
  let bg = null, bgKey = "";        // canvas nền vẽ sẵn + khóa: đổi khóa thì vẽ lại
  let GX = 15, GY = 8, OX = 0, OY = 0, W = 400, H = 300;   // cỡ sàn (ô), gốc chiếu, cỡ thế giới (px)
  let rows = 1, raf = 0, tmo = 0, lastT = 0, visible = false, layoutKey = "";
  let ox = 0, oy = 0;               // gốc cộng thêm cho pt() (0 khi vẽ sprite, OX/OY khi vẽ nền)
  let WINS = [], FURN = [];         // cửa sổ trên tường trái, đồ khu nghỉ (tính lại khi đổi số hàng)
  let sprites = {}, sprKey = "";    // sprite đồ đạc vẽ sẵn theo giao diện
  const bots = new Map();           // tên tài khoản -> robot
  const fx = [];                    // hạt hiệu ứng (tọa độ màn hình): khói, pháo giấy, "+điểm", nốt nhạc, zzz

  const SEAT_DX = 0.9, SEAT_DY = 1.55;              // ghế ở trước mặt bàn (phía +gy, gần người xem): robot quay lưng ra, nhìn màn hình về hướng 1-2 giờ
  const seatGy = (row) => TOP + row * ROWD + SEAT_DY;
  const corridorY = () => seatGy(rows - 1) + 2.4;
  const loungeTop = () => corridorY() + 0.5;
  const frontY = () => loungeTop() + 2.3;           // hàng đứng phía trước đồ khu nghỉ
  const cellOf = (i) => ({ col: i % COLS, row: Math.floor(i / COLS) });
  const deskGx = (col) => col * CW + 0.8, deskGy = (row) => TOP + row * ROWD;   // góc gx/gy nhỏ nhất của bàn (rộng 2 x sâu 1)
  const seat = (i) => { const { col, row } = cellOf(i); return { gx: deskGx(col) + SEAT_DX, gy: seatGy(row) }; };
  const gapX = (col) => col * CW + 3.9;             // khe giữa các cột bàn: lối đi xuống hành lang
  const slotCenter = (i) => { const { col, row } = cellOf(i); return iso(deskGx(col) + 1, deskGy(row) + 0.5); };  // giữa chỗ bàn thứ i
  const LOUNGE_SPOTS = () => {
    const L = loungeTop(), fy = frontY();
    return [
      { gx: 1.5, gy: L + 1.15, pose: "sit", what: "sofa", z: 7.5, bias: 1.5 }, { gx: 2.7, gy: L + 1.15, pose: "sit", what: "sofa", z: 7.5, bias: 1.5 },
      { gx: 5.3, gy: fy, pose: "stand", what: "coffee" }, { gx: 6.55, gy: fy, pose: "stand", what: "water", face: "-gy" },
      { gx: 7.9, gy: fy, pose: "stand", what: "plant", face: "-gy" }, { gx: 13.4, gy: fy, pose: "stand", what: "arcade", face: "-gy" },
      { gx: 9.5, gy: fy, pose: "stand", what: "rug" }, { gx: 11.5, gy: fy, pose: "stand", what: "rug" },
    ];
  };
  // tính cỡ sàn / thế giới từ số hàng bàn; chiều cao thế giới = từ đỉnh tường đến góc sàn xa nhất
  function geom() {
    GX = Math.ceil(COLS * CW + 0.5);
    GY = Math.ceil(loungeTop() + LOUNGE_D);
    OX = GY * HW + 6; OY = WALLH + 6;
    W = (GX + GY) * HW + 12; H = OY + (GX + GY) * HH + 8;
    const n = Math.max(1, Math.min(4, Math.floor(GY / 3.6))), len = GY * HW, ww = 36;
    WINS = Array.from({ length: n }, (_, i) => ({ u: Math.round(len * (i + 0.5) / n - ww / 2), v: 20, w: ww, h: 32 }));
    const L = loungeTop(), y0 = L + 0.5;
    FURN = [["sofa", 0.6, y0, 3, 1], ["coffee", 4.9, y0 + 0.1, 0.8, 0.8], ["water", 6.2, y0 + 0.15, 0.7, 0.7],
            ["plant", 7.5, y0 + 0.1, 0.8, 0.8], ["arcade", 12.9, y0, 1, 0.9]].map(([key, gx0, gy0, gw, gd]) => {
      const p = iso(gx0, gy0);
      return { key, gx0, gy0, gw, gd, d: gx0 + gw / 2 + gy0 + gd / 2, sx: Math.round(p.x), sy: Math.round(p.y) };
    });
  }
  const iso = (gx, gy, z = 0) => ({ x: OX + (gx - gy) * HW, y: OY + (gx + gy) * HH - z });
  const qz = (x, y, z) => [Math.round((x - y) * HW), Math.round((x + y) * HH - z)];   // điểm cục bộ trong sprite
  const hash = (s) => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);

  // ------------------------------------------------------------ bảng màu theo giao diện (tính 1 lần cho mỗi giao diện)
  const PALETTES = {
    cyber: { cyber: true, dark: true, wallR: "#1d1240", wallL: "#140c2c", stripe: "rgba(255,255,255,.035)", base: "#05d9e8",
      floor: "#120a26", floor2: "#170d30", gridIso: "rgba(5,217,232,.22)",
      desk: "#25184a", deskSide: "#190f36", deskTop: "#33246a", deskEdge: "#05d9e8", leg: "#0d0820",
      mon: "#0b0f1f", monEdge: "#ff2a6d", sofa: "#5a1846", sofa2: "#7a2160", sofaSide: "#43102f", rug: "#2a1150", rug2: "#ff2a6d",
      shadow: "rgba(0,0,0,.45)", outline: "#05030d", plant: "#05d9e8", pot: "#3a2470",
      chair: "#3a1f66", chairHi: "#ff2a6d", chairSide: "#2b1750", clock: "#fcee0a", board: "#05d9e8", boardBg: "#0b0f1f", total: "#fcee0a",
      signBox: "#0b0617", signBg: "#1a0b33", frame: "#05d9e8", sill: "#ff2a6d" },
    dark: { cyber: false, dark: true, wallR: "#323850", wallL: "#262b3d", stripe: "rgba(255,255,255,.03)", base: "#1d2130",
      floor: "#3a3546", floor2: "#322e3e", gridIso: null,
      desk: "#5a3e2e", deskSide: "#46301f", deskTop: "#76523b", deskEdge: "#8d6448", leg: "#2c1f17",
      mon: "#1a1d26", monEdge: "#444b5e", sofa: "#4a5d8a", sofa2: "#5c71a3", sofaSide: "#3a4a70", rug: "#4b3a52", rug2: "#6a5470",
      shadow: "rgba(0,0,0,.35)", outline: "#12141b", plant: "#4f9a5c", pot: "#8a5a44",
      chair: "#2f6f8f", chairHi: "#4a8fb0", chairSide: "#235672", clock: "#7dfc9a", board: "#9aa0ac", boardBg: "#fbfcfe", total: "#1f8f4e",
      signBox: "#12141b", signBg: "#23283a", frame: "#12141b", sill: "#1d2130" },
    light: { cyber: false, dark: false, wallR: "#ece6da", wallL: "#d8cfbd", stripe: "rgba(0,0,0,.035)", base: "#b9a98f",
      floor: "#d6c4a6", floor2: "#cbb893", gridIso: null,
      desk: "#93603f", deskSide: "#74492f", deskTop: "#b07a52", deskEdge: "#c48c61", leg: "#5e3d28",
      mon: "#2a2e38", monEdge: "#4a5060", sofa: "#5b7cc4", sofa2: "#7393d6", sofaSide: "#4562a3", rug: "#c97f6a", rug2: "#e0a08d",
      shadow: "rgba(60,40,20,.18)", outline: "#2a2420", plant: "#4f9a5c", pot: "#b5694a",
      chair: "#3f7fa8", chairHi: "#62a2c8", chairSide: "#2e6486", clock: "#7dfc9a", board: "#9aa0ac", boardBg: "#fbfcfe", total: "#1f8f4e",
      signBox: "#2a2420", signBg: "#fdfbf6", frame: "#2a2420", sill: "#b9a98f" },
  };
  const themeKey = () => (document.documentElement.getAttribute("data-skin") === "cyberpunk" ? "cyber"
    : document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light");

  // ------------------------------------------------------------ font pixel 3x5 cho số (nét ở canvas 1x)
  const GLYPHS = {
    0: "111 101 101 101 111", 1: "010 110 010 010 111", 2: "111 001 111 100 111", 3: "111 001 111 001 111",
    4: "101 101 111 001 001", 5: "111 100 111 001 111", 6: "111 100 111 101 111", 7: "111 001 010 010 010",
    8: "111 101 111 101 111", 9: "111 101 111 001 111", "+": "000 010 111 010 000", ":": "0 1 0 1 0",
    ",": "00 00 00 01 10", " ": "0 0 0 0 0", z: "111 001 010 100 111", "(": "01 10 10 10 01",
    "♪": "0110 0101 0100 1100 1100", "♥": "01010 11111 11111 01110 00100",
  };
  const FONT = Object.fromEntries(Object.entries(GLYPHS).map(([c, s]) => [c, s.split(" ")]));
  function pixWidth(s, sc) { let w = 0; for (const ch of s) w += ((FONT[ch] || FONT[" "])[0].length + 1) * sc; return w - sc; }
  // vẽ chuỗi bằng font pixel; mỗi hàng của một ký tự gộp các ô liền nhau thành 1 lệnh fillRect
  function pix(s, x, y, c, sc = 1, align = "center") {
    let cx = Math.round(align === "center" ? x - pixWidth(s, sc) / 2 : x);
    g.fillStyle = c;
    for (const ch of s) {
      const rowsOf = FONT[ch] || FONT[" "];
      rowsOf.forEach((r, ry) => {
        for (let i = 0; i < r.length; i++) {
          if (r[i] !== "1") continue;
          let j = i; while (r[j + 1] === "1") j++;
          g.fillRect(cx + i * sc, Math.round(y) + ry * sc, (j - i + 1) * sc, sc);
          i = j;
        }
      });
      cx += (rowsOf[0].length + 1) * sc;
    }
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
    rows = Math.max(1, Math.ceil((names.length + 1) / COLS));  // +1: luôn chừa đúng 1 chỗ bàn trống cho nút thêm tài khoản
    geom();
    for (const n of [...bots.keys()]) if (!names.includes(n)) { bots.get(n).el.remove(); bots.delete(n); }
    names.forEach((name, i) => {
      let b = bots.get(name);
      if (!b) {
        const color = BODY[hash(name) % BODY.length];
        b = { name, gx: 0, gy: 0, sx: 0, sy: 0, lift: 0, depth: 0, fa: "+gy", path: [], where: null, pose: "stand", act: null, spot: null, until: 0, color,
              dark: shade(color, -0.35), light: shade(color, 0.25), blink: 0, log: "", logUntil: 0, celebrate: 0,
              today: st(name).today, el: document.createElement("div"), bub: { text: null, cls: "", x: -1, y: -1 } };
        b.el.className = "ob";
        b.el.innerHTML = `<div class="ob-bubble" data-no-i18n hidden></div><button type="button" class="ob-tag"></button>`;
        b.tagEl = b.el.querySelector(".ob-tag"); b.bubEl = b.el.querySelector(".ob-bubble");
        b.tagEl.onclick = (e) => { e.stopPropagation(); toggleCard(name); };
        b.tagEl.title = "Xem nhanh tài khoản này";
        layer.appendChild(b.el);
        bots.set(name, b);
      }
      b.index = i;
      // bảng tên: chỉ dựng lại khi điểm / ảnh đại diện đổi; vị trí ở mép trước của bàn (đổi khi số hàng bàn đổi)
      const s = st(name), html = `${avatarHtml(name, "avatar-xs rounded-circle")}<span>${esc(name)}</span>`
        + `<b>${typeof s.points === "number" ? fmt(s.points) : ""}</b>`;
      if (b.tagHtml !== html) { b.tagEl.innerHTML = html; b.tagHtml = html; }
      const { col, row } = cellOf(i), sp = seat(i), tp = iso(sp.gx + TAG_DX, sp.gy + TAG_DY);
      b.tagEl.style.left = (tp.x / W * 100) + "%";
      b.tagEl.style.top = (tp.y / H * 100) + "%";
      b.bub.x = -1;  // W / H có thể đổi: đặt lại vị trí bong bóng ở khung hình tới
    });
    const key = names.join("\n") + "|" + rows;
    const slot = slotCenter(names.length);  // nút "+" ở giữa chỗ bàn trống kế tiếp (chỉ có 1 nút)
    addBtn.style.left = (slot.x / W * 100) + "%"; addBtn.style.top = (slot.y / H * 100) + "%";
    if (key !== layoutKey) {  // đổi danh sách tài khoản: dựng lại kích thước, đặt robot thẳng vào chỗ (không đi bộ)
      layoutKey = key;
      resize();
      for (const b of bots.values()) { b.act = null; b.path = []; b.where = null; }
    }
    for (const b of bots.values()) { update(b); locate(b); }
  }

  // vị trí màn hình + độ sâu của robot, tính 1 lần mỗi khung hình (vẽ, bong bóng, bấm chuột, hiệu ứng đều dùng)
  function locate(b) {
    const p = iso(b.gx, b.gy), still = !b.path.length && b.where;
    b.sx = Math.round(p.x); b.sy = Math.round(p.y);
    const L = loungeTop(), onSofa = b.gx > 0.5 && b.gx < 3.7 && b.gy > L + 0.4 && b.gy < L + 1.6;  // trong chân sofa: giữ độ cao + độ sâu để không "chui" ra sau sofa khi đứng dậy
    b.lift = still && b.pose === "sit" ? b.where.z || 0 : onSofa ? 7.5 : 0;
    b.depth = b.gx + b.gy + (onSofa ? 1.5 : still ? b.where.bias || 0 : 0);
  }
  // hướng mặt khi đứng yên: ngồi bàn thì nhìn màn hình (-gy), còn lại quay về phía người xem
  const restFace = (to) => (to.kind === "desk" && to.pose === "sit" ? "-gy" : to.face || "+gy");
  function place(b, to) { b.gx = to.gx; b.gy = to.gy; b.path = []; b.where = to; b.pose = to.pose; b.fa = restFace(to); locate(b); }
  function walk(b, to) {  // đi theo lối đi: ra khe giữa các bàn, xuống hành lang, qua lối giữa sofa và máy cà phê, rồi mới tới chỗ mới
    const pts = [], cy = corridorY(), fy = frontY(), from = b.where, eps = 1e-6, moving = b.path.length > 0;
    const add = (gx, gy) => {  // bỏ điểm trùng điểm trước để mỗi đoạn đi dọc đúng 1 trục sàn
      const l = pts.length ? pts[pts.length - 1] : b;
      if (Math.abs(l.gx - gx) > eps || Math.abs(l.gy - gy) > eps) pts.push({ gx, gy });
    };
    // đang đi dở thì `from` chỉ là đích cũ: luôn tính khu vực theo vị trí thật (gx, gy) của robot
    const area = b.gy < cy - eps ? "desk" : b.gy > cy + eps ? "lounge" : "corr";
    const nearCol = () => Math.max(0, Math.min(COLS - 1, Math.round((b.gx - 3.9) / CW)));
    if (!moving && from && from.kind === "desk" && to.kind === "desk" && from.col === to.col && from.row === to.row) {
      add(gapX(to.col), b.gy); add(gapX(to.col), to.gy); add(to.gx, to.gy);  // ngồi <-> đứng chờ sau ghế: vòng qua khe bên phải, không cắt qua ghế
    } else {
      if (to.kind === "lounge" && area === "lounge") add(b.gx, fy);  // đã ở khu nghỉ: ra hàng trước rồi đi ngang
      else if (area === "desk") { const c = !moving && from && from.kind === "desk" ? from.col : nearCol(); add(gapX(c), b.gy); add(gapX(c), cy); }
      else if (area === "lounge") { add(b.gx, fy); add(GAP_L, fy); add(GAP_L, cy); }
      if (to.kind === "desk") { add(gapX(to.col), cy); add(gapX(to.col), to.gy); }
      else { if (area !== "lounge") { add(GAP_L, cy); add(GAP_L, fy); } add(to.gx, fy); }
      add(to.gx, to.gy);
    }
    b.path = pts; b.where = to; b.pose = "stand";
  }
  function target(b, act) {
    const { col, row } = cellOf(b.index), s = seat(b.index);
    if (act.at === "desk") return { kind: "desk", col, row, gx: s.gx, gy: s.gy, pose: "sit", z: SEAT_Z };
    if (act.at === "wait") return { kind: "desk", col, row, gx: s.gx, gy: s.gy + 1.2, pose: "stand", face: "+gy" };  // đứng chờ ngay sau ghế của mình
    return pickSpot(b);
  }
  // việc làm ở từng chỗ trong khu nghỉ (chọn ngẫu nhiên khi tới): nằm nghỉ / viết nhật ký trên sofa, pha cà phê, uống nước,
  // tưới cây, chơi máy game, nhảy theo nhạc / vươn vai trên thảm; robot ở thảm cạnh mèo đang ngủ thì vuốt ve mèo
  const TASKS = { sofa: ["rest", "diary"], coffee: ["coffee"], water: ["drink"], plant: ["water"], arcade: ["game"], rug: ["dance", "stretch"] };
  function loungeTask(b) {  // việc đang làm (chỉ khi đứng yên ở khu nghỉ), null nếu không
    if (!b.act || b.act.at !== "lounge" || b.path.length || !b.where || b.where.kind !== "lounge" || b.celebrate > performance.now()) return null;
    if (b.where.what === "rug" && catNear(b)) return "pet";
    return b.task || null;
  }
  function pickSpot(b) {
    const taken = new Set([...bots.values()].filter((o) => o !== b && o.spot).map((o) => o.spot.what + o.spot.gx));
    const free = LOUNGE_SPOTS().filter((s) => !taken.has(s.what + s.gx));
    const s = free.length ? free[Math.floor(Math.random() * free.length)]
      : { gx: 6 + Math.random() * 6, gy: frontY() + Math.random() * 0.6, pose: "stand", what: "rug" };
    b.spot = s;
    const tasks = TASKS[s.what] || ["dance"];
    b.task = tasks[Math.floor(Math.random() * tasks.length)];
    b.until = performance.now() + (b.task === "rest" || b.task === "diary" ? 18000 : 8000) + Math.random() * 12000;
    return { kind: "lounge", ...s };
  }
  function update(b) {
    const act = activity(b.name), prev = b.act;
    const sig = (a) => a && a.at + a.screen;
    if (prev && prev.face !== "happy" && act.face === "happy") {  // vừa chạy xong: ăn mừng tại bàn một lúc rồi mới đi nghỉ
      b.celebrate = performance.now() + 4500;
      burst(b.sx, b.sy - b.lift - 26, "confetti", 26);
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

  // ------------------------------------------------------------ con mèo văn phòng: đi dạo, ăn ở bát, ngủ trên thảm, ngồi liếm lông
  // Đi theo 2 lối thoáng như robot: hành lang (gy = corridorY) và lối trước khu nghỉ (gy = frontY + 0.6); đổi lối qua khe GAP_L.
  // Bát ăn và chỗ ngủ là "nhánh" thẳng góc từ lối trước, nên mọi đoạn đường đều dọc 1 trục sàn, không xuyên đồ đạc.
  const CAT_SPEED = 1.5;
  const cat = { gx: 0, gy: 0, sx: 0, sy: 0, path: [], st: "sleep", goal: "sleep", until: 0, fa: "+gy", hunger: 0.4, food: 1, placed: false };
  const catLane = () => frontY() + 0.6;
  const bowlAt = () => ({ gx: 14.4, gy: loungeTop() + 1.6 });  // góc phải, trước máy game một chút
  const catSpot = (goal) => (goal === "eat" ? { gx: bowlAt().gx - 0.55, gy: bowlAt().gy } : goal === "sleep" ? { gx: 10.6, gy: frontY() + 0.35 } : null);
  function catNear(b) {  // robot đứng sát mèo đang ngủ trên thảm -> vuốt ve
    return cat.st === "sleep" && !cat.path.length && Math.abs(b.gx - cat.gx) < 1.3 && Math.abs(b.gy - cat.gy) < 0.8;
  }
  function catRoute(to) {
    const pts = [], cy = corridorY(), fl = catLane(), eps = 1e-6;
    const add = (gx, gy) => { const l = pts.length ? pts[pts.length - 1] : cat; if (Math.abs(l.gx - gx) > eps || Math.abs(l.gy - gy) > eps) pts.push({ gx, gy }); };
    const inCorr = Math.abs(cat.gy - cy) < eps, toCorr = Math.abs(to.gy - cy) < eps;
    if (!inCorr) add(cat.gx, fl);                       // từ bát / chỗ ngủ: lùi về lối trước
    if (inCorr && !toCorr) { add(GAP_L, cy); add(GAP_L, fl); }
    if (!inCorr && toCorr) { add(GAP_L, fl); add(GAP_L, cy); }
    if (toCorr) add(to.gx, cy); else { add(to.gx, fl); add(to.gx, to.gy); }
    cat.path = pts;
  }
  function catThink(now) {  // chọn việc tiếp theo: đói thì đi ăn, tối hay vừa ăn xong thì ngủ, còn lại đi dạo rồi ngồi / liếm lông
    const r = Math.random(), night = isNight();
    let goal;
    if (cat.hunger > 1 && cat.food > 0.15) goal = "eat";
    else if (cat.st === "eat" || r < (night ? 0.7 : 0.2)) goal = "sleep";  // ban ngày chủ yếu đi dạo
    else if (r < 0.8) goal = "sit";
    else goal = "groom";
    let to = catSpot(goal);
    if (!to && goal === "sit") {  // đi dạo tới 1 điểm ngẫu nhiên trên hành lang hoặc lối trước rồi ngồi
      to = Math.random() < 0.5 ? { gx: 0.6 + Math.random() * 13.8, gy: corridorY() } : { gx: 4.6 + Math.random() * 9.6, gy: catLane() };
    }
    cat.goal = goal;
    if (to) catRoute(to); else cat.path = [];
    if (cat.path.length) cat.st = "walk"; else catArrive(now);
  }
  function catArrive(now) {
    cat.st = cat.goal;
    if (cat.goal === "eat") cat.fa = "+gx";                          // bát ở phía +gx: mèo quay mặt ra người xem khi ăn
    else if (cat.goal !== "walk" && cat.fa[0] === "-") cat.fa = cat.fa === "-gy" ? "+gx" : "+gy";  // ngồi / ngủ: quay mặt ra người xem
    cat.until = now + (cat.goal === "eat" ? 6000 : cat.goal === "sleep" ? (isNight() ? 40000 : 15000) + Math.random() * 20000 : 5000 + Math.random() * 7000);
  }
  function catStep(dt, now) {
    if (!cat.placed) { const s = catSpot("sleep"); cat.gx = s.gx; cat.gy = s.gy; cat.placed = true; cat.until = now + 8000 + Math.random() * 10000; }
    cat.hunger += dt / 90;
    if (cat.st === "eat") { cat.hunger = Math.max(0, cat.hunger - dt / 5); cat.food = Math.max(0, cat.food - dt * 0.06); }
    else cat.food = Math.min(1, cat.food + dt / 150);  // bát tự đầy lại từ từ
    if (cat.path.length) {
      const p = cat.path[0], dx = p.gx - cat.gx, dy = p.gy - cat.gy, d = Math.hypot(dx, dy), mv = CAT_SPEED * dt;
      if (Math.abs(dx) > 1e-6 || Math.abs(dy) > 1e-6) cat.fa = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "+gx" : "-gx") : (dy > 0 ? "+gy" : "-gy");  // nhìn theo hướng đi
      if (d <= mv) { cat.gx = p.gx; cat.gy = p.gy; cat.path.shift(); if (!cat.path.length) catArrive(now); }
      else { cat.gx += (dx / d) * mv; cat.gy += (dy / d) * mv; }
    } else if (now > cat.until) catThink(now);
    const s = iso(cat.gx, cat.gy); cat.sx = Math.round(s.x); cat.sy = Math.round(s.y);
  }
  function drawBowl(P) {  // bát bầu dục 2:1 nằm trên sàn: thành bát dày 2 px, trong lòng là hạt thức ăn
    const b = bowlAt(), s = iso(b.gx, b.gy), x = Math.round(s.x) + 0.5, y = Math.round(s.y), rim = P.cyber ? "#ff2a6d" : "#d9534f";
    const ell = (cy, rx, ry, c) => { g.fillStyle = c; g.beginPath(); g.ellipse(x, cy, rx, ry, 0, 0, Math.PI * 2); g.fill(); };
    ell(y + 1, 7, 3, P.shadow);
    ell(y, 6, 3, shade(rim, -0.3));                  // thân bát (phần khuất)
    ell(y - 2, 6, 3, rim);                            // miệng bát
    ell(y - 2, 4, 2, cat.food > 0.05 ? "#b7793a" : shade(rim, -0.45));
    if (cat.food > 0.5) { R(x - 2.5, y - 4, 2, 1, "#d69a55"); R(x + 0.5, y - 3, 2, 1, "#d69a55"); }
  }
  // mèo khối isometric như robot: thân, đầu, tai, đuôi, chân là các hộp; hướng mặt cat.fa ("+gx" / "-gx" / "+gy" / "-gy").
  // Tọa độ cục bộ (f = phía trước theo hướng mặt, s = sang ngang) đổi sang (gx, gy) rồi vẽ các khối từ xa tới gần.
  function drawCat(t, P) {
    const O = P.cyber ? P.outline : "#6b3a17", body = "#f0a24b", dark = "#c8742c", light = "#ffd59a", fa = cat.fa || "+gy";
    const K = 1.45;  // cỡ mèo: mọi số đo cục bộ bên dưới nhân K (khoảng 1/2 chiều cao robot)
    const st = cat.st, walk = st === "walk", stepA = walk ? Math.floor(t * 8) % 2 : 0;
    const sg = fa[0] === "-" ? -1 : 1, alongX = fa[2] === "x";
    const toG = (f, s) => (alongX ? [sg * f, s] : [s, sg * f]);
    const parts = [];
    const part = (f0, f1, s0, s1, z0, z1, top, left, right, outline = true) => {
      const [ax, ay] = toG(f0 * K, s0 * K), [bx, by] = toG(f1 * K, s1 * K);
      z0 *= K; z1 *= K;
      const x0 = Math.min(ax, bx), x1 = Math.max(ax, bx), y0 = Math.min(ay, by), y1 = Math.max(ay, by);
      parts.push({ d: (x0 + x1) / 2 + (y0 + y1) / 2, z0, draw: () => (outline ? boxO(x0, y0, x1, y1, z0, z1, top, left, right, O) : box(x0, y0, x1, y1, z0, z1, top, left, right)) });
    };
    const head = { f0: 0, f1: 0, z0: 0, z1: 0 };
    const mox = ox, moy = oy;
    ox = cat.sx; oy = cat.sy;
    try {
      flat(-0.2 * K, -0.2 * K, 0.2 * K, 0.2 * K, 0, P.shadow);
      if (st === "sleep") {  // nằm cuộn tròn: thân dẹt, đầu gối lên thân, đuôi quấn phía trước
        part(-0.18, 0.14, -0.12, 0.12, 0, 4, light, body, dark);
        part(0.06, 0.24, -0.1, 0.08, 1, 5.5, light, body, dark); Object.assign(head, { f0: 0.06, f1: 0.24, s0: -0.1, s1: 0.08, z1: 5.5 });
        part(0.1, 0.15, -0.09, -0.04, 5.5, 7, dark, dark, dark, false); part(0.1, 0.15, 0.02, 0.07, 5.5, 7, dark, dark, dark, false);
        part(-0.16, 0.1, 0.12, 0.17, 0, 1.5, dark, dark, dark, false);
      } else if (st === "sit" || st === "groom") {  // ngồi thẳng, đuôi nằm trên sàn vẫy qua lại
        const sway = Math.sin(t * 2) > 0 ? 0.03 : -0.03;
        part(-0.3, -0.12, -0.03 + sway, 0.03 + sway, 0, 1.5, dark, body, dark, false);
        part(-0.14, 0.08, -0.09, 0.09, 0, 8, light, body, dark);
        part(-0.04, 0.14, -0.1, 0.1, 7, 12, light, body, dark); Object.assign(head, { f0: -0.04, f1: 0.14, s0: -0.1, s1: 0.1, z1: 12 });
        part(0.02, 0.08, -0.09, -0.04, 12, 14, dark, dark, dark, false); part(0.02, 0.08, 0.04, 0.09, 12, 14, dark, dark, dark, false);
        if (st === "groom" && Math.floor(t * 3) % 2) part(0.1, 0.17, 0.02, 0.07, 6, 10, light, body, dark, false);  // giơ chân liếm
        else part(0.06, 0.12, -0.06, 0.06, 0, 2, light, body, dark, false);                                       // 2 chân trước
      } else {  // đứng / đi / ăn
        const eat = st === "eat", bob = eat && Math.floor(t * 4) % 2 ? 1 : 0;
        for (const [f, s, ph] of [[0.12, -0.06, 0], [0.12, 0.06, 1], [-0.14, -0.06, 1], [-0.14, 0.06, 0]]) {
          const lift = walk && (ph === stepA) ? 1 : 0;
          part(f - 0.03, f + 0.03, s - 0.03, s + 0.03, lift, 3, dark, dark, dark, false);
        }
        part(-0.2, 0.16, -0.09, 0.09, 3, 8, light, body, dark);
        const sway = walk ? (stepA ? 0.02 : -0.02) : Math.sin(t * 2) > 0 ? 0.02 : -0.02;
        part(-0.26, -0.2, -0.025 + sway, 0.025 + sway, 6, 13, dark, body, dark, false);                     // đuôi dựng
        const hz = eat ? 2 - bob : 7, hf = eat ? 0.18 : 0.12;
        part(hf, hf + 0.18, -0.1, 0.1, hz, hz + 5, light, body, dark); Object.assign(head, { f0: hf, f1: hf + 0.18, s0: -0.1, s1: 0.1, z1: hz + 5 });
        part(hf + 0.05, hf + 0.1, -0.09, -0.04, hz + 5, hz + 7, dark, dark, dark, false); part(hf + 0.05, hf + 0.1, 0.04, 0.09, hz + 5, hz + 7, dark, dark, dark, false);
      }
      parts.sort((a, c) => a.d - c.d || a.z0 - c.z0);
      for (const p of parts) p.draw();
      for (const [f0, f1] of [[-0.12, -0.09], [-0.03, 0]]) {  // sọc lưng trên mặt trên của thân
        if (st === "sit" || st === "groom") break;
        const [ax, ay] = toG(f0 * K, -0.09 * K), [bx, by] = toG(f1 * K, 0.09 * K);
        flat(Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by), (st === "sleep" ? 4 : 8) * K, dark);
      }
      // mặt: chỉ vẽ khi đầu quay về phía người xem (+gy: mặt trái, +gx: mặt phải của khối đầu)
      if (fa === "+gy" || fa === "+gx") {
        const [ax, ay] = toG(head.f1 * K, head.s0 * K), [bx, by] = toG(head.f1 * K, head.s1 * K);
        const p = fa === "+gy" ? pt(Math.min(ax, bx), ay, head.z1 * K) : pt(ax, Math.max(ay, by), head.z1 * K);
        g.save(); g.transform(1, fa === "+gy" ? 0.5 : -0.5, 0, 1, p[0], p[1]);
        const closed = st === "sleep" || st === "eat";
        R(0, 4, 5, 3, light);                                                        // mõm sáng màu
        if (closed) { R(0, 3, 2, 1, O); R(3, 3, 2, 1, O); } else { R(0, 2, 1, 2, "#1d1d1d"); R(4, 2, 1, 2, "#1d1d1d"); }
        R(2, 4, 1, 1, "#ff8fa0");
        g.restore();
      }
    } finally { ox = mox; oy = moy; }
  }

  // ------------------------------------------------------------ hiệu ứng (tọa độ màn hình)
  function burst(x, y, kind, n) {
    const cols = ["#ff5d73", "#ffd23f", "#4fd1c5", "#7aa2ff", "#b28dff", "#8fd16a"];
    for (let i = 0; i < n; i++) {
      fx.push({ kind, x, y, vx: (Math.random() - 0.5) * 60, vy: -30 - Math.random() * 50, life: 1.4 + Math.random(), age: 0,
                c: cols[i % cols.length] });
    }
  }
  function floatText(b, text) { fx.push({ kind: "text", text, x: b.sx, y: b.sy - b.lift - 36, vx: 0, vy: -10, life: 2.2, age: 0 }); }
  function onLog(e) {
    const b = bots.get(e.name);
    if (!b || !e.msg) return;
    b.log = e.msg.length > 70 ? e.msg.slice(0, 68) + "…" : e.msg;
    b.logUntil = performance.now() + 3500;
  }

  // ------------------------------------------------------------ vẽ: hình cơ bản
  function R(x, y, w, h, c) { g.fillStyle = c; g.fillRect(Math.round(x), Math.round(y), w, h); }
  const pt = (gx, gy, z = 0) => [Math.round(ox + (gx - gy) * HW), Math.round(oy + (gx + gy) * HH - z)];
  function poly(pts, c) {  // đa giác đặc; viền cùng màu để các mặt kề nhau không hở kẽ
    g.fillStyle = c; g.strokeStyle = c; g.lineWidth = 1; g.beginPath();
    pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])));
    g.closePath(); g.fill(); g.stroke();
  }
  const flat = (x0, y0, x1, y1, z, c) => poly([pt(x0, y0, z), pt(x1, y0, z), pt(x1, y1, z), pt(x0, y1, z)], c);
  function box(x0, y0, x1, y1, z0, z1, top, left, right) {  // khối hộp: mặt trên + mặt hướng +gy (trái) + mặt hướng +gx (phải, tối hơn)
    poly([pt(x0, y1, z0), pt(x1, y1, z0), pt(x1, y1, z1), pt(x0, y1, z1)], left);
    poly([pt(x1, y0, z0), pt(x1, y1, z0), pt(x1, y1, z1), pt(x1, y0, z1)], right);
    poly([pt(x0, y0, z1), pt(x1, y0, z1), pt(x1, y1, z1), pt(x0, y1, z1)], top);
  }
  const faceL = (x0, x1, z0, z1, y, c) => poly([pt(x0, y, z0), pt(x1, y, z0), pt(x1, y, z1), pt(x0, y, z1)], c);  // hình dán lên mặt trái
  function withWall(side, fn) {  // tọa độ cục bộ (u ngang theo tường, v từ đỉnh tường xuống) với phép nghiêng 2:1 của tường phải / trái
    g.save(); g.transform(side === "R" ? 1 : -1, 0.5, 0, 1, OX, OY - WALLH); fn(); g.restore();
  }

  // ------------------------------------------------------------ nền tĩnh
  // chỉ vẽ lại khi giao diện / số bàn / giờ:phút / điểm hôm nay / số robot đang làm đổi
  function staticKey(P, key) {
    const now = new Date(), total = officeTotal(), working = [...bots.values()].filter(isWorking).length;
    return `${key}|${layoutKey}|${now.getHours()}:${now.getMinutes()}|${total}|${working}|${S.officeRain ? 1 : 0}`;
  }
  function officeTotal() { return S.profiles.reduce((a, p) => a + (typeof st(p.name).today === "number" ? st(p.name).today : 0), 0); }
  // chỉ vẽ những thứ không có gì đứng sau: sàn, tường, thảm, đồ treo tường. Đồ đạc và ghế nằm trong danh sách xếp theo độ sâu.
  function drawStatic(P) {
    ox = OX; oy = OY;
    const L = loungeTop(), lenR = GX * HW, lenL = GY * HW, t = 0.25;
    for (let a = 0; a < GX; a++) for (let c = 0; c < GY; c++) flat(a, c, a + 1, c + 1, 0, (a + c) % 2 ? P.floor2 : P.floor);  // sàn caro
    if (P.gridIso) {  // Cyberpunk: lưới neon dọc theo các trục sàn
      g.strokeStyle = P.gridIso; g.lineWidth = 1; g.beginPath();
      for (let a = 0; a <= GX; a++) { const p = pt(a, 0), q = pt(a, GY); g.moveTo(p[0] + 0.5, p[1] + 0.5); g.lineTo(q[0] + 0.5, q[1] + 0.5); }
      for (let c = 0; c <= GY; c++) { const p = pt(0, c), q = pt(GX, c); g.moveTo(p[0] + 0.5, p[1] + 0.5); g.lineTo(q[0] + 0.5, q[1] + 0.5); }
      g.stroke();
    }
    flat(0, L, GX, L + 0.1, 0, P.base);  // vạch ngăn khu nghỉ
    {  // chỗ bàn trống kế tiếp: khung nét đứt trên sàn (nút "+" ở lớp HTML)
      const { col, row } = cellOf(S.profiles.length), x0 = deskGx(col), y0 = deskGy(row);
      g.save(); g.setLineDash([3, 3]); g.lineWidth = 1; g.strokeStyle = P.cyber ? "rgba(5,217,232,.7)" : P.dark ? "rgba(255,255,255,.3)" : "rgba(60,40,20,.35)";
      g.beginPath(); [pt(x0, y0), pt(x0 + 2, y0), pt(x0 + 2, y0 + 1), pt(x0, y0 + 1)].forEach((q, i) => (i ? g.lineTo(q[0] + 0.5, q[1] + 0.5) : g.moveTo(q[0] + 0.5, q[1] + 0.5)));
      g.closePath(); g.stroke(); g.restore();
    }
    poly([pt(0, GY), pt(GX, GY), pt(GX, GY, -5), pt(0, GY, -5)], P.wallL);                    // gờ sàn phía trước-trái
    poly([pt(GX, 0), pt(GX, GY), pt(GX, GY, -5), pt(GX, 0, -5)], shade(P.wallL, -0.3));        // gờ sàn phía trước-phải
    // thảm (hình thoi phẳng, lồng 3 lớp)
    flat(8.8, L + 1.8, 12.4, L + 3.1, 0, P.rug); flat(8.95, L + 1.95, 12.25, L + 2.95, 0, P.rug2); flat(9.15, L + 2.1, 12.05, L + 2.8, 0, P.rug);
    // hai bức tường: trái (tối hơn) và phải, mỗi bức có mép trên dày và đầu tường
    poly([pt(0, 0, WALLH), pt(0, GY, WALLH), pt(0, GY), pt(0, 0)], P.wallL);
    poly([pt(0, 0, WALLH), pt(GX, 0, WALLH), pt(GX, 0), pt(0, 0)], P.wallR);
    poly([pt(0, 0, WALLH), pt(0, GY, WALLH), pt(-t, GY, WALLH), pt(-t, -t, WALLH)], shade(P.wallL, 0.35));
    poly([pt(0, 0, WALLH), pt(GX, 0, WALLH), pt(GX, -t, WALLH), pt(-t, -t, WALLH)], shade(P.wallR, 0.35));
    poly([pt(0, GY, WALLH), pt(-t, GY, WALLH), pt(-t, GY), pt(0, GY)], shade(P.wallL, -0.2));
    poly([pt(GX, 0, WALLH), pt(GX, -t, WALLH), pt(GX, -t), pt(GX, 0)], shade(P.wallR, -0.2));
    withWall("L", () => {
      for (let u = 0; u < lenL; u += 16) R(u, 0, 8, WALLH, P.stripe);  // giấy dán tường sọc
      R(0, WALLH - 5, lenL, 5, P.base);                                  // chân tường
      for (const w of WINS) {  // khung cửa sổ + bậu (phần trong kính vẽ động)
        R(w.u - 2, w.v - 2, w.w + 4, 2, P.frame); R(w.u - 2, w.v + w.h, w.w + 4, 2, P.frame);
        R(w.u - 2, w.v, 2, w.h, P.frame); R(w.u + w.w, w.v, 2, w.h, P.frame);
        R(w.u - 4, w.v + w.h + 2, w.w + 8, 3, P.sill);
      }
    });
    withWall("R", () => {
      for (let u = 0; u < lenR; u += 16) R(u, 0, 8, WALLH, P.stripe);
      R(0, WALLH - 5, lenR, 5, P.base);
      R(12, 10, 76, 26, P.signBox); R(14, 12, 72, 22, P.signBg);   // biển tên (chữ ở lớp HTML)
      const now = new Date();                                         // đồng hồ số (dấu ":" nhấp nháy vẽ động)
      R(104, 12, 44, 16, P.outline); R(106, 14, 40, 12, "#0d1410");
      pix(`${String(now.getHours()).padStart(2, "0")} ${String(now.getMinutes()).padStart(2, "0")}`, 126, 15, P.clock, 2);
      R(160, 8, 72, 46, P.board); R(162, 10, 68, 42, P.boardBg);   // bảng điểm hôm nay (chữ "Hôm nay" / "đang làm" ở lớp HTML)
      pix(`+${officeTotal().toLocaleString("en-US")}`, 196, 26, P.total, 2);
    });
  }
  function ensureStatic(P, key) {
    const k2 = staticKey(P, key);
    if (k2 === bgKey && bg.width === W && bg.height === H) return;
    bgKey = k2;
    if (bg.width !== W || bg.height !== H) { bg.width = W; bg.height = H; }
    const main = g;
    g = bg.getContext("2d");
    try { g.clearRect(0, 0, W, H); drawStatic(P); } finally { g = main; ox = 0; oy = 0; }
    // chữ trên tường (lớp HTML): chỉ đổi khi số robot đang làm đổi
    const working = [...bots.values()].filter(isWorking).length, txt = `${working}/${S.profiles.length} đang làm`;
    if (wall.working.textContent !== txt) wall.working.textContent = txt;
  }

  function drawWindows(t, P) {  // phần trong kính: trời theo giờ thật, mây trôi / sao nhấp nháy, mưa; cắt theo hình bình hành của tường trái
    const hr = new Date().getHours() + new Date().getMinutes() / 60, day = hr >= 6 && hr < 18, dusk = (hr >= 17 && hr < 19) || (hr >= 5 && hr < 7);
    const sky = P.cyber ? "#1b0838" : dusk ? "#f4a06a" : day ? "#8fd0f5" : "#141a3a";
    const city = P.cyber ? ["#2b0f55", "#ff2a6d", "#05d9e8"] : day ? ["#7d93a8", "#c6d6e4", "#fff3b0"] : ["#232a52", "#2f3868", "#ffd56a"];
    withWall("L", () => WINS.forEach((w, wi) => {
      g.save(); g.beginPath(); g.rect(w.u, w.v, w.w, w.h); g.clip();  // không bao giờ vẽ tràn ra khung
      R(w.u, w.v, w.w, w.h, sky);
      if (P.cyber || !day) {
        for (let i = 0; i < 9; i++) { const sx = w.u + ((i * 37 + wi * 13) % (w.w - 2)), sy = w.v + ((i * 23) % 16); if (Math.sin(t * 2 + i) > -0.3) R(sx, sy, 1, 1, "#fff"); }
        if (!P.cyber && wi === WINS.length - 1) { R(w.u + 24, w.v + 5, 7, 7, "#f3efd6"); R(w.u + 26, w.v + 5, 5, 5, sky); }
      } else {
        const cx = w.u + ((t * 4 + wi * 30) % (w.w + 16)) - 12;  // mây trôi
        R(cx, w.v + 8, 14, 4, "#fff"); R(cx + 3, w.v + 5, 8, 3, "#fff");
        if (wi === 0) R(w.u + 5, w.v + 4, 6, 6, "#ffe27a");
      }
      for (let i = 0; i < Math.floor(w.w / 9); i++) {  // nhà phía xa
        const bw = 7 + ((i * 5 + wi * 3) % 5), bh = 8 + ((i * 7 + wi * 11) % 14), bx = w.u + i * 9;
        R(bx, w.v + w.h - bh, bw, bh, city[0]);
        for (let yy = w.v + w.h + 2 - bh; yy < w.v + w.h - 2; yy += 4) if ((yy + i) % 3) R(bx + 2, yy, 1, 1, i % 2 ? city[2] : city[1]);
      }
      if (S.officeRain) {
        g.fillStyle = "rgba(200,220,255,.55)";
        for (let i = 0; i < 10; i++) { const rx = w.u + ((i * 17 + Math.floor(t * 60) * 3) % w.w), ry = w.v + ((i * 29 + Math.floor(t * 120)) % (w.h - 2)); g.fillRect(rx, ry, 1, 3); }
      }
      g.restore();
      R(w.u + w.w / 2 - 1, w.v, 2, w.h, P.frame); R(w.u, w.v + w.h / 2 - 1, w.w, 2, P.frame);  // song cửa chữ thập
    }));
  }
  function drawAmbient(t, P) {  // vài chi tiết động trên nền tĩnh: dấu ":" đồng hồ (tường phải), đèn máy cà phê, hơi nước, màn hình máy game
    if (new Date().getSeconds() % 2) withWall("R", () => { R(125, 17, 2, 2, P.clock); R(125, 21, 2, 2, P.clock); });
    for (const f of FURN) {
      if (f.key === "coffee") {
        const [lx, ly] = qz(0.15, 0.8, 22), [sx2, sy2] = qz(0.42, 0.8, 16);
        R(f.sx + lx, f.sy + ly, 2, 2, Math.sin(t * 3) > 0 ? "#ff4d4d" : "#4dff88");
        if (Math.floor(t * 2) % 3 === 0) R(f.sx + sx2, f.sy + sy2 - 4, 1, 3, "rgba(255,255,255,.6)");
      } else if (f.key === "arcade") {
        for (let i = 0; i < 3; i++) {
          const [lx, ly] = qz(0.22 + i * 0.22, 0.9, 27 + ((Math.floor(t * 4) + i) % 3) * 3);
          R(f.sx + lx, f.sy + ly, 3, 3, ["#4dff88", "#ffd23f", "#4fd1c5"][i]);
        }
      }
    }
  }

  // ------------------------------------------------------------ sprite đồ đạc: vẽ sẵn 1 lần cho mỗi giao diện, mỗi khung hình chỉ dán
  function mk(w, h, ax, ay, fn) {  // (ax, ay) = vị trí điểm neo (gx0, gy0, độ cao 0) trong sprite; fn vẽ bằng tọa độ cục bộ
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const main = g, mox = ox, moy = oy;
    g = c.getContext("2d"); g.translate(ax, ay); ox = 0; oy = 0;
    try { fn(); } finally { g = main; ox = mox; oy = moy; }
    return { c, ax, ay };
  }
  const MUGS = ["#e05d5d", "#5d8fe0", "#5dc08a", "#e0b85d"];
  // màn hình: khối mỏng đứng ở mép sau bàn, mặt kính hướng +gy (về phía ghế và người xem). Nội dung 26 x 15 px vẽ lên mặt
  // đó bằng phép nghiêng 2:1 (đi 1 px theo gx thì xuống 0,5 px), nên màn hình nằm cùng không gian với cái bàn.
  const MON = { x0: 0.13, x1: 1.89, y0: 0.12, y1: 0.28, z0: 14, z1: 33 };   // khung (ô / px độ cao, cục bộ trong bàn)
  const SCR = { gx: 0.2, z: 31 };                                            // góc trên-trái vùng hiển thị trên mặt kính
  const SCRQ = qz(SCR.gx, MON.y1, SCR.z);
  function buildSprite(name, P) {
    const dk = (c) => shade(c, -0.3);
    switch (name) {
      case "desk0": case "desk1": case "desk2": case "desk3": {
        const mug = MUGS[+name.slice(4)], kb = P.cyber ? "#05d9e8" : "#e8e8ec";
        return mk(76, 70, 26, 34, () => {
          flat(-0.1, -0.1, 2.2, 1.2, 0, P.shadow);
          box(1.7, 0.1, 1.9, 0.3, 0, 9, P.leg, P.leg, P.leg); box(0.1, 0.1, 0.3, 0.3, 0, 9, P.leg, P.leg, P.leg);
          box(1.7, 0.7, 1.9, 0.9, 0, 9, P.leg, P.leg, P.leg); box(0.1, 0.7, 0.3, 0.9, 0, 9, P.leg, P.leg, P.leg);
          box(0, 0, 2, 1, 9, 11, P.deskTop, P.desk, P.deskSide);
          // viền sáng mép trước: đường chéo theo mép bàn (không phải vạch ngang)
          g.strokeStyle = P.deskEdge; g.lineWidth = 1; g.beginPath(); { const a = pt(0, 1, 11), b = pt(2, 1, 11); g.moveTo(a[0], a[1] + 0.5); g.lineTo(b[0], b[1] + 0.5); } g.stroke();
          flat(0.75, 0.08, 1.25, 0.32, 11.2, shade(P.monEdge, -0.2));                                                // đế màn hình
          box(0.94, 0.14, 1.06, 0.22, 11, 15, P.monEdge, P.monEdge, dk(P.monEdge));                                  // cổ màn hình
          box(MON.x0, MON.y0, MON.x1, MON.y1, MON.z0, MON.z1, shade(P.monEdge, 0.15), P.monEdge, dk(P.monEdge));      // khung màn hình
          box(0.55, 0.5, 1.45, 0.78, 11, 11.8, kb, shade(kb, -0.15), dk(kb));                                         // bàn phím trước màn hình
          box(1.62, 0.55, 1.8, 0.73, 11, 16, mug, mug, dk(mug));                                                      // cốc
        });
      }
      case "chair":  // ghế xoay: bóng, chân, mặt ghế (lưng ghế là sprite riêng, vẽ sau robot)
        return mk(40, 40, 20, 24, () => {
          flat(-0.05, -0.05, 0.8, 0.8, 0, P.shadow);
          box(0.3, 0.3, 0.4, 0.4, 0, SEAT_Z - 1, P.outline, P.outline, P.outline);
          box(0, 0, 0.7, 0.7, SEAT_Z - 2, SEAT_Z, P.chairHi, P.chair, P.chairSide);
        });
      case "chairBack":  // lưng ghế ở phía +gy (sau lưng robot, gần người xem): che phần dưới lưng robot đang ngồi
        return mk(40, 48, 20, 32, () => {
          box(0.08, 0.6, 0.62, 0.7, SEAT_Z, SEAT_Z + 6, P.chairHi, P.chair, P.chairSide);  // thấp: vẫn thấy vai + đầu robot
        });
      case "sofa":
        return mk(80, 64, 24, 24, () => {
          flat(-0.1, -0.1, 3.2, 1.2, 0, P.shadow);
          box(0, 0, 3, 1, 0, 5, P.sofa2, P.sofa, P.sofaSide);
          box(0, 0, 3, 0.3, 5, 15, P.sofa2, P.sofa, P.sofaSide);
          box(0, 0.3, 0.3, 1, 5, 10, P.sofa2, P.sofa, P.sofaSide); box(2.7, 0.3, 3, 1, 5, 10, P.sofa2, P.sofa, P.sofaSide);
          box(0.3, 0.3, 1.5, 1, 5, 7.5, P.sofa2, P.sofa, P.sofaSide); box(1.5, 0.3, 2.7, 1, 5, 7.5, P.sofa2, P.sofa, P.sofaSide);
        });
      case "coffee": {
        const body = P.cyber ? "#2b2050" : "#d9dde6";
        return mk(40, 46, 20, 30, () => {
          flat(-0.1, -0.1, 0.9, 0.9, 0, P.shadow);
          box(0, 0, 0.8, 0.8, 0, 26, shade(body, 0.15), body, dk(body));
          faceL(0.2, 0.6, 14, 20, 0.8, "#222"); faceL(0.35, 0.5, 8, 12, 0.8, "#fff");
        });
      }
      case "water": {
        const body = P.cyber ? "#33246a" : "#e6e9ef";
        return mk(40, 48, 20, 32, () => {
          flat(-0.1, -0.1, 0.8, 0.8, 0, P.shadow);
          box(0, 0, 0.7, 0.7, 0, 14, shade(body, 0.15), body, dk(body));
          box(0.1, 0.1, 0.6, 0.6, 14, 28, "#c7e8fb", "#9fd3f5", "#7fb8de");
        });
      }
      case "plant":
        return mk(48, 64, 24, 40, () => {
          flat(-0.1, -0.1, 0.9, 0.9, 0, P.shadow);
          box(0.1, 0.1, 0.7, 0.7, 0, 9, shade(P.pot, 0.2), P.pot, dk(P.pot));
          const [cx, cy] = pt(0.4, 0.4, 9), blob = (x, y, rx, ry, c) => { g.fillStyle = c; g.beginPath(); g.ellipse(x, y, rx, ry, 0, 0, 7); g.fill(); };
          blob(cx, cy - 11, 12, 9, dk(P.plant)); blob(cx - 3, cy - 17, 8, 7, P.plant); blob(cx + 4, cy - 21, 6, 6, shade(P.plant, 0.2));
        });
      case "arcade": {
        const body = P.cyber ? "#ff2a6d" : "#5a3fa0";
        return mk(50, 66, 22, 50, () => {
          flat(-0.1, -0.1, 1.1, 1, 0, P.shadow);
          box(0, 0, 1, 0.9, 0, 44, shade(body, 0.2), body, dk(body));
          faceL(0.12, 0.88, 24, 38, 0.9, "#08080f"); faceL(0.12, 0.88, 14, 19, 0.9, shade(body, 0.25));
          for (const [x, c] of [[0.3, "#ffd23f"], [0.5, "#ff5d73"], [0.7, "#4fd1c5"]]) { const p = pt(x, 0.9, 16); R(p[0], p[1], 2, 2, c); }
        });
      }
    }
    return null;
  }
  function spr(name, P) { return sprites[name] || (sprites[name] = buildSprite(name, P)); }
  function blit(name, P, x, y) { const s = spr(name, P); g.drawImage(s.c, Math.round(x) - s.ax, Math.round(y) - s.ay); }

  function drawDesk(i, P, t) {
    const { col, row } = cellOf(i), a = iso(deskGx(col), deskGy(row)), x = Math.round(a.x), y = Math.round(a.y);
    blit("desk" + (i % 4), P, x, y);
    const b = bots.get(S.profiles[i]?.name);
    g.save(); g.transform(1, 0.5, 0, 1, x + SCRQ[0], y + SCRQ[1]);  // nội dung nằm trên mặt kính nghiêng 2:1
    drawScreen(b && b.act ? b.act.screen : "off", 0, 0, t + i, P, b);
    g.restore();
  }
  function drawChair(i, P, part) { const s = seat(i), a = iso(s.gx - 0.35, s.gy - 0.35); blit(part, P, a.x, a.y); }
  function deskCenter(i) {  // giữa mặt kính màn hình (tọa độ thế giới)
    const { col, row } = cellOf(i), a = iso(deskGx(col), deskGy(row)), c = qz(SCR.gx + 13 / TW * 2, MON.y1, SCR.z - 7);
    return { x: Math.round(a.x) + c[0], y: Math.round(a.y) + c[1] };
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
      case "error": fill("#2456c8"); pix(":(", x + 4, y + 5, "#fff", 1, "left"); R(x + 13, y + 5, 9, 1, "#c8d6ff"); R(x + 13, y + 8, 7, 1, "#c8d6ff"); break;
      case "done": fill("#103a2a"); R(x + 8, y + 8, 3, 2, "#4dff88"); R(x + 10, y + 9, 3, 2, "#4dff88"); R(x + 12, y + 5, 2, 4, "#4dff88"); R(x + 14, y + 3, 2, 3, "#4dff88"); break;
      default: {  // tắt: màn hình chờ chấm nhảy
        fill(P.mon);
        if (b && b.act && b.act.at === "lounge") { const px = Math.abs(((t * 6) % 44) - 22), py = Math.abs(((t * 4) % 26) - 13); R(x + 1 + px, y + 1 + py, 2, 1, P.cyber ? "#ff2a6d" : "#3b4258"); }
      }
    }
    if (P.cyber && kind !== "off") { g.fillStyle = "rgba(0,0,0,.18)"; for (let yy = y; yy < y + h; yy += 2) g.fillRect(x, yy, w, 1); }
  }

  function drawFurn(f, P) { blit(f.key, P, f.sx, f.sy); }

  // robot là 2 khối hộp isometric (thân + đầu), vẽ quanh điểm chân (b.sx, b.sy). b.fa = hướng mặt: "+gy" (xuống-trái),
  // "+gx" (xuống-phải) thì thấy mặt; "-gy" (lên-phải, ví dụ ngồi nhìn màn hình) và "-gx" thì thấy lưng, chỉ ló mép kính mặt.
  const BH = 0.2, HH2 = 0.28;                          // nửa cạnh thân / đầu (ô)
  function boxO(x0, y0, x1, y1, z0, z1, top, left, right, O) {  // hộp + viền ngoài
    box(x0, y0, x1, y1, z0, z1, top, left, right);
    g.strokeStyle = O; g.lineWidth = 1; g.beginPath();
    [pt(x0, y0, z1), pt(x1, y0, z1), pt(x1, y0, z0), pt(x1, y1, z0), pt(x0, y1, z0), pt(x0, y1, z1)]
      .forEach((p, i) => (i ? g.lineTo(p[0] + 0.5, p[1] + 0.5) : g.moveTo(p[0] + 0.5, p[1] + 0.5)));
    g.closePath(); g.stroke();
  }
  function onFace(side, h, ztop, fn) {  // vẽ bằng tọa độ phẳng (u sang phải, v xuống) trên mặt +gy ("L") hoặc +gx ("R") của hộp nửa cạnh h
    const p = side === "L" ? pt(-h, h, ztop) : pt(h, h, ztop);
    g.save(); g.transform(1, side === "L" ? 0.5 : -0.5, 0, 1, p[0], p[1]); fn(Math.round(2 * h * HW)); g.restore();
  }
  function drawBot(b, t, P, beat, now) {
    const moving = b.path.length > 0, sit = !moving && b.pose === "sit";
    const cele = b.celebrate > now;
    let bob = 0;
    if (cele) bob = -Math.abs(Math.sin(t * 9)) * 6;
    else if (moving) bob = Math.floor(t * 8) % 2 ? -1 : 0;
    else if (beat !== null && b.act && b.act.at !== "desk") bob = Math.sin(beat * Math.PI) ** 2 > 0.6 ? -1 : 0;  // nhún theo nhạc
    const O = P.outline, fa = b.fa || "+gy", alongGy = fa[2] === "y", act = b.act || {};
    if (!sit) { R(b.sx - 6, b.sy - 2, 12, 3, P.shadow); R(b.sx - 4, b.sy - 3, 8, 1, P.shadow); R(b.sx - 4, b.sy + 1, 8, 1, P.shadow); }  // bóng trên sàn
    const mox = ox, moy = oy;
    ox = b.sx; oy = Math.round(b.sy - b.lift + bob);
    try {
      const bz = sit ? 1 : 5, hz = bz + 11, top = hz + 11;  // đáy thân, đáy đầu, đỉnh đầu (px độ cao)
      // tay / chân nằm ở 2 bên vuông góc với hướng mặt; vẽ bên xa (độ sâu nhỏ) trước thân, bên gần sau thân
      const side = (k, w) => (alongGy ? [k - w, -0.06, k + w, 0.06] : [-0.06, k - w, 0.06, k + w]);
      const legs = [-0.1, 0.1], sw = moving ? (Math.floor(t * 8) % 2 ? 1 : -1) : 0;
      if (!sit) legs.forEach((k, i) => { const [a0, b0, a1, b1] = side(k, 0.06), up = Math.max(0, i ? sw : -sw); box(a0, b0, a1, b1, up, bz, O, O, O); });
      const typing = sit && act.typing && !cele, tp = Math.floor(t * (act.slow ? 3 : 10)) % 2;
      const atDesk = sit && act.at === "desk" && fa === "-gy", task = loungeTask(b);
      const reach = !cele && (atDesk || task === "game" || task === "water" || task === "diary" || task === "pet");
      const busyHands = typing || task === "game" || task === "diary", hp = Math.floor(t * (task === "diary" ? 4 : task === "game" ? 8 : act.slow ? 3 : 10)) % 2;
      const sgn = fa[0] === "-" ? -1 : 1;
      const arm = (k, i) => {
        const [a0, b0, a1, b1] = side(k, 0.05);
        if (reach) {  // tay vươn về phía trước (bàn phím, máy game, bình tưới, cuốn sổ, con mèo); bận tay thì nhấp lên xuống
          const z0 = bz + 4 + (busyHands ? (i ? hp : 1 - hp) : 0), f0 = sgn * 0.02, f1 = sgn * (BH + 0.24);
          if (alongGy) boxO(a0, Math.min(f0, f1), a1, Math.max(f0, f1), z0, z0 + 3, b.light, b.color, b.dark, O);
          else boxO(Math.min(f0, f1), b0, Math.max(f0, f1), b1, z0, z0 + 3, b.light, b.color, b.dark, O);
          return;
        }
        const wave = task === "dance" ? (Math.floor((beat !== null ? beat : t * 1.5)) + i) % 2 === 0 : task === "stretch" && Math.floor(t / 2) % 2 === 0;
        const up = cele || wave;
        const z0 = up ? bz + 9 : bz + 2 + (typing ? (i ? tp : 1 - tp) : 0), z1 = up ? bz + 16 : z0 + 6;
        boxO(a0, b0, a1, b1, z0, z1, b.light, b.color, b.dark, O);
      };
      arm(-(BH + 0.05), 0);
      boxO(-BH, -BH, BH, BH, bz, bz + 10, b.light, b.color, b.dark, O);
      const working = act.at === "desk" && act.screen !== "error";
      const chest = working ? (Math.floor(t * 4) % 2 ? "#4dff88" : "#1f8f4e") : act.screen === "error" ? "#ff4d4d" : b.dark;
      if (fa === "+gy" || fa === "+gx") onFace(fa === "+gy" ? "L" : "R", BH, bz + 10, (w) => R(Math.floor(w / 2) - 1, 4, 3, 3, chest));
      else onFace("L", BH, bz + 10, (w) => { R(2, 3, w - 4, 1, b.dark); R(2, 5, w - 4, 1, b.dark); });  // lưng: khe tản nhiệt
      arm(BH + 0.05, 1);
      // đầu + kính mặt
      boxO(-HH2, -HH2, HH2, HH2, hz, top, b.light, b.color, b.dark, O);
      const face = cele || task === "pet" || task === "dance" ? "happy" : sleeping(b) ? "sleep" : task === "diary" ? "focus" : task === "game" ? "wow" : act.face || "idle";
      const eye = face === "sad" ? "#ff5d5d" : face === "happy" ? "#ffd23f" : "#6ff0ff";
      if (fa === "+gy" || fa === "+gx") {
        onFace(fa === "+gy" ? "L" : "R", HH2, top, (w) => { R(0, 2, w, 6, "#10131c"); drawFace(b, Math.round(w / 2), 2, now, face); });
      } else if (fa === "-gy") {  // nhìn lên-phải: kính mặt ló ở đầu phải của mặt +gx
        onFace("R", HH2, top, (w) => { R(w - 3, 2, 3, 6, "#10131c"); R(w - 2, 4, 1, 2, eye); });
      } else {                    // nhìn lên-trái: ló ở đầu trái của mặt +gy
        onFace("L", HH2, top, () => { R(0, 2, 3, 6, "#10131c"); R(1, 4, 1, 2, eye); });
      }
      // đồ cầm tay
      if (act.prop === "phone" && !moving) { const p = pt(BH + 0.12, -0.05, hz + 6); R(p[0], p[1], 4, 7, "#2a2e38"); R(p[0] + 1, p[1] + 1, 2, 4, Math.floor(t * 3) % 2 ? "#5fc9e8" : "#9fe6ff"); }
      if (task === "diary") {  // cuốn sổ mở trên đùi + bút chì chạy theo dòng
        box(-0.16, BH + 0.06, 0.16, BH + 0.3, bz + 5, bz + 6, "#fbfaf4", "#e6e2d4", "#cfc9b6");
        const s0 = pt(-0.12, BH + 0.26, bz + 6), px = Math.floor(t * 3) % 6;
        R(s0[0] + 1, s0[1] - 3, 5, 1, "#9aa3b5"); R(s0[0] + 1, s0[1] - 1, px, 1, "#606878");
        R(s0[0] + 1 + px, s0[1] - 4, 1, 3, "#e0b85d");
      }
      if (task === "water") {  // bình tưới ở tay phải, vòi chĩa về chậu cây
        const p = pt(BH + 0.05, -BH - 0.3, bz + 4); R(p[0] - 1, p[1] - 4, 5, 4, "#7fa7c9"); R(p[0] - 1, p[1] - 5, 5, 1, "#a9c7e0"); R(p[0] + 4, p[1] - 6, 3, 1, "#7fa7c9");
      }
      if (task === "coffee" || task === "drink") {  // cốc cà phê (bốc hơi) / cốc nước
        const p = pt(BH + 0.1, 0.12, bz + 7), c = task === "coffee" ? "#f4f4f4" : "#cfe9ff";
        R(p[0], p[1], 4, 4, c); if (task === "coffee") { R(p[0] + 4, p[1] + 1, 1, 2, c); if (Math.floor(t * 2) % 2) R(p[0] + 1, p[1] - 3, 1, 2, "rgba(255,255,255,.6)"); }
      }
      if (act.prop === "mug" && !moving && !task) { const p = pt(BH + 0.1, 0.12, bz + 7); R(p[0], p[1], 4, 4, "#f4f4f4"); R(p[0] + 4, p[1] + 1, 1, 2, "#f4f4f4"); if (Math.floor(t * 2) % 2) R(p[0] + 1, p[1] - 3, 1, 2, "rgba(255,255,255,.6)"); }
      // ăng-ten
      const a = pt(0, 0, top), ant = working ? (Math.floor(t * 3) % 2 ? "#4dff88" : "#ffd23f") : act.screen === "error" ? (Math.floor(t * 4) % 2 ? "#ff4d4d" : "#7a1d1d") : b.light;
      R(a[0], a[1] - 3, 1, 3, O); R(a[0] - 1, a[1] - 5, 3, 2, ant);
    } finally { ox = mox; oy = moy; }
  }
  function isWorking(b) { return !!(b.act && b.act.at === "desk" && b.act.screen !== "error" && b.act.screen !== "lock"); }
  let nightCache = { at: 0, night: false };
  function isNight() {  // đọc giờ tối đa 1 lần/giây
    const now = Date.now();
    if (now - nightCache.at > 1000) { const h = new Date().getHours(); nightCache = { at: now, night: h >= 23 || h < 6 }; }
    return nightCache.night;
  }
  function sleeping(b) {
    return !!(b.act && b.act.at === "lounge" && b.spot && b.spot.what === "sofa" && !b.path.length && (isNight() || loungeTask(b) === "rest"));
  }
  function drawFace(b, x, y, now, face) {
    if (now > b.blink) b.blink = now + 2500 + Math.random() * 3000;
    const blink = b.blink - now < 180;  // đủ dài để không lọt giữa 2 khung hình khi chạy 6 khung/giây
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

  function drawFx(dt) {
    for (let i = fx.length - 1; i >= 0; i--) {
      const p = fx[i];
      p.age += dt;
      if (p.age > p.life) { fx.splice(i, 1); continue; }
      p.x += p.vx * dt; p.y += p.vy * dt;
      g.globalAlpha = Math.max(0, 1 - p.age / p.life);
      if (p.kind === "confetti") { p.vy += 90 * dt; R(p.x, p.y, 2, 2, p.c); }
      else if (p.kind === "smoke") R(p.x, p.y, 3 + p.age * 3, 3 + p.age * 3, "rgba(120,120,130,.55)");
      else if (p.kind === "note") pix("♪", p.x + Math.sin(p.age * 4) * 2, p.y, p.c);
      else if (p.kind === "zzz") pix("z", p.x + Math.sin(p.age * 3) * 2, p.y, "#a9b4d6");
      else if (p.kind === "drop") R(p.x, p.y, 1, 2, "#6fc3ff");
      else if (p.kind === "heart") pix("♥", p.x + Math.sin(p.age * 4), p.y, "#ff6b8b");
      else if (p.kind === "text") { pix(p.text, p.x + 1, p.y + 1, "rgba(0,0,0,.5)"); pix(p.text, p.x, p.y, "#ffd23f"); }
      g.globalAlpha = 1;
    }
    for (const b of bots.values()) {  // hiệu ứng liên tục theo trạng thái
      if (!b.act || b.path.length) continue;
      const top = b.sy - b.lift;
      if (b.act.fx === "smoke" && Math.random() < dt * 3) fx.push({ kind: "smoke", x: b.sx - 2 + Math.random() * 4, y: top - 34, vx: (Math.random() - 0.5) * 6, vy: -12, life: 1.6, age: 0 });
      if (sleeping(b) && Math.random() < dt * 0.8) fx.push({ kind: "zzz", x: b.sx + 6, y: top - 30, vx: 4, vy: -8, life: 2.2, age: 0 });
      const task = loungeTask(b);
      if (task === "water" && Math.random() < dt * 6) {  // giọt nước rơi từ vòi bình tưới xuống chậu
        const p = iso(b.gx + BH + 0.05, b.gy - BH - 0.3, 15);
        fx.push({ kind: "drop", x: p.x + 6 + Math.random() * 2, y: p.y, vx: 6, vy: 18, life: 0.7, age: 0 });
      }
      if (task === "pet" && Math.random() < dt * 0.9) fx.push({ kind: "heart", x: cat.sx - 2, y: cat.sy - 12, vx: (Math.random() - 0.5) * 6, vy: -10, life: 1.6, age: 0 });
      if (Lofi.on && b.act.at === "lounge" && !sleeping(b) && Math.random() < dt * 0.35)
        fx.push({ kind: "note", x: b.sx + 5, y: top - 30, vx: 3, vy: -9, life: 2.4, age: 0, c: ["#ffd23f", "#ff8fb1", "#7fe3ff"][Math.floor(Math.random() * 3)] });
    }
    if (cat.st === "sleep" && !cat.path.length && Math.random() < dt * 0.4) fx.push({ kind: "zzz", x: cat.sx + 4, y: cat.sy - 12, vx: 3, vy: -6, life: 2, age: 0 });
    if (fx.length > 300) fx.splice(0, fx.length - 300);
  }

  function step(dt, now) {
    for (const b of bots.values()) {
      if (b.path.length) {
        const p = b.path[0], dx = p.gx - b.gx, dy = p.gy - b.gy, d = Math.hypot(dx, dy), mv = SPEED * dt;
        if (Math.abs(dx) > 1e-6 || Math.abs(dy) > 1e-6) b.fa = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "+gx" : "-gx") : (dy > 0 ? "+gy" : "-gy");  // nhìn theo hướng đi
        if (d <= mv) {
          b.gx = p.gx; b.gy = p.gy; b.path.shift();
          if (!b.path.length) { b.pose = b.where.pose; b.fa = restFace(b.where); }
        } else { b.gx += (dx / d) * mv; b.gy += (dy / d) * mv; }
      } else if (b.act && b.act.at === "lounge") {
        if (b.celebrate && b.celebrate < now && b.where && b.where.kind === "desk") { b.celebrate = 0; walk(b, pickSpot(b)); }
        else if (b.where && b.where.kind === "lounge" && now > b.until && !sleeping(b)) walk(b, pickSpot(b));  // đổi chỗ chơi
      }
      if (b.where && b.where.what === "rug" && !b.path.length && catNear(b)) b.fa = b.gx < cat.gx ? "+gx" : "-gx";  // quay sang vuốt mèo
      locate(b);
    }
    catStep(dt, now);
  }

  // ------------------------------------------------------------ lớp HTML: chỉ chạm DOM khi có gì thật sự đổi
  function drawLayer(now) {
    placeCard();
    for (const b of bots.values()) {
      const bt = b.name === cardName ? null : bubbleText(b, now), c = b.bub, el = b.bubEl;  // đang mở thẻ thì ẩn bong bóng (thẻ che chỗ đó)
      const text = bt ? bt[0] : null;
      if (text !== c.text) {
        el.hidden = text === null;
        if (text !== null) el.textContent = text;
        c.text = text;
      }
      if (text === null) continue;
      if (bt[1] !== c.cls) { el.className = "ob-bubble" + (bt[1] ? " " + bt[1] : ""); c.cls = bt[1]; }
      const bx = b.sx, by = Math.round(b.sy - b.lift - (b.pose === "sit" && !b.path.length ? 28 : 32));
      if (bx !== c.x || by !== c.y) {
        el.style.left = (bx / W * 100) + "%"; el.style.top = (by / H * 100) + "%";
        c.x = bx; c.y = by;
      }
    }
  }

  // ------------------------------------------------------------ vòng vẽ
  function busy(now) {  // có gì đang chuyển động thì chạy nhanh, không thì chỉ vài khung/giây cho nháy mắt, mây trôi
    if (Lofi.on || S.officeRain || fx.length || cat.path.length || cat.st === "eat" || cat.st === "groom") return true;
    for (const b of bots.values()) {
      if (b.path.length || b.celebrate > now || isWorking(b) || (b.act && b.act.fx)) return true;
    }
    return false;
  }
  const order = [];
  function frame(ts) {
    raf = 0;
    if (!visible) return;
    const dt = Math.min(0.25, (ts - (lastT || ts)) / 1000);
    lastT = ts;
    const t = ts / 1000, now = performance.now(), key = themeKey(), P = PALETTES[key], beat = Lofi.beat();
    if (key !== sprKey) { sprites = {}; sprKey = key; }  // đổi giao diện: vẽ lại sprite
    step(dt, now);
    ensureStatic(P, key);
    g.clearRect(0, 0, W, H);
    g.drawImage(bg, 0, 0);
    drawWindows(t, P);
    drawAmbient(t, P);
    // vẽ theo độ sâu gx + gy: vật xa người xem (nhỏ) vẽ trước, vật gần che lên; cùng độ sâu thì đồ đạc trước robot
    order.length = 0;
    S.profiles.forEach((_, i) => {
      const s = seat(i), c = cellOf(i);
      order.push({ d: deskGx(c.col) + 1 + deskGy(c.row) + 0.5, k: 0, desk: i }, { d: s.gx + s.gy - 0.05, k: 1, chair: i, part: "chair" },
        { d: s.gx + s.gy + 0.3, k: 4, chair: i, part: "chairBack" });
    });
    for (const f of FURN) order.push({ d: f.d, k: 0, f });
    for (const b of bots.values()) order.push({ d: b.depth, k: 3, b });
    const bw = bowlAt();
    order.push({ d: bw.gx + bw.gy, k: 0, bowl: true }, { d: cat.gx + cat.gy, k: 2, cat: true });
    order.sort((a, c) => a.d - c.d || a.k - c.k);
    for (const it of order) {
      if (it.b) drawBot(it.b, t, P, beat, now);
      else if (it.cat) drawCat(t, P);
      else if (it.bowl) drawBowl(P);
      else if (it.f) drawFurn(it.f, P);
      else if (it.chair !== undefined) drawChair(it.chair, P, it.part);
      else drawDesk(it.desk, P, t);
    }
    for (const b of bots.values()) {
      if (b.act && b.act.fx === "flash" && !b.path.length && Math.floor(t * 1.5) % 4 === 0) {  // Visual Search: chớp sáng quanh màn hình
        const c = deskCenter(b.index);
        const grad = g.createRadialGradient(c.x, c.y, 2, c.x, c.y, 40);
        grad.addColorStop(0, "rgba(255,255,255,.55)"); grad.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = grad; g.fillRect(c.x - 40, c.y - 40, 80, 80);
      }
    }
    drawFx(dt);
    drawLayer(now);
    const delay = busy(now) ? Math.max(0, 1000 / FPS - (performance.now() - ts)) : 1000 / IDLE_FPS;
    tmo = setTimeout(() => { tmo = 0; if (visible && !raf) raf = requestAnimationFrame(frame); }, delay);
  }
  function wake() {  // trạng thái vừa đổi: vẽ ngay, không chờ hết nhịp nghỉ
    if (tmo) { clearTimeout(tmo); tmo = 0; }
    if (visible && !raf) raf = requestAnimationFrame(frame);
  }

  function resize() {
    if (!stage) return;
    const dpr = window.devicePixelRatio || 1, cssW = Math.max(200, stage.clientWidth);
    let k = Math.max(1, Math.floor((cssW * dpr) / W));  // phóng to theo số nguyên lần pixel thiết bị -> pixel đều, sắc nét
    if (cssW * dpr / W < 1.5) k = (cssW * dpr) / W;    // màn hình hẹp: chấp nhận co lẻ (luôn vừa chiều ngang, không bị cắt)
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; bgKey = ""; }  // canvas chỉ to bằng thế giới
    const px = k / dpr;
    inner.style.width = W * px + "px"; inner.style.height = H * px + "px";
    inner.style.setProperty("--px", px + "px");  // chữ trên tường (HTML) co giãn theo cùng tỉ lệ
    // chữ trên tường: điểm (u, v) trên tường phải ứng với (OX + u, OY - WALLH + v + u / 2); skewY(26.565deg) ở CSS khớp độ nghiêng 2:1
    const at = (el, u, v, w, h) => Object.assign(el.style, { left: (OX + u) / W * 100 + "%", top: (OY - WALLH + v + u / 2) / H * 100 + "%",
      width: w / W * 100 + "%", height: h / H * 100 + "%" });
    at(wall.sign, 14, 12, 72, 22); at(wall.sub, 12, 38, 76, 10);
    at(wall.today, 162, 11, 68, 11); at(wall.working, 162, 40, 68, 11);
    if (visible) wake();
  }
  // nhật ký của robot (khi ngồi sofa viết nhật ký): tóm tắt ngày hôm nay từ dữ liệu thật của tài khoản đó
  function diaryLines(name) {
    const s = st(name), x = s.stats || {}, out = [];
    if (typeof s.today === "number") out.push(`Nhật ký: hôm nay +${fmt(s.today)} điểm`);
    if (x.pc_max) out.push(`Search PC ${x.pc}/${x.pc_max} · Mobile ${x.mobile || 0}/${x.mobile_max || 0}`);  // giống nhau ở 2 ngôn ngữ
    const streak = (s.streak && s.streak.daily_streak) || x.daily_streak;
    if (streak) out.push(`Chuỗi ${streak} ngày liên tiếp`);
    const tasks = s.tasks || [];
    if (tasks.length) out.push(`Đã xong ${tasks.filter((k) => k.done).length}/${tasks.length} việc hôm nay`);
    const goal = (S.goals || {})[name];
    if (goal && goal.points && typeof s.points === "number") {
      const left = goal.points - s.points;
      out.push(left > 0 ? `Còn ${fmt(left)} điểm nữa là tới mục tiêu` : "Đủ điểm đổi quà rồi!");
    }
    return out.length ? out : ["Hôm nay chưa có gì để ghi"];
  }
  function bubbleText(b, now) {
    if (b.logUntil > now && b.act && b.act.at === "desk") return [b.log, "log"];
    if (b.celebrate > now) return [tr("Xong việc rồi!"), ""];
    if (loungeTask(b) === "diary") {  // mỗi lượt 4,5 giây; 2 chỗ trên sofa thay phiên nhau "đọc" để bong bóng không đè nhau
      const slot = Math.floor(now / 4500), seat = b.where.gx > 2 ? 1 : 0;
      if ((slot + seat) % 2) return null;
      const lines = diaryLines(b.name);
      return [tr(lines[Math.floor(slot / 2) % lines.length]), "log"];
    }
    const a = b.act;
    if (!a || !a.say) return null;  // đang đi tới bàn cũng nói luôn việc sắp làm
    return [tr(a.say), a.screen === "error" ? "err" : ""];
  }

  // ------------------------------------------------------------ thẻ thông tin khi bấm robot (HTML, nổi trên đầu robot)
  let cardEl = null, cardName = null, cardHtml = "";
  const cardPos = { x: -1, y: -1 };
  const CARD_DONE_MAX = 8;  // việc đã xong chỉ liệt kê vài dòng đầu, còn lại gộp "+n việc khác"
  function toggleCard(name) { if (cardName === name) closeCard(); else openCard(name); }
  function openCard(name) {
    cardName = name; cardHtml = ""; cardPos.x = -1;
    cardEl.hidden = false;
    renderCard();
    cardEl.classList.remove("pop"); void cardEl.offsetWidth; cardEl.classList.add("pop");
    for (const b of bots.values()) b.tagEl.classList.toggle("active", b.name === name);
    wake();
  }
  function closeCard() {
    if (!cardName) return;
    cardName = null; cardEl.hidden = true;
    for (const b of bots.values()) b.tagEl.classList.remove("active");
    wake();
  }
  function taskRow(t) {
    const unit = t.unit || "điểm", ic = t.done ? "ti-circle-check" : t.progress > 0 ? "ti-circle-half-2" : "ti-circle";
    return `<li class="${t.done ? "done" : ""}" title="${esc(t.title)}${t.bot ? " · " + esc(t.bot) : ""}"><i class="ti ${ic}"></i>`
      + `<span class="oc-t">${esc(t.title)}</span><span class="oc-n">${fmt(t.progress)}/${fmt(t.max)} <small>${esc(unit)}</small></span></li>`;
  }
  function renderCard() {
    if (!cardName || !cardEl) return;
    const name = cardName, prof = S.profiles.find((p) => p.name === name);
    if (!prof) { closeCard(); return; }
    const s = st(name), tasks = s.tasks || [], email = savedEmail(name), running = S.running.has(name);
    const todo = tasks.filter((t) => !t.done), done = tasks.filter((t) => t.done);
    const linked = email ? `<span data-no-i18n>${esc(email)}</span>` : `<span class="oc-muted">Chưa lưu email đăng nhập</span>`;
    const extra = [prof.mode === "cdp" ? `CDP :${esc(prof.cdp_port)}` : "",
      prof.proxy ? `Proxy <span data-no-i18n>${esc(prof.proxy)}</span>` : ""].filter(Boolean);
    let body;
    if (!tasks.length) body = `<p class="oc-empty">Chưa có dữ liệu task. Bấm <b>Làm mới</b> để đọc task hôm nay từ Rewards.</p>`;
    else {
      body = `<div class="oc-sec"><span>Chưa làm</span><b>${todo.length}</b></div>`
        + (todo.length ? `<ul class="oc-list">${todo.map(taskRow).join("")}</ul>`
          : `<p class="oc-empty ok"><i class="ti ti-confetti"></i>Đã làm hết việc hôm nay</p>`)
        + `<div class="oc-sec"><span>Đã làm</span><b>${done.length}</b></div>`
        + (done.length ? `<ul class="oc-list">${done.slice(0, CARD_DONE_MAX).map(taskRow).join("")}`
          + (done.length > CARD_DONE_MAX ? `<li class="oc-more">+${done.length - CARD_DONE_MAX} việc khác</li>` : "") + `</ul>`
          : `<p class="oc-empty">Chưa làm việc nào</p>`);
    }
    const html = `<div class="oc-head">${avatarHtml(name, "avatar-sm rounded-circle")}
        <div class="oc-who"><b data-no-i18n>${esc(name)}</b><small><i class="ti ti-link"></i>${linked}</small>${extra.length ? `<small>${extra.join(" · ")}</small>` : ""}</div>
        <button type="button" class="oc-x" data-act="close" title="Đóng" aria-label="Đóng"><i class="ti ti-x"></i></button></div>
      <div class="oc-stats"><div><small>Điểm</small><b>${fmt(s.points)}</b></div><div><small>Hôm nay</small><b>${s.today != null ? "+" + fmt(s.today) : "—"}</b></div>
        <div><small>Trạng thái</small>${statePill(name)}</div></div>
      ${s.progress ? `<div class="oc-now"><i class="ti ti-player-play"></i><span>${esc(s.progress)}</span></div>` : ""}
      <div class="oc-body">${body}</div>
      <div class="oc-foot"><small>${s.updated ? "Cập nhật " + esc(s.updated) : ""}</small>
        ${running ? `<button type="button" class="btn btn-sm" data-act="stop"><i class="ti ti-player-stop"></i>Dừng</button>`
          : `<button type="button" class="btn btn-sm btn-primary" data-act="run"><i class="ti ti-player-play"></i>Chạy</button>`}
        <button type="button" class="btn btn-sm" data-act="open"><i class="ti ti-layout-dashboard"></i>Tổng quan</button></div>`;
    if (html === cardHtml) return;  // không đổi gì: khỏi đụng DOM (sự kiện trạng thái đến liên tục khi bot chạy)
    const scroll = cardEl.querySelector(".oc-body")?.scrollTop || 0;
    cardEl.innerHTML = html; cardHtml = html;
    const bd = cardEl.querySelector(".oc-body"); if (bd) bd.scrollTop = scroll;
    cardPos.x = -1;  // cỡ thẻ có thể đổi: đặt lại vị trí ở khung hình tới
  }
  function placeCard() {  // neo thẻ trên đầu robot (robot có thể đang đi), kẹp trong khung văn phòng; sát mép trên thì lật xuống dưới
    if (!cardName) return;
    const b = bots.get(cardName);
    if (!b) { closeCard(); return; }
    const x = b.sx, y = Math.round(b.sy - b.lift - (b.pose === "sit" && !b.path.length ? 28 : 32));
    if (x === cardPos.x && y === cardPos.y) return;
    cardPos.x = x; cardPos.y = y;
    const lw = layer.clientWidth, lh = layer.clientHeight, sc = lw / W, ax = x * sc, ay = y * sc, gap = 8;
    const by = (b.sy + 4) * sc + gap;  // mép trên của thẻ khi lật xuống dưới chân robot
    const up = ay - gap - 4, down = lh - by - 4;  // chỗ trống phía trên / dưới robot
    cardEl.style.maxHeight = "none";
    const full = cardEl.offsetHeight, below = full > up && down > up;  // trên không đủ chỗ mà dưới rộng hơn thì lật xuống
    cardEl.style.maxHeight = Math.max(120, below ? down : up) + "px";  // văn phòng thấp: thẻ co lại, danh sách việc tự cuộn
    const w = cardEl.offsetWidth, h = cardEl.offsetHeight;
    const left = Math.max(4, Math.min(lw - w - 4, ax - w / 2));
    const top = below ? Math.min(lh - h - 4, by) : ay - h - gap;
    cardEl.classList.toggle("below", below);
    cardEl.style.left = left + "px"; cardEl.style.top = Math.max(4, top) + "px";
    cardEl.style.setProperty("--ax", Math.max(14, Math.min(w - 14, ax - left)) + "px");  // mũi nhọn chỉ đúng robot
  }
  function bindCard() {
    layer.insertAdjacentHTML("beforeend", `<div class="ob-card" role="dialog" aria-label="Thông tin tài khoản" hidden></div>`);
    cardEl = $(".ob-card", layer);
    cardEl.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      const name = cardName, act = btn.dataset.act;
      if (act === "close") closeCard();
      else if (act === "open") { closeCard(); S.selected = name; go("dashboard"); }
      else if (act === "run") { btn.disabled = true; await start([name], "run"); renderCard(); }
      else if (act === "stop") { btn.disabled = true; await api().stop([name]); toast("Đang dừng " + name); }
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && cardName) closeCard(); });
    document.addEventListener("pointerdown", (e) => {  // bấm ra ngoài văn phòng: đóng thẻ
      if (cardName && !e.target.closest(".ob-card, .ob-tag, #office-canvas")) closeCard();
    }, true);
    window.addEventListener("resize", () => { cardPos.x = -1; });
  }

  let armResume = null, repaint = null;  // gán trong bindControls; Office.setFun dùng
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
      wake();
    };
    music.onclick = () => { Lofi.toggle(); pref.set("officeMusic", Lofi.on); paint(); };
    rain.onclick = () => { S.officeRain = !S.officeRain; Lofi.setRain(S.officeRain); pref.set("officeRain", S.officeRain); paint(); };
    volume.oninput = () => { const v = +volume.value / 100; Lofi.setVolume(v); pref.set("officeVolume", v); };
    cv.addEventListener("click", (e) => {  // bấm vào robot -> mở thẻ thông tin nhỏ trên đầu robot
      const r = cv.getBoundingClientRect(), wx = (e.clientX - r.left) / r.width * W, wy = (e.clientY - r.top) / r.height * H;
      let hit = null;  // robot gần người xem nhất (độ sâu lớn nhất) trong vùng bấm; robot luôn được ưu tiên hơn mèo
      for (const b of bots.values()) {
        if (Math.abs(b.sx - wx) < 9 && wy > b.sy - b.lift - 30 && wy < b.sy + 2 && (!hit || b.depth > hit.depth)) hit = b;
      }
      if (hit) { toggleCard(hit.name); return; }
      closeCard();  // bấm chỗ trống / con mèo: đóng thẻ đang mở
      if (Math.abs(cat.sx - wx) < 9 && wy > cat.sy - 20 && wy < cat.sy + 2) {  // bấm vào mèo: thả tim, mèo thức dậy ngồi một lúc
        for (let i = 0; i < 4; i++) fx.push({ kind: "heart", x: cat.sx - 3 + i * 2, y: cat.sy - 18, vx: (i - 1.5) * 6, vy: -14, life: 1.4, age: 0 });
        if (!cat.path.length && cat.st !== "eat") { cat.goal = "sit"; cat.st = "sit"; cat.until = performance.now() + 5000; }
        wake();
      }
    });
    paint();
    // lần trước để nhạc bật: bật lại ở lần bấm chuột đầu tiên (trình duyệt không cho tự phát tiếng khi chưa bấm gì)
    // chế độ vui tắt thì không tự bật (giữ nguyên pref, bật chế độ vui lại là tiếp tục chờ lần bấm đầu)
    let armed = false;
    const resume = (e) => {
      if (!S.settings.fun_mode) return;
      if (e.target.closest("#office-music")) return;  // bấm chính nút nhạc thì để nút tự xử lý
      document.removeEventListener("pointerdown", resume, true);
      armed = false;
      if (!Lofi.on) { Lofi.start(); paint(); }
    };
    armResume = () => {
      if (armed || Lofi.on || !pref.get("officeMusic", false)) return;
      armed = true;
      document.addEventListener("pointerdown", resume, true);
    };
    repaint = paint;
    armResume();
  }

  return {
    init() {
      cv = $("#office-canvas"); stage = $("#office-stage"); inner = $("#office-inner"); layer = $("#office-layer");
      if (!cv) return;
      g = cv.getContext("2d");  // nền trong suốt ngoài khối văn phòng: lộ màu nền của khung
      bg = document.createElement("canvas");
      layer.insertAdjacentHTML("afterbegin", `<div class="ow ow-right ow-sign">REWARDS HQ</div><div class="ow ow-right ow-sub">Văn phòng bot</div>`
        + `<div class="ow ow-right ow-today">Hôm nay</div><div class="ow ow-right ow-working"></div>`);
      wall = { sign: $(".ow-sign", layer), sub: $(".ow-sub", layer), today: $(".ow-today", layer), working: $(".ow-working", layer) };
      layer.insertAdjacentHTML("beforeend", `<button type="button" class="ob-add" title="Thêm tài khoản" aria-label="Thêm tài khoản"><i class="ti ti-plus"></i></button>`);
      addBtn = $(".ob-add", layer);
      addBtn.onclick = () => window.openProfileDialog(null);
      bindCard();
      bindControls();
      new ResizeObserver(() => resize()).observe(stage);
      document.addEventListener("visibilitychange", () => this.render());
    },
    render() {  // gọi mỗi lần trạng thái đổi hoặc đổi trang
      if (!cv) return;
      const show = S.page === "office" && !document.hidden;
      sync();
      if (show) renderCard(); else closeCard();
      $("#office-empty").hidden = S.profiles.length > 0;
      const run = [...bots.values()].filter(isWorking).length;
      const sub = `${run} robot đang làm việc · ${S.profiles.length - run} đang nghỉ`;
      if ($("#office-sub").textContent !== sub) $("#office-sub").textContent = sub;
      if (show && !visible) { visible = true; lastT = 0; resize(); }
      visible = show;
      if (!visible && tmo) { clearTimeout(tmo); tmo = 0; }
      if (visible) wake();
    },
    onLog,
    // app.js gọi khi bật / tắt chế độ vui: tắt thì dừng nhạc lofi (không xóa pref officeMusic), bật lại thì chờ lần bấm đầu để phát tiếp
    setFun(on) {
      if (!on) { if (Lofi.on) Lofi.stop(); } else if (armResume) armResume();
      if (repaint) repaint();
    },
    // chỉ để kiểm thử: khung (client) của màn hình từng bàn, kể cả khung viền
    _screens() {
      if (!cv) return [];
      const r = cv.getBoundingClientRect();
      return S.profiles.map((_, i) => {
        const c = deskCenter(i);
        return { left: r.left + (c.x - 15) / W * r.width, right: r.left + (c.x + 15) / W * r.width,  // cả khung nghiêng
                 top: r.top + (c.y - 16) / H * r.height, bottom: r.top + (c.y + 16) / H * r.height };
      });
    },
    // chỉ để kiểm thử: vị trí hiện tại + các điểm còn phải đi (tọa độ sàn)
    _path(name) { const b = bots.get(name); return b ? [{ gx: b.gx, gy: b.gy }, ...b.path.map((p) => ({ gx: p.gx, gy: p.gy }))] : []; },
    // chỉ để kiểm thử: các dòng nhật ký của 1 tài khoản (tiếng Việt, chưa dịch)
    _diary(name) { return diaryLines(name); },
    // chỉ để kiểm thử: trạng thái mèo (tọa độ sàn) + các điểm còn phải đi
    _cat() { return { st: cat.st, gx: cat.gx, gy: cat.gy, path: cat.path.map((p) => ({ gx: p.gx, gy: p.gy })), GX, GY }; },
    // chỉ để kiểm thử: tên tài khoản đang mở thẻ thông tin (null nếu không mở)
    _card() { return cardName; },
    // chỉ để kiểm thử: tọa độ (client) giữa thân robot, null nếu chưa có
    _pos(name) {
      const b = bots.get(name);
      if (!b || !cv) return null;
      const r = cv.getBoundingClientRect();
      return { x: r.left + b.sx / W * r.width, y: r.top + (b.sy - b.lift - 12) / H * r.height, depth: b.depth, moving: b.path.length > 0 };
    },
  };
})();
window.Office = Office;  // const ở cấp cao nhất không thành thuộc tính của window; app.js gọi qua window.Office
