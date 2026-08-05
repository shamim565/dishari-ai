(function () {
  "use strict";

  const cfg = window.KIOSK_CONFIG;
  if (!cfg || !cfg.active) return;

  const idleSeconds = Math.max(15, cfg.idleSeconds || 120);
  const warnSeconds = Math.min(15, idleSeconds - 1);
  const overlay = document.getElementById("kiosk-idle-overlay");
  const countEl = document.getElementById("kiosk-idle-count");
  const continueBtn = document.getElementById("kiosk-idle-continue");

  let lastActivity = Date.now();
  let warning = false;
  let ending = false;

  function endSession() {
    if (ending) return;
    ending = true;
    const go = function () {
      window.location.replace(cfg.homeUrl || "/");
    };
    try {
      fetch(cfg.endUrl, {
        method: "POST",
        headers: { "X-CSRFToken": cfg.csrf },
        keepalive: true,
      }).then(go).catch(go);
    } catch (e) {
      go();
    }
  }

  function showWarning(secondsLeft) {
    warning = true;
    if (overlay) overlay.hidden = false;
    if (countEl) countEl.textContent = String(secondsLeft);
  }

  function hideWarning() {
    warning = false;
    if (overlay) overlay.hidden = true;
  }

  function tick() {
    if (ending) return;
    if (document.querySelector("[data-kiosk-hold]")) {
      // A phone upload is in progress — keep the session alive.
      lastActivity = Date.now();
    }
    const elapsed = Math.floor((Date.now() - lastActivity) / 1000);
    const left = idleSeconds - elapsed;
    if (left <= 0) {
      endSession();
    } else if (left <= warnSeconds) {
      showWarning(left);
    } else if (warning) {
      hideWarning();
    }
  }
