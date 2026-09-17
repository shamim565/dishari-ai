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

    startSession() {
      if (!this.canSession) {
        this.startListening(false);
        return;
      }
      chatVlog("session start");
      this.sessionToken++;
      this.sessionActive = true;
      this.paused = false;
      this.silentStrikes = 0;
      this.voiceMessage = "";
      const token = ++this.speakToken;
      const greeting = this.labels.sessionGreeting || "";
      const begin = () => {
        if (token !== this.speakToken) return;
        if (!this.sessionActive) return;
        this.startListening(true);
      };
      if (greeting && typeof VoiceIO !== "undefined") {
        this.phase = "speaking";
        VoiceIO.speak(greeting, this.config.lang, this.config.ttsUrl, this.config.csrf, begin);
      } else {
        begin();
      }
    },

    endSession() {
      chatVlog("session end");
      this.sessionToken++;
      this.sessionActive = false;
      this.paused = false;
      this.silentStrikes = 0;
      this.clearTimers();
      this.speakToken++;
      if (typeof VoiceIO !== "undefined") VoiceIO.cancelSpeaking();
      if (this.recognition && this.recognition.stop) {
        try {
          this.recognition.stop();
        } catch (e) {}
      }
      this.recognition = null;
      this.phase = "idle";
    },

    pauseSession(message) {
      chatVlog("session pause");
      this.sessionToken++;
      this.sessionActive = false;
      this.paused = true;
      this.silentStrikes = 0;
      this.clearTimers();
      this.speakToken++;
      if (typeof VoiceIO !== "undefined") VoiceIO.cancelSpeaking();
      this.recognition = null;
      this.phase = "idle";
      this.voiceMessage = message || this.labels.pauseHint || "";
    },

    clearTimers() {
      if (this.retryTimer) {
        clearTimeout(this.retryTimer);
        this.retryTimer = null;
      }
      if (this.silenceTimer) {
        clearTimeout(this.silenceTimer);
        this.silenceTimer = null;
      }
    },

    scheduleNextListen() {
      this.clearTimers();
      const token = this.sessionToken;
      const self = this;
      this.retryTimer = setTimeout(() => {
        self.retryTimer = null;
        if (self.sessionActive && token === self.sessionToken && self.phase === "idle") {
          self.startListening(true);
        }
      }, 500);
    },

    startListening(fromSession) {
      if (!this.voiceInSupported || typeof VoiceIO === "undefined") return;
      this.clearTimers();
      this.voiceMessage = "";
      this.phase = "listening";
      chatVlog("listening start", "session=" + this.sessionActive, "fromSession=" + fromSession);
      const self = this;
      const token = this.sessionToken;
      let finished = false;
      let listenWatchdog = null;
      const clearListenWatchdog = () => {
        if (listenWatchdog) {
          clearTimeout(listenWatchdog);
          listenWatchdog = null;
        }
      };

      const armSilenceTimer = () => {
        if (self.silenceTimer) clearTimeout(self.silenceTimer);
        self.silenceTimer = setTimeout(() => {
          self.silenceTimer = null;
          if (self.sessionActive) self.pauseSession(self.labels.paused || "");
        }, 120000);
      };
      if (this.sessionActive) armSilenceTimer();

      const onEmptyTurn = () => {
        if (!self.sessionActive) return;
        self.silentStrikes++;
        chatVlog("empty turn", "strikes=" + self.silentStrikes);
        if (self.silentStrikes >= 3) {
          self.pauseSession(self.labels.paused || "");
          return;
        }
        self.voiceMessage = self.labels.noSpeech || "";
        self.retryTimer = setTimeout(() => {
          self.retryTimer = null;
          if (self.sessionActive && token === self.sessionToken) self.startListening(true);
        }, 1200);
      };

      const finalize = (text) => {
        if (finished) return;
        finished = true;
        clearListenWatchdog();
        if (token !== self.sessionToken) return;
        if (self.phase !== "listening") return;
        const transcript = (text || "").trim();
        if (transcript) {
          chatVlog("transcript", transcript);
          self.silentStrikes = 0;
          self.voiceMessage = "";
          if (self.silenceTimer) {
            clearTimeout(self.silenceTimer);
            self.silenceTimer = null;
          }
          self.send(transcript);
        } else if (self.sessionActive) {
          onEmptyTurn();
        } else {
          self.phase = "idle";
        }
      };

      const fail = (code) => {
        if (finished) return;
        finished = true;
        clearListenWatchdog();
        if (token !== self.sessionToken) return;
        chatVlog("listen error:", code);
        if (code === "no-speech" || code === "aborted") {
          if (self.phase === "listening") self.phase = "idle";
          if (self.sessionActive) onEmptyTurn();
          return;
        }
        if (code === "not-allowed" || code === "service-not-allowed" || code === "audio-capture") {
          self.voiceMessage = self.labels.errorHeard || "";
          if (self.sessionActive) self.pauseSession(self.labels.errorHeard || "");
          else self.phase = "idle";
          return;
        }
        if (code === "language-not-supported") {
          const msg = self.labels.langUnsupported || self.labels.errorHeard || "";
          self.voiceMessage = msg;
          if (self.sessionActive) self.pauseSession(msg);
          else self.phase = "idle";
          return;
        }
        if (self.phase === "listening") self.phase = "idle";
        if (self.sessionActive) onEmptyTurn();
      };

      this.recognition = VoiceIO.listen(
        this.config.sttLang,
        (text, isFinal) => {
          if (token !== self.sessionToken) return;
          clearListenWatchdog();
          if (isFinal) finalize(text);
        },
        () => {
          if (!finished) finalize("");
        },
        (code) => fail(code),
        this.config.sttUrl,
        this.config.csrf
      );
      if (!this.recognition) {
        finalize("");
        return;
      }
      if (this.browserStt) {
        listenWatchdog = setTimeout(() => {
          listenWatchdog = null;
          if (finished) return;
          chatVlog("listen watchdog fired");
          try {
            if (self.recognition && self.recognition.stop) self.recognition.stop();
          } catch (e) {}
          fail("no-events");
        }, 9000);
      }
    },

    cancelSpeech() {
      this.speakToken++;
      if (typeof VoiceIO !== "undefined") VoiceIO.cancelSpeaking();
      this.phase = "idle";
    },

    speakFiller() {
      const filler = this.labels.filler;
      if (!filler || typeof VoiceIO === "undefined") return;
      VoiceIO.speak(filler, this.config.lang, this.config.ttsUrl, this.config.csrf);
    },

    replayLast() {
      if (this.lastSpoken) this.speakText(this.lastSpoken, false);
    },

    speakText(text, chainAfter) {
      if (typeof VoiceIO === "undefined" || !text) {
        this.phase = "idle";
        return;
      }
      this.phase = "speaking";
      const token = ++this.speakToken;
      const sessToken = this.sessionToken;
      VoiceIO.speak(text, this.config.lang, this.config.ttsUrl, this.config.csrf, () => {
        if (token !== this.speakToken) return;
        this.lastSpoken = text;
        this.phase = "idle";
        if (chainAfter && this.sessionActive && this.canSession && !this.paused && sessToken === this.sessionToken) {
          this.scheduleNextListen();
        }
      });
    },

    async send(message) {
      const text = (message || "").trim();
      if (!text || this.sending) return;
      this.sending = true;
      this.voiceMessage = "";
      this.clearTimers();
      this.phase = "thinking";
      this.speakFiller();
      let reply = "";

      try {
        const body = new URLSearchParams({ message: text });
        const response = await fetch(this.config.sendUrl, {
          method: "POST",
          headers: {
            "X-CSRFToken": this.config.csrf,
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: body,
        });
        if (!response.ok || !response.body) throw new Error("bad_response");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop();
          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            let payload;
            try {
              payload = JSON.parse(part.slice(6));
            } catch (e) {
              continue;
            }
            if (payload.delta) reply += payload.delta;
            if (payload.done) chatVlog("reply complete", reply.length, "chars");
          }
        }
      } catch (e) {
        chatVlog("send failed", String(e));
        if (!reply) reply = this.config.errorText || "";
      }
      this.sending = false;
      this.speakText(reply.trim(), true);
    },
  };
}
