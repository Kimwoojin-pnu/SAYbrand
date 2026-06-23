/**
 * SAYbrand 모바일 + PC 통합 테스트
 * - iPhone 12 (390x844) — 모바일 뷰포트
 * - Desktop (1280x800) — PC 뷰포트
 */
import { chromium, devices } from '@playwright/test';
import { mkdirSync } from 'fs';

const BASE = 'http://localhost:8001';
const SHOTS_DIR = './test_screenshots';
try { mkdirSync(SHOTS_DIR, { recursive: true }); } catch(e) {}

const results = [];
function log(test, pass, detail = '') {
  const status = pass ? '✅ PASS' : '❌ FAIL';
  results.push({ test, pass, detail });
  console.log(`${status} | ${test}${detail ? ' — ' + detail : ''}`);
}

async function demoLogin(page) {
  await page.goto(BASE + '/login');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  const demoVisible = await page.evaluate(() => {
    const el = document.getElementById('demo-section');
    return el && !el.classList.contains('hidden');
  });
  if (demoVisible) {
    await page.click('a[href="/auth/demo-login"]', { force: true });
    await page.waitForLoadState('networkidle');
  } else {
    await page.goto(BASE + '/auth/demo-login');
    await page.waitForLoadState('networkidle');
  }
  return page.url().includes('/dashboard') || page.url().includes('/threats') || page.url().includes('/onboarding');
}

// ══════════════════════════════════════════════════════════════════
// 1. 모바일 테스트 (iPhone 12 — 390×844)
// ══════════════════════════════════════════════════════════════════
console.log('\n📱 모바일 테스트 (390×844 — iPhone 12)\n' + '─'.repeat(55));
const browser = await chromium.launch({ headless: true });
const mobileCtx = await browser.newContext({ ...devices['iPhone 12'], locale: 'ko-KR' });
const mp = await mobileCtx.newPage();

// ── 랜딩 ──────────────────────────────────────────────────────────
await mp.goto(BASE + '/');
await mp.waitForLoadState('networkidle');
await mp.screenshot({ path: `${SHOTS_DIR}/m01_landing.png` });
log('[모바일] 랜딩: 햄버거 버튼 표시', await mp.locator('.ld-nav-hamburger').isVisible());
log('[모바일] 랜딩: 데스크탑 링크 숨김', !(await mp.locator('.ld-nav-links').isVisible()));
await mp.click('#hamburger', { force: true });
await mp.waitForTimeout(300);
log('[모바일] 랜딩: 모바일 메뉴 열림', await mp.locator('#mobile-menu').isVisible());
await mp.click('#hamburger', { force: true });
await mp.waitForTimeout(200);

// ── 로그인 ────────────────────────────────────────────────────────
await mp.goto(BASE + '/login');
await mp.waitForLoadState('networkidle');
await mp.screenshot({ path: `${SHOTS_DIR}/m02_login.png` });
log('[모바일] 로그인: 카드 표시 (max-w-sm)', await mp.locator('.w-full.max-w-sm').isVisible());

// ── 데모 로그인 ───────────────────────────────────────────────────
const mobileLoggedIn = await demoLogin(mp);
log('[모바일] 데모 로그인 성공', mobileLoggedIn);

await mp.goto(BASE + '/threats');
await mp.waitForLoadState('networkidle');
await mp.screenshot({ path: `${SHOTS_DIR}/m03_threats.png` });

const mobileTopbarVisible = await mp.locator('#db-mobile-topbar').isVisible();
log('[모바일] 대시보드: 모바일 상단 바 표시', mobileTopbarVisible);

const mobileSidebarHidden = await mp.evaluate(() => {
  const s = document.getElementById('db-sidebar');
  if (!s) return true;
  const rect = s.getBoundingClientRect();
  return rect.right <= 0;
});
log('[모바일] 사이드바: 기본값 숨김 (화면 밖)', mobileSidebarHidden);

// 햄버거 → 사이드바 열림
await mp.click('#db-mobile-topbar .db-hamburger', { force: true });
await mp.waitForTimeout(350);
const mobileSidebarOpen = await mp.evaluate(() => {
  const s = document.getElementById('db-sidebar');
  return s ? s.classList.contains('open') : false;
});
log('[모바일] 사이드바: 햄버거 클릭 → 열림', mobileSidebarOpen);
const mobileOverlayOpen = await mp.evaluate(() => {
  const o = document.getElementById('db-overlay');
  return o ? o.classList.contains('open') : false;
});
log('[모바일] 사이드바: 오버레이 표시', mobileOverlayOpen);
await mp.screenshot({ path: `${SHOTS_DIR}/m04_sidebar_open.png` });

// 오버레이 클릭 → 닫힘
await mp.click('#db-overlay', { force: true });
await mp.waitForTimeout(350);
const mobileSidebarClosed = await mp.evaluate(() => {
  const s = document.getElementById('db-sidebar');
  return s ? !s.classList.contains('open') : true;
});
log('[모바일] 사이드바: 오버레이 클릭 → 닫힘', mobileSidebarClosed);

// ESC 키 → 닫힘
await mp.click('#db-mobile-topbar .db-hamburger', { force: true });
await mp.waitForTimeout(300);
await mp.keyboard.press('Escape');
await mp.waitForTimeout(300);
const mobileEscClosed = await mp.evaluate(() => {
  const s = document.getElementById('db-sidebar');
  return s ? !s.classList.contains('open') : true;
});
log('[모바일] 사이드바: ESC 키 → 닫힘', mobileEscClosed);

// KPI 2열
await mp.goto(BASE + '/dashboard');
await mp.waitForLoadState('networkidle');
const mobileKpi = await mp.evaluate(() => {
  const el = document.querySelector('.db-kpi-grid');
  if (!el) return null;
  return window.getComputedStyle(el).gridTemplateColumns;
});
log('[모바일] 대시보드: KPI 2열 배치', mobileKpi !== null && mobileKpi.split(' ').length === 2, mobileKpi || 'not found');

// 테이블 가로 스크롤
await mp.goto(BASE + '/threats');
await mp.waitForLoadState('networkidle');
const mobileTableScroll = await mp.evaluate(() => {
  const t = document.querySelector('.db-table-scroll');
  return t ? window.getComputedStyle(t).overflowX : 'not found';
});
log('[모바일] 위협 테이블: 가로 스크롤 (overflow-x:auto)', mobileTableScroll === 'auto', mobileTableScroll);

// mobile-nav.js 함수 로드
const mobileNavFns = await mp.evaluate(() => ({
  toggle: typeof window.toggleSidebar === 'function',
  open: typeof window.openSidebar === 'function',
  close: typeof window.closeSidebar === 'function',
}));
log('[모바일] mobile-nav.js: 3개 함수 로드', mobileNavFns.toggle && mobileNavFns.open && mobileNavFns.close);

// 각 페이지 HTML 구조 확인
const mobilePages = [
  ['/dashboard', 'db-mobile-topbar', 'db-kpi-grid'],
  ['/threats', 'db-mobile-topbar', 'db-table-scroll', 'db-filters'],
  ['/settings', 'db-mobile-topbar', 'db-tab-nav'],
  ['/brand-image', 'db-mobile-topbar', 'db-two-col-grid'],
  ['/reports', 'db-mobile-topbar', 'db-sidebar'],
  ['/support', 'db-mobile-topbar', 'db-sidebar'],
  ['/actions', 'db-mobile-topbar', 'db-sidebar'],
  ['/negative-mentions', 'db-mobile-topbar', 'db-sidebar'],
  ['/history', 'db-mobile-topbar', 'db-table-scroll'],
];
for (const [path, ...checks] of mobilePages) {
  const res = await mp.evaluate(async (url) => {
    const r = await fetch(url, { redirect: 'follow' });
    return { status: r.status, html: await r.text() };
  }, BASE + path);
  for (const cls of checks) {
    log(`[모바일] ${path}: .${cls} HTML에 존재`, res.html.includes(cls), `HTTP ${res.status}`);
  }
}

await mobileCtx.close();

// ══════════════════════════════════════════════════════════════════
// 2. PC 테스트 (1280×800 — 데스크탑)
// ══════════════════════════════════════════════════════════════════
console.log('\n🖥  PC 테스트 (1280×800 — Desktop)\n' + '─'.repeat(55));
const desktopCtx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  locale: 'ko-KR',
});
const dp = await desktopCtx.newPage();

// ── 랜딩 ──────────────────────────────────────────────────────────
await dp.goto(BASE + '/');
await dp.waitForLoadState('networkidle');
await dp.screenshot({ path: `${SHOTS_DIR}/d01_landing.png` });
const desktopHamburgerHidden = !(await dp.locator('.ld-nav-hamburger').isVisible());
log('[PC] 랜딩: 햄버거 버튼 숨김 (데스크탑)', desktopHamburgerHidden);
const desktopNavLinksVisible = await dp.locator('.ld-nav-links').isVisible();
log('[PC] 랜딩: 데스크탑 내비 링크 표시', desktopNavLinksVisible);

// ── 로그인 ────────────────────────────────────────────────────────
await dp.goto(BASE + '/login');
await dp.waitForLoadState('networkidle');
await dp.screenshot({ path: `${SHOTS_DIR}/d02_login.png` });
log('[PC] 로그인: 카드 표시', await dp.locator('.w-full.max-w-sm').isVisible());

// ── 데모 로그인 ───────────────────────────────────────────────────
const desktopLoggedIn = await demoLogin(dp);
log('[PC] 데모 로그인 성공', desktopLoggedIn);

await dp.goto(BASE + '/threats');
await dp.waitForLoadState('networkidle');
await dp.screenshot({ path: `${SHOTS_DIR}/d03_threats.png` });

// 모바일 상단 바는 PC에서 숨겨져야 함
const desktopTopbarHidden = await dp.evaluate(() => {
  const el = document.getElementById('db-mobile-topbar');
  if (!el) return true;
  return window.getComputedStyle(el).display === 'none';
});
log('[PC] 모바일 상단 바: 데스크탑에서 숨김 (display:none)', desktopTopbarHidden);

// 사이드바는 PC에서 보여야 함 (화면 안에)
const desktopSidebarVisible = await dp.evaluate(() => {
  const s = document.getElementById('db-sidebar');
  if (!s) return false;
  const rect = s.getBoundingClientRect();
  return rect.left >= 0 && rect.width > 0;
});
log('[PC] 사이드바: 데스크탑에서 기본 표시', desktopSidebarVisible);

// KPI 4열 — dashboard에서
await dp.goto(BASE + '/dashboard');
await dp.waitForLoadState('networkidle');
await dp.screenshot({ path: `${SHOTS_DIR}/d04_dashboard.png` });
const desktopKpi = await dp.evaluate(() => {
  const el = document.querySelector('.db-kpi-grid');
  if (!el) return null;
  return window.getComputedStyle(el).gridTemplateColumns;
});
const desktopKpiIs4Col = desktopKpi !== null && desktopKpi.split(' ').length === 4;
log('[PC] 대시보드: KPI 4열 배치', desktopKpiIs4Col, desktopKpi || 'not found');

// two-col-grid — 2열이어야 함
const desktopTwoCol = await dp.evaluate(() => {
  const el = document.querySelector('.db-two-col-grid');
  if (!el) return null;
  return window.getComputedStyle(el).gridTemplateColumns;
});
const desktopIs2Col = desktopTwoCol !== null && desktopTwoCol.split(' ').length === 2;
log('[PC] 대시보드: 2열 그리드 유지', desktopIs2Col, desktopTwoCol || 'not found');

// 각 페이지 로드 상태 확인
const desktopPageRoutes = [
  '/dashboard', '/threats', '/settings', '/brand-image',
  '/reports', '/support', '/actions', '/negative-mentions', '/history',
];
await dp.goto(BASE + '/threats');
await dp.waitForLoadState('networkidle');
for (const path of desktopPageRoutes) {
  const res = await dp.evaluate(async (url) => {
    const r = await fetch(url, { redirect: 'follow' });
    return { status: r.status, ok: r.ok };
  }, BASE + path);
  log(`[PC] ${path}: HTTP 200`, res.ok, `status=${res.status}`);
}

// 위협 테이블 정상 표시 (오버플로우 없이)
await dp.goto(BASE + '/threats');
await dp.waitForLoadState('networkidle');
await dp.screenshot({ path: `${SHOTS_DIR}/d05_threats.png` });
const desktopTableOk = await dp.evaluate(() => {
  const t = document.querySelector('.db-table-scroll');
  if (!t) return true; // 없으면 pass
  const style = window.getComputedStyle(t);
  // PC에서는 auto이거나 visible이어야 함 (hidden이 아니면 OK)
  return style.overflowX !== 'hidden';
});
log('[PC] 위협 테이블: 가로 오버플로우 정상 (hidden 아님)', desktopTableOk);

// CSS 파일 확인
const customCss = await dp.evaluate(async (url) => {
  const r = await fetch(url);
  return r.text();
}, BASE + '/assets/css/custom.css');
log('[PC/공통] CSS: 모바일 미디어 쿼리 존재', customCss.includes('max-width: 768px') || customCss.includes('max-width:768px'));
log('[PC/공통] CSS: 사이드바 드로어 애니메이션', customCss.includes('translateX'));

await desktopCtx.close();
await browser.close();

// ══════════════════════════════════════════════════════════════════
// 최종 결과
// ══════════════════════════════════════════════════════════════════
console.log('\n' + '='.repeat(60));
const passed = results.filter(r => r.pass).length;
const total = results.length;
const mobilePassed = results.filter(r => r.test.startsWith('[모바일]') && r.pass).length;
const mobileTotal = results.filter(r => r.test.startsWith('[모바일]')).length;
const pcPassed = results.filter(r => r.test.startsWith('[PC]') && r.pass).length;
const pcTotal = results.filter(r => r.test.startsWith('[PC]')).length;
const commonPassed = results.filter(r => r.test.startsWith('[PC/공통]') && r.pass).length;
const commonTotal = results.filter(r => r.test.startsWith('[PC/공통]')).length;

console.log(`모바일: ${mobilePassed}/${mobileTotal} 통과`);
console.log(`PC:     ${pcPassed}/${pcTotal} 통과`);
console.log(`공통:   ${commonPassed}/${commonTotal} 통과`);
console.log(`전체:   ${passed}/${total} 통과`);
if (passed === total) {
  console.log('\n✅ 전체 통과 — 모바일 + PC 모든 환경 정상 작동');
} else {
  console.log('\n❌ 실패 항목:');
  results.filter(r => !r.pass).forEach(r => console.log(`  - ${r.test}: ${r.detail}`));
}
process.exit(passed === total ? 0 : 1);
