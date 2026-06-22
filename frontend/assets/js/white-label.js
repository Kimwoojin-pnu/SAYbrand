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

  function shiftL(hex, delta) {
    var hsl = hexToHsl(hex);
    return hslToHex(hsl[0], hsl[1], Math.max(0, Math.min(100, hsl[2] + delta)));
  }

  // WCAG 상대 휘도 — L > 0.179 이면 배경이 밝은 것 → 어두운 글씨 사용
  function contrastColor(hex) {
    var c = hexToRgb(hex);
    function lin(v) { v /= 255; return v <= 0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }
    var L = 0.2126*lin(c[0]) + 0.7152*lin(c[1]) + 0.0722*lin(c[2]);
    return L > 0.179 ? '#0c1428' : '#ffffff';
  }

  // ── 사이드바 CSS 생성 ────────────────────────────────────────────────
  function buildSidebarCss(sidebarColor) {
    var sText = contrastColor(sidebarColor);
    var isDark = sText === '#ffffff';
    var sDark = shiftL(sidebarColor, -5);
    var lines = [
      'aside { background: ' + sidebarColor + ' !important; }',
      'aside #org-menu { background: ' + sDark + ' !important; }',
    ];
    if (!isDark) {
      // 밝은 배경이면 사이드바 내 흰색 텍스트를 어두운 색으로 교체
      lines.push(
        'aside [style*="color:#fff"],aside [style*="color:#ffffff"] { color: #0c1428 !important; }',
        'aside [style*="rgba(255,255,255,0.4)"],aside [style*="rgba(255,255,255,.4)"] { color: rgba(12,20,40,0.5) !important; }',
        'aside [style*="rgba(255,255,255,0.35)"] { color: rgba(12,20,40,0.45) !important; }',
        'aside [style*="rgba(255,255,255,0.2)"] { color: rgba(12,20,40,0.3) !important; }',
        'aside [style*="rgba(255,255,255,0.6)"] { color: rgba(12,20,40,0.7) !important; }',
        'aside .db-nav-item { color: rgba(12,20,40,0.65) !important; }',
        'aside .db-nav-active { color: #0c1428 !important; border-left-color: #0c1428 !important; }',
        'aside [style*="background:rgba(255,255,255,0.06)"],aside [style*="background: rgba(255,255,255,0.06)"] { background: rgba(12,20,40,0.06) !important; }'
      );
    }
    return lines.join('\n');
  }

  // ── CSS 생성 ──────────────────────────────────────────────────────────
  function buildCss(color, sidebarColor) {
    var rgb   = hexToRgb(color);
    var r = rgb[0], g = rgb[1], b = rgb[2];
    var dark    = shiftL(color, -10);
    var light   = shiftL(color, +10);
    var textClr = contrastColor(color);       // 브랜드 배경 위 글씨 색
    var textDark = contrastColor(dark);       // dark shade 배경 위 글씨 색

    var lines = [
      // CSS 변수
      ':root {',
      '  --brand-500: ' + color + ';',
      '  --brand-600: ' + dark  + ';',
      '  --brand-400: ' + light + ';',
      '  --clr-brand: ' + color + ';',
      '  --brand-text: ' + textClr + ';',
      '}',

      // ── 단색 배경 + 글씨 대비 ──
      '[style*="background:#1a6ef8"],[style*="background: #1a6ef8"],' +
      '[style*="background-color:#1a6ef8"],[style*="background-color: #1a6ef8"] ' +
      '{ background-color:' + color + ' !important; background:' + color + ' !important;' +
      '  color:' + textClr + ' !important; }',

      // dark shade 배경
      '[style*="background:#1558cc"],[style*="background: #1558cc"] ' +
      '{ background-color:' + dark + ' !important; background:' + dark + ' !important;' +
      '  color:' + textDark + ' !important; }',

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

      // rgba tint 안의 글씨는 브랜드 색으로 (뱃지/태그)
      '[style*="rgba(26,110,248"][style*="color:#1a6ef8"]' +
      '{ color:' + color + ' !important; }',

      // ── AI 어시스턴트 버튼 box-shadow + 글씨 ──
      '#btn-assistant { box-shadow:0 4px 16px rgba(' + r + ',' + g + ',' + b + ',0.4) !important;' +
      ' color:' + textClr + ' !important; }',

      // ── 버튼 클래스 ──
      '.btn-primary { background:' + color + ' !important; color:' + textClr + ' !important; }',
      '.btn-primary:hover { background:' + dark + ' !important; color:' + textDark + ' !important; }',

      // ── 네비게이션 활성 ──
      '.db-nav-active { border-left-color:' + color + ' !important; color:' + color + ' !important; }',

      // ── CSS 클래스 기반 (custom.css) ──
      '.toast-notification.info { border-left-color:' + color + ' !important; }',
      '.bp-input:focus, .bp-select:focus, .bp-textarea:focus { border-color:' + color + ' !important; }',

      // ── 선택/active 상태 ──
      '.path-card.selected { border-color:' + color + ' !important; background:rgba(' + r + ',' + g + ',' + b + ',0.1) !important; }',
      '.type-btn.selected  { border-color:' + color + ' !important; background:rgba(' + r + ',' + g + ',' + b + ',0.12) !important; color:' + color + ' !important; }',
      'input:focus, select:focus { border-color:' + color + ' !important; }',
      '.step-dot.active { background:' + color + ' !important; }',
    ];
    if (sidebarColor) lines.push(buildSidebarCss(sidebarColor));
    return lines.join('\n');
  }

  // ── 적용 ─────────────────────────────────────────────────────────────
  function applyConfig(cfg) {
    if (!cfg) return;

    if (cfg.color || cfg.sidebar_color) {
      // CSS 주입
      var el = document.getElementById('wl-override');
      if (!el) { el = document.createElement('style'); el.id = 'wl-override'; document.head.appendChild(el); }
      el.textContent = cfg.color ? buildCss(cfg.color, cfg.sidebar_color) : buildSidebarCss(cfg.sidebar_color);
    }

    if (cfg.color) {
      var textClr = contrastColor(cfg.color);
      var dark    = shiftL(cfg.color, -10);
      var textDark = contrastColor(dark);

      // meta theme-color (모바일 브라우저 상단)
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute('content', cfg.color);

      // _btnOn monkey-patch (reports.html — JS 직접 할당은 CSS 선택자에 안 걸림)
      if (typeof window._btnOn === 'function' && !window._btnOn._wl) {
        var _orig = window._btnOn;
        window._btnOn = function (b) {
          _orig(b);
          if (b) { b.style.background = cfg.color; b.style.color = textClr; }
        };
        window._btnOn._wl = true;
      }

      // _buildGraphData monkey-patch (ECharts 브랜드 노드 색상)
      if (typeof window._buildGraphData === 'function' && !window._buildGraphData._wl) {
        var _origGraph = window._buildGraphData;
        var _rgb = hexToRgb(cfg.color);
        window._buildGraphData = function (data) {
          var result = _origGraph(data);
          // 중심 브랜드 노드를 찾아 색상 교체
          if (result && result.nodes) {
            result.nodes.forEach(function (node) {
              if (node._type === 'brand' && node.itemStyle) {
                node.itemStyle.color = cfg.color;
                node.itemStyle.shadowColor = 'rgba(' + _rgb[0] + ',' + _rgb[1] + ',' + _rgb[2] + ',0.6)';
                if (node.label) node.label.color = textClr;
              }
            });
          }
          return result;
        };
        window._buildGraphData._wl = true;
      }
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
    var data = { brand_name: org.white_label_brand_name, color: org.white_label_color, sidebar_color: org.white_label_sidebar_color, logo_url: org.white_label_logo_url };
    localStorage.setItem(CACHE_KEY, JSON.stringify({ data: data, ts: Date.now() }));
    applyConfig(data);
  }).catch(function () {});
})();
