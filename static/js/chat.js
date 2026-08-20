function chatVlog() {
  const enabled =
    window.__VOICE_DEBUG__ === true ||
    (function () {
      try {
        return localStorage.getItem("voiceDebug") === "1";
      } catch (e) {
        return false;
      }
    })();
  if (enabled) console.log("[chat]", ...arguments);
}

function chatApp() {
  return {
    phase: "idle",
    voiceInSupported: false,
    voiceReason: "",
    voiceMessage: "",
    browserStt: false,
    sessionActive: false,
    paused: false,
    sending: false,
    lastSpoken: "",
    config: {},
    recognition: null,
    speakToken: 0,
    sessionToken: 0,
    retryTimer: null,
    silenceTimer: null,
    silentStrikes: 0,

    get labels() {
      return this.config.labels || {};
    },

    get listening() {
      return this.phase === "listening";
    },

    get canSession() {
      return this.voiceInSupported && this.browserStt;
    },

    get showReplay() {
      return !!(this.lastSpoken && this.phase === "idle");
    },

    get phaseCaption() {
      if (this.phase === "listening") return this.labels.listening || "";
      if (this.phase === "thinking") return this.labels.thinking || "";
      if (this.phase === "speaking") {
        return (this.labels.speaking || "") + " · " + (this.labels.stopHint || "");
      }
      if (this.sessionActive) return this.labels.listening || "";
      if (this.paused) return this.labels.pauseHint || "";
      if (this.canSession) return this.labels.start || "";
      return this.labels.tapToSpeak || "";
    },

    get voiceHint() {
      if (this.voiceInSupported) return "";
      if (this.voiceReason === "https") return this.config.voiceHttpsMsg || "";
      return this.config.voiceSetupMsg || "";
    },

    init() {
      const node = document.getElementById("chat-config");
      try {
        this.config = node ? JSON.parse(node.textContent) : {};
      } catch (e) {
        this.config = {};
      }
      if (this.config.fallbackNotice) this.voiceMessage = this.config.fallbackNotice;
      this.setupVoice();
    },

    setupVoice() {
      const browserSupports = () => typeof VoiceIO !== "undefined" && VoiceIO.sttSupported();
      const checkStatus = () => {
        fetch("/api/voice/status/")
          .then((response) => response.json())
          .then((payload) => {
            if (payload && payload.available) {
              this.voiceInSupported = true;
              this.voiceReason = "";
              this.prefetchGreeting();
            } else {
              this.voiceReason = window.isSecureContext ? "setup" : "https";
            }
          })
          .catch(() => {
            this.voiceReason = "setup";
          });
      };
      if (browserSupports()) {
        this.browserStt = true;
        this.voiceInSupported = true;
        this.prefetchGreeting();
        return;
      }
      if (typeof VoiceIO === "undefined") {
        window.addEventListener("load", () => {
          if (browserSupports()) {
            this.browserStt = true;
            this.voiceInSupported = true;
            this.prefetchGreeting();
          } else {
            checkStatus();
          }
        });
        checkStatus();
        return;
      }
      checkStatus();
    },

    prefetchGreeting() {
      if (typeof VoiceIO === "undefined" || !VoiceIO.prefetch) return;
      const greeting = this.labels.sessionGreeting;
      if (greeting) {
        VoiceIO.prefetch(greeting, this.config.lang, this.config.ttsUrl, this.config.csrf);
      }
      const filler = this.labels.filler;
      if (filler) {
        VoiceIO.prefetch(filler, this.config.lang, this.config.ttsUrl, this.config.csrf);
      }
    },

    micTap() {
      if (this.phase === "thinking") return;
      if (this.phase === "speaking") {
        if (this.sessionActive) {
          this.cancelSpeech();
          this.startListening(true);
        }
        return;
      }
      if (this.phase === "listening") return;
      if (this.canSession) {
        if (!this.sessionActive) this.startSession();
        return;
      }
      this.startListening(false);
    },
