export function timeAgo(dateStr) {
  const diff = Math.floor((Date.now() - new Date(dateStr + "Z").getTime()) / 1000);
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

export function severityBadge(severity) {
  const map = {
    critical: { label: "CRITICAL", cls: "bg-red-100 text-red-700 ring-red-200" },
    high:     { label: "HIGH",     cls: "bg-orange-100 text-orange-700 ring-orange-200" },
    medium:   { label: "MEDIUM",   cls: "bg-amber-100 text-amber-700 ring-amber-200" },
    low:      { label: "LOW",      cls: "bg-green-100 text-green-700 ring-green-200" },
  };
  const { label, cls } = map[severity] || { label: severity, cls: "bg-slate-100 text-slate-600" };
  return `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold font-mono ring-1 ${cls}">${label}</span>`;
}

export function statusBadge(status) {
  const map = {
    active:    { label: "활성",   cls: "bg-red-50 text-red-600" },
    reviewing: { label: "검토중", cls: "bg-blue-50 text-blue-600" },
    resolved:  { label: "해결됨", cls: "bg-slate-100 text-slate-500" },
  };
  const { label, cls } = map[status] || { label: status, cls: "bg-slate-100 text-slate-500" };
  return `<span class="inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${cls}">${label}</span>`;
}

export function moduleBadge(module) {
  const map = {
    A: { label: "모듈 A", cls: "bg-violet-100 text-violet-700" },
    B: { label: "모듈 B", cls: "bg-sky-100 text-sky-700" },
    C: { label: "모듈 C", cls: "bg-teal-100 text-teal-700" },
  };
  const { label, cls } = map[module] || { label: module, cls: "bg-slate-100 text-slate-600" };
  return `<span class="inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}">${label}</span>`;
}

export function platformIcon(platform) {
  const icons = {
    instagram: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>`,
    youtube:   `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M23.495 6.205a3.007 3.007 0 0 0-2.088-2.088c-1.87-.501-9.396-.501-9.396-.501s-7.507-.01-9.396.501A3.007 3.007 0 0 0 .527 6.205a31.247 31.247 0 0 0-.522 5.805 31.247 31.247 0 0 0 .522 5.783 3.007 3.007 0 0 0 2.088 2.088c1.868.502 9.396.502 9.396.502s7.506 0 9.396-.502a3.007 3.007 0 0 0 2.088-2.088 31.247 31.247 0 0 0 .5-5.783 31.247 31.247 0 0 0-.5-5.805zM9.609 15.601V8.408l6.264 3.602z"/></svg>`,
    x:         `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`,
    tiktok:    `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.33 6.33 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.69a8.18 8.18 0 004.78 1.52V6.76a4.84 4.84 0 01-1.01-.07z"/></svg>`,
    naver:     `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M16.273 12.845L7.376 0H0v24h7.727V11.155L16.624 24H24V0h-7.727z"/></svg>`,
  };
  return icons[platform] || `<span class="text-xs">${platform}</span>`;
}

const _cssVar = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

export function scoreColor(score) {
  if (score >= 80) return _cssVar('--clr-critical');
  if (score >= 60) return _cssVar('--clr-high');
  if (score >= 35) return _cssVar('--clr-medium');
  return _cssVar('--clr-low');
}

export function levelLabel(level) {
  const map = { CRITICAL: "즉각 대응", HIGH: "당일 대응", MEDIUM: "모니터링", LOW: "정기 리포트" };
  return map[level] || level;
}
