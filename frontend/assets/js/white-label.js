(function () {
  var CACHE_KEY = 'wl_config';
  var CACHE_TTL = 5 * 60 * 1000; // 5분

  function hexToRgb(hex) {
    var h = hex.replace('#', '');
    if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function buildCss(color) {
    var rgb = hexToRgb(color);
    var r = rgb[0], g = rgb[1], b = rgb[2];
    var lines = [
      // CSS 변수
      ':root { --brand-500: ' + color + '; --clr-brand: ' + color + '; }',

      // 단색 배경
      '[style*="background:#1a6ef8"],[style*="background: #1a6ef8"],' +
      '[style*="background-color:#1a6ef8"],[style*="background-color: #1a6ef8"] ' +
      '{ background-color: ' + color + ' !important; background: ' + color + ' !important; }',

      // 텍스트
      '[style*="color:#1a6ef8"],[style*="color: #1a6ef8"] { color: ' + color + ' !important; }',

      // 테두리 단색
      '[style*="border-color:#1a6ef8"],[style*="border-color: #1a6ef8"] { border-color: ' + color + ' !important; }',
      '[style*="solid #1a6ef8"] { border-color: ' + color + ' !important; }',

      // SVG 속성 (stroke="/fill= 형태)
      '[stroke="#1a6ef8"] { stroke: ' + color + ' !important; }',
      '[fill="#1a6ef8"] { fill: ' + color + ' !important; }',

      // rgba 배경 (10%)
      '[style*="background:rgba(26,110,248,0.1)"],[style*="background: rgba(26,110,248,0.1)"],' +
      '[style*="background:rgba(26,110,248,.1)"],[style*="background:rgba(26,110,248,0.10)"],' +
      '[style*="background:rgba(26,110,248,.10)"]' +
      '{ background-color: rgba(' + r + ',' + g + ',' + b + ',0.1) !important; }',

      // rgba 배경 (6%)
      '[style*="background:rgba(26,110,248,0.06)"],[style*="background: rgba(26,110,248,0.06)"],' +
      '[style*="background:rgba(26,110,248,.06)"]' +
      '{ background-color: rgba(' + r + ',' + g + ',' + b + ',0.06) !important; }',

      // rgba 배경 (12%)
      '[style*="background:rgba(26,110,248,0.12)"],[style*="background: rgba(26,110,248,0.12)"],' +
      '[style*="background:rgba(26,110,248,.12)"]' +
      '{ background-color: rgba(' + r + ',' + g + ',' + b + ',0.12) !important; }',

      // AI 어시스턴트 버튼 box-shadow
      '#btn-assistant { box-shadow: 0 4px 16px rgba(' + r + ',' + g + ',' + b + ',0.4) !important; }',

      // 네비게이션 활성
      '.db-nav-active { border-left-color: ' + color + ' !important; color: ' + color + ' !important; }',

      // 클래스 기반 (custom.css)
      '.toast-notification.info { border-left-color: ' + color + ' !important; }',
      '.bp-input:focus, .bp-select:focus, .bp-textarea:focus { border-color: ' + color + ' !important; }',
    ];
    return lines.join('\n');
  }

  function applyConfig(cfg) {
    if (!cfg) return;

    if (cfg.color) {
      var el = document.getElementById('wl-override');
      if (!el) {
        el = document.createElement('style');
        el.id = 'wl-override';
        document.head.appendChild(el);
      }
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

  // 캐시에서 즉시 적용 (API 호출 없이)
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

  // 캐시 만료 또는 미존재 → API 조회 후 캐시 저장
  fetch('/api/orgs').then(function (r) {
    return r.ok ? r.json() : [];
  }).then(function (orgs) {
    if (!orgs.length) { localStorage.removeItem(CACHE_KEY); return; }
    var org = orgs[0];
    if (!org.white_label_enabled) { localStorage.removeItem(CACHE_KEY); return; }
    var data = {
      brand_name: org.white_label_brand_name,
      color: org.white_label_color,
      logo_url: org.white_label_logo_url,
    };
    localStorage.setItem(CACHE_KEY, JSON.stringify({ data: data, ts: Date.now() }));
    applyConfig(data);
  }).catch(function () {});
})();
