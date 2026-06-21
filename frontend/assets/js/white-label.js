(function () {
  var CACHE_KEY = 'wl_config';
  var CACHE_TTL = 5 * 60 * 1000;

  // ── 색상 유틸 ─────────────────────────────────────────────────────────
  function hexToRgb(hex) {
    var h = hex.replace('#', '');
    if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function hexToHsl(hex) {
    var c = hexToRgb(hex);
    var r = c[0]/255, g = c[1]/255, b = c[2]/255;
    var max = Math.max(r,g,b), min = Math.min(r,g,b);
    var h = 0, s = 0, l = (max + min) / 2;
    if (max !== min) {
      var d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
      else if (max === g) h = ((b - r) / d + 2) / 6;
      else h = ((r - g) / d + 4) / 6;
    }
    return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
  }

  function hslToHex(h, s, l) {
    s /= 100; l /= 100;
    var a = s * Math.min(l, 1 - l);
    function f(n) {
      var k = (n + h / 30) % 12;
      var v = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
      return Math.round(255 * v).toString(16).padStart(2, '0');
    }
    return '#' + f(0) + f(8) + f(4);
  }

  // delta: 양수=밝게, 음수=어둡게
  function shiftL(hex, delta) {
    var hsl = hexToHsl(hex);
    return hslToHex(hsl[0], hsl[1], Math.max(0, Math.min(100, hsl[2] + delta)));
  }

  // ── CSS 생성 ──────────────────────────────────────────────────────────
  function buildCss(color) {
    var rgb   = hexToRgb(color);
    var r = rgb[0], g = rgb[1], b = rgb[2];
    var dark  = shiftL(color, -10);  // hover / 강조 (brand-600 상당)
    var light = shiftL(color, +10);  // 선택 상태 (brand-400 상당)

    var lines = [
      // CSS 변수 — 전체 팔레트 노출
      ':root {',
      '  --brand-500: ' + color + ';',
      '  --brand-600: ' + dark  + ';',
      '  --brand-400: ' + light + ';',
      '  --clr-brand: ' + color + ';',
      '}',

      // ── 단색 배경 ──
      '[style*="background:#1a6ef8"],[style*="background: #1a6ef8"],' +
      '[style*="background-color:#1a6ef8"],[style*="background-color: #1a6ef8"] ' +
      '{ background-color:' + color + ' !important; background:' + color + ' !important; }',

      // hover/dark shade (#1558cc) — 버튼 hover 등
      '[style*="background:#1558cc"],[style*="background: #1558cc"] ' +
      '{ background-color:' + dark + ' !important; background:' + dark + ' !important; }',

      // ── 텍스트 ──
      '[style*="color:#1a6ef8"],[style*="color: #1a6ef8"] { color:' + color + ' !important; }',
      '[style*="color:#1558cc"],[style*="color: #1558cc"] { color:' + dark  + ' !important; }',

      // ── 테두리 ──
      '[style*="border-color:#1a6ef8"],[style*="border-color: #1a6ef8"] { border-color:' + color + ' !important; }',
      '[style*="solid #1a6ef8"] { border-color:' + color + ' !important; }',
      '[style*="solid #1558cc"] { border-color:' + dark  + ' !important; }',

      // ── SVG 속성 ──
      '[stroke="#1a6ef8"] { stroke:' + color + ' !important; }',
      '[fill="#1a6ef8"]   { fill:'   + color + ' !important; }',

      // ── rgba 배경 tint ──
      '[style*="background:rgba(26,110,248,0.1)"],' +
      '[style*="background: rgba(26,110,248,0.1)"],' +
      '[style*="background:rgba(26,110,248,.1)"],' +
      '[style*="background:rgba(26,110,248,.10)"],' +
      '[style*="background:rgba(26,110,248,0.10)"]' +
      '{ background-color:rgba(' + r + ',' + g + ',' + b + ',0.1) !important; }',

      '[style*="background:rgba(26,110,248,0.06)"],' +
      '[style*="background: rgba(26,110,248,0.06)"],' +
      '[style*="background:rgba(26,110,248,.06)"]' +
      '{ background-color:rgba(' + r + ',' + g + ',' + b + ',0.06) !important; }',

      '[style*="background:rgba(26,110,248,0.12)"],' +
      '[style*="background: rgba(26,110,248,0.12)"],' +
      '[style*="background:rgba(26,110,248,.12)"]' +
      '{ background-color:rgba(' + r + ',' + g + ',' + b + ',0.12) !important; }',

      // ── hover 클래스 ──
      '.btn-primary { background:' + color + ' !important; }',
      '.btn-primary:hover { background:' + dark  + ' !important; }',

      // ── AI 어시스턴트 버튼 box-shadow ──
      '#btn-assistant { box-shadow:0 4px 16px rgba(' + r + ',' + g + ',' + b + ',0.4) !important; }',

      // ── 네비게이션 활성 ──
      '.db-nav-active { border-left-color:' + color + ' !important; color:' + color + ' !important; }',

      // ── 클래스 기반 (custom.css) ──
      '.toast-notification.info { border-left-color:' + color + ' !important; }',
      '.bp-input:focus, .bp-select:focus, .bp-textarea:focus { border-color:' + color + ' !important; }',

      // ── 선택/active 상태 배경 ──
      '.path-card.selected { border-color:' + color + ' !important; background:rgba(' + r + ',' + g + ',' + b + ',0.1) !important; }',
      '.type-btn.selected  { border-color:' + color + ' !important; background:rgba(' + r + ',' + g + ',' + b + ',0.12) !important; color:' + color + ' !important; }',
      'input:focus, select:focus { border-color:' + color + ' !important; }',

      // ── step dot (온보딩) ──
      '.step-dot.active { background:' + color + ' !important; }',
    ];
    return lines.join('\n');
  }

  // ── 적용 ─────────────────────────────────────────────────────────────
  function applyConfig(cfg) {
    if (!cfg) return;
    if (cfg.color) {
      var el = document.getElementById('wl-override');
      if (!el) { el = document.createElement('style'); el.id = 'wl-override'; document.head.appendChild(el); }
      el.textContent = buildCss(cfg.color);
    }
    if (cfg.brand_name) {
      var nameEl = document.querySelector('aside a[href="/"] span');
      if (nameEl) nameEl.textContent = cfg.brand_name;
      document.title = document.title.replace(/SAYbrand/g, cfg.brand_name);
    }
    if (cfg.logo_url) {
      var logoEl = document.querySelector('aside a[href="/"] img');
      if (logoEl) { logoEl.src = cfg.logo_url; logoEl.onerror = null; }
    }
  }

  // ── 캐시 우선 적용 ────────────────────────────────────────────────────
  var needsFetch = true;
  try {
    var raw = localStorage.getItem(CACHE_KEY);
    if (raw) {
      var cached = JSON.parse(raw);
      if (Date.now() - cached.ts < CACHE_TTL) {
        applyConfig(cached.data);
        needsFetch = false;
      }
    }
  } catch (_) {}

  if (!needsFetch) return;

  fetch('/api/orgs').then(function (r) { return r.ok ? r.json() : []; }).then(function (orgs) {
    if (!orgs.length) { localStorage.removeItem(CACHE_KEY); return; }
    var org = orgs[0];
    if (!org.white_label_enabled) { localStorage.removeItem(CACHE_KEY); return; }
    var data = { brand_name: org.white_label_brand_name, color: org.white_label_color, logo_url: org.white_label_logo_url };
    localStorage.setItem(CACHE_KEY, JSON.stringify({ data: data, ts: Date.now() }));
    applyConfig(data);
  }).catch(function () {});
})();
