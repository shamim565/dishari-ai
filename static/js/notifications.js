(function () {
  const config = window.NOTIFY_CONFIG;
  if (!config || !config.pollUrl) return;

  const POLL_MS = 10000;
  let lastId = null;
  let toastWrap = null;

  function notifyEnabled() {
    return localStorage.getItem("notifyEnabled") !== "0";
  }

  function ensureWrap() {
    if (!toastWrap) {
      toastWrap = document.createElement("div");
      toastWrap.className = "toast-wrap";
      document.body.appendChild(toastWrap);
    }
    return toastWrap;
  }

  function showToast(event) {
    const wrap = ensureWrap();
    const urgent = event.priority === "urgent";
    const toast = document.createElement("div");
    toast.className = "toast" + (urgent ? " toast-urgent" : "");

    const icon = document.createElement("div");
    icon.className = "toast-icon";
    icon.textContent = urgent ? "!" : "\u25CF";

    const body = document.createElement("div");
    body.className = "min-w-0 flex-1";

    const title = document.createElement("p");
    title.className = "toast-title";
    title.textContent = urgent ? config.strings.urgent : "\u0996\u09AC\u09B0";

    const message = document.createElement("p");
    message.className = "toast-msg";
    message.textContent = event.message;

    const actions = document.createElement("div");
    actions.className = "toast-actions";

    const refresh = document.createElement("button");
    refresh.type = "button";
    refresh.className = "toast-btn";
    refresh.textContent = config.strings.refresh;
    refresh.addEventListener("click", () => window.location.reload());

    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.className = "toast-btn";
    dismiss.textContent = "\u2715";
    dismiss.addEventListener("click", () => toast.remove());

    actions.appendChild(refresh);
    actions.appendChild(dismiss);
    body.appendChild(title);
    body.appendChild(message);
    body.appendChild(actions);
    toast.appendChild(icon);
    toast.appendChild(body);
    wrap.appendChild(toast);

    setTimeout(() => toast.remove(), urgent ? 20000 : 10000);
  }

  function handleEvent(event) {
    showToast(event);
    if (event.speak && (notifyEnabled() || event.priority === "urgent")) {
      if (typeof VoiceIO !== "undefined") {
        VoiceIO.speak(event.message, config.lang, config.ttsUrl, config.csrf);
      }
    }
    window.dispatchEvent(new Event("dishari:notify"));
  }
