// 모바일 사이드바 드로어 컨트롤러
(function () {
  function getSidebar() { return document.getElementById('db-sidebar'); }
  function getOverlay()  { return document.getElementById('db-overlay'); }

  window.toggleSidebar = function () {
    var s = getSidebar(), o = getOverlay();
    if (!s || !o) return;
    var isOpen = s.classList.contains('open');
    if (isOpen) { closeSidebar(); } else { openSidebar(); }
  };

  window.openSidebar = function () {
    var s = getSidebar(), o = getOverlay();
    if (!s || !o) return;
    s.classList.add('open');
    o.classList.add('open');
    document.body.style.overflow = 'hidden';
  };

  window.closeSidebar = function () {
    var s = getSidebar(), o = getOverlay();
    if (!s || !o) return;
    s.classList.remove('open');
    o.classList.remove('open');
    document.body.style.overflow = '';
  };

  // 사이드바 링크 클릭 시 닫기 (모바일)
  document.addEventListener('DOMContentLoaded', function () {
    var sidebar = getSidebar();
    if (!sidebar) return;
    sidebar.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth <= 768) closeSidebar();
      });
    });
  });

  // ESC 키로 닫기
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeSidebar();
  });
})();
