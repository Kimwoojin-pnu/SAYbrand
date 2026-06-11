/* SAYbrand PWA — 서비스워커 등록 + 설치(Add to Home Screen) 버튼 제어 */
(function () {
  "use strict";

  // 서비스워커 등록 (루트 스코프)
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }

  var deferredPrompt = null;
  var isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  function getInstallButtons() {
    return document.querySelectorAll("[data-pwa-install]");
  }

  function showInstallButtons() {
    if (isStandalone) return;
    getInstallButtons().forEach(function (btn) {
      btn.style.display = "";
    });
  }

  function hideInstallButtons() {
    getInstallButtons().forEach(function (btn) {
      btn.style.display = "none";
    });
  }

  // 초기에는 숨김 (beforeinstallprompt 발생 시에만 노출)
  document.addEventListener("DOMContentLoaded", hideInstallButtons);

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showInstallButtons();
  });

  window.addEventListener("appinstalled", function () {
    deferredPrompt = null;
    hideInstallButtons();
  });

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-pwa-install]");
    if (!btn) return;
    e.preventDefault();
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.finally(function () {
      deferredPrompt = null;
      hideInstallButtons();
    });
  });
})();
