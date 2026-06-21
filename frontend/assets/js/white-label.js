(async function applyWhiteLabel() {
  try {
    const orgs = await fetch('/api/orgs').then(r => r.ok ? r.json() : []);
    if (!orgs.length) return;
    const org = orgs[0];
    if (!org.white_label_enabled) return;

    const brandName = org.white_label_brand_name;
    const color = org.white_label_color;
    const logoUrl = org.white_label_logo_url;

    if (brandName) {
      const nameEl = document.querySelector('aside a[href="/"] span');
      if (nameEl) nameEl.textContent = brandName;
      document.title = document.title.replace('SAYbrand', brandName);
    }

    if (logoUrl) {
      const logoEl = document.querySelector('aside a[href="/"] img');
      if (logoEl) { logoEl.src = logoUrl; logoEl.onerror = null; }
    }

    if (color) {
      const style = document.createElement('style');
      style.textContent = [
        `:root { --brand-500: ${color}; }`,
        `.db-nav-active { border-left-color: ${color} !important; color: ${color} !important; }`,
        `[style*="background:#1a6ef8"] { background-color: ${color} !important; }`,
        `[style*="background: #1a6ef8"] { background-color: ${color} !important; }`,
        `[style*="background:rgba(26,110,248"] { background-color: ${color}22 !important; }`,
        `[style*="color:#1a6ef8"] { color: ${color} !important; }`,
        `[style*="color: #1a6ef8"] { color: ${color} !important; }`,
        `[style*="border-color:#1a6ef8"] { border-color: ${color} !important; }`,
        `button[style*="#1a6ef8"] { background-color: ${color} !important; }`,
        `a[style*="background:#1a6ef8"] { background-color: ${color} !important; }`,
      ].join('\n');
      document.head.appendChild(style);
    }
  } catch (_) {}
})();
