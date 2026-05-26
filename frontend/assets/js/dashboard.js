import { api } from "/assets/js/api.js";
import { keywordApi } from "/assets/js/api.js";
import { timeAgo, severityBadge, statusBadge, moduleBadge, platformIcon, scoreColor, levelLabel } from "/assets/js/utils.js";

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = "success") {
  const wrap = document.getElementById("toast-wrap");
  if (!wrap) return;
  const colors = { success: "#1D9E75", error: "#E24B4A", info: "#185FA5", critical: "#E24B4A", high: "#BA7517", medium: "#185FA5", low: "#1D9E75" };
  const color = colors[type] || "#1D9E75";
  const el = document.createElement("div");
  el.style.cssText = `display:flex;align-items:center;gap:10px;padding:11px 14px;background:#fff;border:1px solid rgba(0,0,0,.08);border-left:3px solid ${color};border-radius:8px;box-shadow:rgba(12,20,40,.14) 0 4px 16px;font-size:12px;font-family:'NanumSquare',sans-serif;pointer-events:auto;transform:translateX(120%);transition:transform .3s cubic-bezier(.34,1.56,.64,1);min-width:260px;max-width:340px;`;
  el.innerHTML = `<span style="width:7px;height:7px;border-radius:50%;background:${color};flex-shrink:0;"></span><span style="color:#0c1428;">${msg}</span>`;
  wrap.appendChild(el);
  requestAnimationFrame(() => requestAnimationFrame(() => { el.style.transform = "translateX(0)"; }));
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .4s"; setTimeout(() => el.remove(), 400); }, 3500);
}

// ── State ─────────────────────────────────────────────────────────────────────
const state = { threats: [], total: 0, page: 1, pageSize: 10, filterSeverity: "", filterStatus: "", selectedThreat: null };

// ── Gauge ─────────────────────────────────────────────────────────────────────
const GAUGE_ARC = 376.99;
function renderGauge(score, level) {
  const filled = (score / 100) * GAUGE_ARC;
  const color = scoreColor(score);
  document.getElementById("gauge-value").setAttribute("stroke-dasharray", `${filled} ${GAUGE_ARC + 10}`);
  document.getElementById("gauge-value").setAttribute("stroke", color);
  document.getElementById("gauge-score").textContent = Math.round(score);
  document.getElementById("gauge-score").setAttribute("fill", color);
  document.getElementById("gauge-level").textContent = level;
  document.getElementById("gauge-level").setAttribute("fill", color);
  const actionEl = document.getElementById("gauge-action");
  actionEl.textContent = levelLabel(level);
  actionEl.style.color = color;
}

function renderModuleBar(id, score, count) {
  const el = document.getElementById(id);
  if (!el) return;
  el.querySelector(".module-bar").style.width = `${Math.min(score, 100)}%`;
  el.querySelector(".module-bar").style.backgroundColor = scoreColor(score);
  el.querySelector(".module-score").textContent = Math.round(score);
  el.querySelector(".module-count").textContent = `${count}건`;
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function renderStats(stats) {
  document.getElementById("stat-critical").textContent = stats.critical;
  document.getElementById("stat-high").textContent = stats.high;
  document.getElementById("stat-medium").textContent = stats.medium;
  document.getElementById("stat-low").textContent = stats.low;
  document.getElementById("stat-active").textContent = stats.active;
  document.getElementById("stat-reviewing").textContent = stats.reviewing;
  document.getElementById("stat-total").textContent = stats.total;
}

// ── Alerts ────────────────────────────────────────────────────────────────────
function renderAlerts(alerts) {
  const el = document.getElementById("alerts-feed");
  if (!alerts.length) { el.innerHTML = `<p style="color:rgba(12,20,40,.35);font-size:12px;text-align:center;padding:20px;">알림 없음</p>`; return; }
  const dots = { critical: "#E24B4A", high: "#BA7517", medium: "#185FA5", low: "#1D9E75" };
  el.innerHTML = alerts.map(a => `
    <div style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid rgba(0,0,0,.05);">
      <span style="margin-top:4px;flex-shrink:0;width:6px;height:6px;border-radius:50%;background:${dots[a.severity] || '#94a3b8'};"></span>
      <div style="flex:1;min-width:0;">
        <p style="font-size:12px;color:#0c1428;line-height:1.5;">${a.message}</p>
        <p style="font-size:10px;color:rgba(12,20,40,.35);margin-top:2px;font-family:'JetBrains Mono',monospace;">${timeAgo(a.sent_at)}</p>
      </div>
    </div>`).join("");
}

// ── Chart dark-mode helpers ───────────────────────────────────────────────────
function isDark() { return document.documentElement.getAttribute('data-theme') === 'dark'; }
function chartColors() {
  const d = isDark();
  return {
    grid:   d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
    tick:   d ? 'rgba(230,237,243,0.38)' : 'rgba(12,20,40,0.38)',
    legend: d ? 'rgba(230,237,243,0.55)' : 'rgba(12,20,40,0.55)',
  };
}
function applyChartTheme() {
  if (!trendChart) return;
  const c = chartColors();
  trendChart.options.scales.x.grid.color = c.grid;
  trendChart.options.scales.x.ticks.color = c.tick;
  trendChart.options.scales.y.grid.color = c.grid;
  trendChart.options.scales.y.ticks.color = c.tick;
  trendChart.options.plugins.legend.labels.color = c.legend;
  trendChart.update('none');
}

// ── Trend Chart ───────────────────────────────────────────────────────────────
let trendChart = null;

function buildDatasets(data) {
  return [
    { label: '모듈 A (브랜드 사칭)',   data: data.module_a || [], borderColor: '#E24B4A', backgroundColor: 'rgba(226,75,74,.06)', tension: .4, fill: true, pointRadius: 3, pointHoverRadius: 5, borderWidth: 2 },
    { label: '모듈 B (가짜뉴스·루머)', data: data.module_b || [], borderColor: '#BA7517', backgroundColor: 'rgba(186,117,23,.06)', tension: .4, fill: true, pointRadius: 3, pointHoverRadius: 5, borderWidth: 2 },
    { label: '모듈 C (임직원 평판)',   data: data.module_c || [], borderColor: '#185FA5', backgroundColor: 'rgba(24,95,165,.06)', tension: .4, fill: true, pointRadius: 3, pointHoverRadius: 5, borderWidth: 2 },
  ];
}

async function initTrendChart() {
  const ctx = document.getElementById("trendChart");
  if (!ctx || !window.Chart) return;
  const c = chartColors();

  let trendData = { labels: ['6일전','5일전','4일전','3일전','2일전','어제','오늘'], module_a: [0,0,0,0,0,0,0], module_b: [0,0,0,0,0,0,0], module_c: [0,0,0,0,0,0,0] };
  try { trendData = await api.trend(); } catch (_) {}

  const datasets = buildDatasets(trendData);
  trendChart = new Chart(ctx, {
    type: "line",
    data: { labels: trendData.labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { font: { family: "'NanumSquare',sans-serif", size: 11 }, usePointStyle: true, pointStyleWidth: 8, padding: 14, color: c.legend } },
        tooltip: { backgroundColor: "#0c1428", titleFont: { family: "'NanumSquare',sans-serif", weight: "700", size: 11 }, bodyFont: { family: "'NanumSquare',sans-serif", size: 11 }, padding: 10, cornerRadius: 5, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}건` } },
      },
      scales: {
        x: { grid: { color: c.grid }, ticks: { font: { family: "'NanumSquare',sans-serif", size: 10 }, color: c.tick }, border: { display: false } },
        y: { grid: { color: c.grid }, ticks: { font: { family: "'NanumSquare',sans-serif", size: 10 }, color: c.tick }, border: { display: false }, beginAtZero: true },
      },
      interaction: { intersect: false, mode: "index" },
    },
  });

  document.querySelectorAll(".trend-filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".trend-filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const idx = btn.dataset.dataset;
      datasets.forEach((_, i) => trendChart.setDatasetVisibility(i, idx === "" || idx == i));
      trendChart.update();
    });
  });
}

// ── Platform Stats ────────────────────────────────────────────────────────────
const PLATFORM_META = {
  instagram: { name: "Instagram", abbr: "IG", color: "#e1306c" },
  x:         { name: "X (트위터)", abbr: "X",  color: "#334155" },
  youtube:   { name: "YouTube",   abbr: "YT", color: "#ff0000" },
  tiktok:    { name: "TikTok",    abbr: "TT", color: "#69c9d0" },
  naver:     { name: "Naver",     abbr: "NV", color: "#03c75a" },
};

async function renderPlatformStats() {
  const el = document.getElementById("platform-list");
  if (!el) return;
  let data = [];
  try { data = await api.platformStats(); } catch (_) {}
  if (!data.length) {
    el.innerHTML = `<p style="font-size:11px;color:rgba(12,20,40,.35);padding:16px 0;">수집 후 표시됩니다.</p>`;
    return;
  }
  el.innerHTML = data.map(p => {
    const m = PLATFORM_META[p.platform] || { name: p.platform, abbr: p.platform[0].toUpperCase(), color: "#6B7280" };
    return `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid rgba(0,0,0,.05);">
      <span style="width:22px;height:22px;border-radius:4px;background:${m.color}18;color:${m.color};font-size:8px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;">${m.abbr}</span>
      <span style="font-size:11px;color:#0c1428;width:72px;flex-shrink:0;">${m.name}</span>
      <div style="flex:1;height:3px;background:rgba(0,0,0,.06);border-radius:2px;">
        <div style="height:100%;width:0%;border-radius:2px;background:#185FA5;transition:width 1s ease;" data-pct="${p.pct}"></div>
      </div>
      <span style="font-size:10px;color:rgba(12,20,40,.45);font-family:'JetBrains Mono',monospace;width:38px;text-align:right;flex-shrink:0;">${p.count}</span>
    </div>`;
  }).join("");
  requestAnimationFrame(() => el.querySelectorAll("[data-pct]").forEach(b => { b.style.width = b.getAttribute("data-pct") + "%"; }));
}

// ── Mock 배지 ─────────────────────────────────────────────────────────────────
function updateMockBadge(stats) {
  const badge = document.getElementById("mock-banner");
  if (!badge) return;
  // API 키가 없거나 데이터가 0건이면 데모 상태로 간주
  const hasRealScan = localStorage.getItem("sb-scanned") === "true";
  const hasMock = !hasRealScan || stats.total === 0;
  badge.style.display = hasMock ? "flex" : "none";
}

// ── 30초 폴링 ─────────────────────────────────────────────────────────────────
function startPolling() {
  setInterval(async () => {
    try {
      const [stats, riskScore] = await Promise.all([api.stats(), api.riskScore()]);
      renderStats(stats);
      renderGauge(riskScore.overall, riskScore.level);
      renderModuleBar("module-a", riskScore.module_a.score, riskScore.module_a.threat_count);
      renderModuleBar("module-b", riskScore.module_b.score, riskScore.module_b.threat_count);
      renderModuleBar("module-c", riskScore.module_c.score, riskScore.module_c.threat_count);
      document.getElementById("last-updated").textContent = new Date().toLocaleTimeString("ko-KR");
    } catch (_) {}
  }, 30000);
}

// ── 수동 스캔 ─────────────────────────────────────────────────────────────────
async function runScan() {
  const btn = document.getElementById("btn-scan");
  if (btn) { btn.disabled = true; btn.textContent = "스캔 중..."; }
  try {
    const result = await api.scan([], "all");
    if (result.scanned > 0) localStorage.setItem("sb-scanned", "true");
    showToast(`스캔 완료 — ${result.new_threats}건 신규 위협 탐지 (수집: ${result.scanned}건)`, result.new_threats > 0 ? "info" : "success");
    await loadThreats();
    const [stats, riskScore] = await Promise.all([api.stats(), api.riskScore()]);
    renderStats(stats);
    renderGauge(riskScore.overall, riskScore.level);
    renderModuleBar("module-a", riskScore.module_a.score, riskScore.module_a.threat_count);
    renderModuleBar("module-b", riskScore.module_b.score, riskScore.module_b.threat_count);
    renderModuleBar("module-c", riskScore.module_c.score, riskScore.module_c.threat_count);
  } catch (e) {
    showToast("스캔 실패: " + e.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "스캔 실행"; }
  }
}

// ── Threat Table ──────────────────────────────────────────────────────────────
function renderThreats(data) {
  state.threats = data.items;
  state.total = data.total;
  const tbody = document.getElementById("threat-tbody");
  if (!data.items.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding:36px;text-align:center;color:rgba(12,20,40,.35);">위협 없음</td></tr>`;
  } else {
    tbody.innerHTML = data.items.map(t => `
      <tr style="cursor:pointer;transition:background .1s;border-bottom:1px solid rgba(0,0,0,.05);" onmouseover="this.style.background='rgba(0,0,0,.02)'" onmouseout="this.style.background='transparent'" data-id="${t.id}" onclick="window._openThreat(${t.id})">
        <td style="padding:10px 14px;">${severityBadge(t.severity)}</td>
        <td style="padding:10px 14px;">
          <div style="display:flex;align-items:center;gap:6px;">
            ${moduleBadge(t.module)}
            <span style="font-size:12px;color:#0c1428;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${formatThreatType(t.threat_type)}</span>
          </div>
        </td>
        <td style="padding:10px 14px;">
          <div style="display:flex;align-items:center;gap:5px;font-size:12px;color:rgba(12,20,40,.60);">
            ${platformIcon(t.platform)}<span style="text-transform:capitalize;">${t.platform}</span>
          </div>
        </td>
        <td style="padding:10px 14px;font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(12,20,40,.60);max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${t.source_account}</td>
        <td style="padding:10px 14px;"><span style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;" style="color:${scoreColor(t.risk_score)}">${t.risk_score}</span></td>
        <td style="padding:10px 14px;font-size:11px;color:rgba(12,20,40,.38);font-family:'JetBrains Mono',monospace;white-space:nowrap;">${timeAgo(t.detected_at)}</td>
        <td style="padding:10px 14px;">${statusBadge(t.status)}</td>
      </tr>`).join("");
  }
  renderPagination(data.total, data.page, data.page_size);
}

function formatThreatType(type) {
  const map = { logo_spoof:"로고 사칭", account_impersonation:"계정 사칭", organized_rumor:"조직적 루머", viral_rumor:"바이럴 루머", executive_exposure:"임직원 노출", bot_attack:"봇 공격", reputation_attack:"평판 공격", negative_review_cluster:"부정 리뷰 클러스터", internal_info_leak:"내부 정보 유출", watermark_removal:"워터마크 제거", negative_comment:"부정 댓글", casual_mention:"일반 언급", competitor_mention:"경쟁사 언급", similar_logo:"유사 로고" };
  return map[type] || type;
}

function renderPagination(total, page, pageSize) {
  const tp = Math.max(1, Math.ceil(total / pageSize));
  document.getElementById("page-info").textContent = `${page} / ${tp} 페이지 (총 ${total}건)`;
  document.getElementById("btn-prev").disabled = page <= 1;
  document.getElementById("btn-next").disabled = page >= tp;
}

// ── Detail Panel ──────────────────────────────────────────────────────────────
window._openThreat = function(id) {
  const threat = state.threats.find(t => t.id === id);
  if (!threat) return;
  state.selectedThreat = threat;

  document.getElementById("detail-severity").innerHTML = severityBadge(threat.severity);
  document.getElementById("detail-module").innerHTML = moduleBadge(threat.module);
  document.getElementById("detail-account").textContent = threat.source_account;
  document.getElementById("detail-platform").innerHTML = `<span style="display:inline-flex;align-items:center;gap:4px;">${platformIcon(threat.platform)} ${threat.platform}</span>`;
  document.getElementById("detail-detected").textContent = timeAgo(threat.detected_at);
  document.getElementById("detail-content").textContent = threat.content_preview;

  const scoreEl = document.getElementById("detail-score");
  scoreEl.textContent = `${threat.risk_score}/100`;
  scoreEl.style.color = scoreColor(threat.risk_score);
  document.getElementById("detail-confidence").textContent = `${Math.round(threat.confidence * 100)}%`;

  const botEl = document.getElementById("detail-bot");
  if (threat.bot_probability != null) {
    const pct = Math.round(threat.bot_probability * 100);
    botEl.textContent = pct + "%";
    botEl.style.color = pct >= 70 ? "#E24B4A" : pct >= 40 ? "#BA7517" : "#1D9E75";
  } else { botEl.textContent = "—"; botEl.style.color = "rgba(12,20,40,.35)"; }

  const orgEl = document.getElementById("detail-organized");
  if (threat.is_organized === true)       { orgEl.textContent = "감지됨"; orgEl.style.color = "#BA7517"; }
  else if (threat.is_organized === false) { orgEl.textContent = "감지되지 않음"; orgEl.style.color = "#1D9E75"; }
  else                                    { orgEl.textContent = "—"; orgEl.style.color = "rgba(12,20,40,.35)"; }

  const analysisWrap = document.getElementById("detail-analysis-wrap");
  if (threat.ai_analysis) { document.getElementById("detail-analysis").textContent = threat.ai_analysis; analysisWrap.style.display = ""; }
  else { analysisWrap.style.display = "none"; }

  const suggWrap = document.getElementById("detail-suggestion-wrap");
  if (threat.ai_response_suggestion) { document.getElementById("detail-suggestion").textContent = threat.ai_response_suggestion; suggWrap.style.display = ""; }
  else { suggWrap.style.display = "none"; }

  const linkEl = document.getElementById("detail-url");
  if (threat.source_url) { linkEl.href = threat.source_url; linkEl.style.display = "inline-flex"; }
  else { linkEl.style.display = "none"; }

  ["active","reviewing","resolved"].forEach(s => {
    const btn = document.getElementById(`status-${s}`);
    btn.style.opacity = threat.status === s ? "1" : "0.55";
    btn.style.fontWeight = threat.status === s ? "800" : "700";
  });

  openPanel();
};

function openPanel() {
  document.getElementById("detail-panel").style.transform = "translateX(0)";
  document.getElementById("panel-backdrop").style.display = "block";
  document.body.style.overflow = "hidden";
}

function closePanel() {
  document.getElementById("detail-panel").style.transform = "translateX(100%)";
  document.getElementById("panel-backdrop").style.display = "none";
  document.body.style.overflow = "";
  state.selectedThreat = null;
}

async function handleStatusChange(newStatus) {
  if (!state.selectedThreat) return;
  try {
    await api.updateStatus(state.selectedThreat.id, newStatus);
    state.selectedThreat.status = newStatus;
    ["active","reviewing","resolved"].forEach(s => {
      const btn = document.getElementById(`status-${s}`);
      btn.style.opacity = s === newStatus ? "1" : "0.55";
      btn.style.fontWeight = s === newStatus ? "800" : "700";
    });
    await loadThreats();
    const labels = { active:"활성", reviewing:"검토중", resolved:"해결됨" };
    showToast(`상태가 "${labels[newStatus]}"으로 변경되었습니다`);
  } catch (e) { showToast("상태 변경 실패: " + e.message, "error"); }
}

// ── Filters ───────────────────────────────────────────────────────────────────
function setFilter(severity) {
  state.filterSeverity = severity; state.page = 1;
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.toggle("active", b.dataset.severity === severity));
  loadThreats();
}

function setStatusFilter(status) {
  state.filterStatus = status; state.page = 1;
  document.querySelectorAll(".status-filter-btn").forEach(b => b.classList.toggle("active", b.dataset.status === status));
  loadThreats();
}

// ── Data ──────────────────────────────────────────────────────────────────────
async function loadThreats() {
  const data = await api.threats({ severity: state.filterSeverity || null, status: state.filterStatus || null, page: state.page, page_size: state.pageSize });
  renderThreats(data);
}

async function initDashboard() {
  try {
    const [stats, riskScore, alerts] = await Promise.all([api.stats(), api.riskScore(), api.alerts(8)]);
    renderStats(stats);
    updateMockBadge(stats);
    renderGauge(riskScore.overall, riskScore.level);
    renderModuleBar("module-a", riskScore.module_a.score, riskScore.module_a.threat_count);
    renderModuleBar("module-b", riskScore.module_b.score, riskScore.module_b.threat_count);
    renderModuleBar("module-c", riskScore.module_c.score, riskScore.module_c.threat_count);
    renderAlerts(alerts);
    await loadThreats();
    document.getElementById("last-updated").textContent = new Date().toLocaleTimeString("ko-KR");
    await initTrendChart();
    await renderPlatformStats();
    startPolling();
  } catch (e) { console.error("Dashboard init failed:", e); }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
  document.querySelectorAll(".filter-btn").forEach(b => b.addEventListener("click", () => setFilter(b.dataset.severity)));
  document.querySelectorAll(".status-filter-btn").forEach(b => b.addEventListener("click", () => setStatusFilter(b.dataset.status)));
  document.getElementById("btn-prev").addEventListener("click", () => { if (state.page > 1) { state.page--; loadThreats(); } });
  document.getElementById("btn-next").addEventListener("click", () => { const tp = Math.ceil(state.total / state.pageSize); if (state.page < tp) { state.page++; loadThreats(); } });
  document.addEventListener('themechange', applyChartTheme);
  document.getElementById("btn-close-panel").addEventListener("click", closePanel);
  document.getElementById("panel-backdrop").addEventListener("click", closePanel);
  document.getElementById("status-active").addEventListener("click", () => handleStatusChange("active"));
  document.getElementById("status-reviewing").addEventListener("click", () => handleStatusChange("reviewing"));
  document.getElementById("status-resolved").addEventListener("click", () => handleStatusChange("resolved"));
  const scanBtn = document.getElementById("btn-scan");
  if (scanBtn) scanBtn.addEventListener("click", runScan);
});
