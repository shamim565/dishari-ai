function liveApp() {
  return {
    phase: "idle",
    voiceMessage: "",
    sessionActive: false,
    config: {},
    labels: {},

    _ws: null,
    _connecting: false,
    _micCtx: null,
    _micStream: null,
    _processor: null,
    _micSource: null,
    _outCtx: null,
    _nextTime: 0,
    _scheduled: [],
    _turnInput: "",
    _turnOutput: "",
    _ready: false,
    _micOn: false,
    _ctxHash: "",

    get voiceHint() {
      return "";
    },

    get showReplay() {
      return false;
    },

    get phaseCaption() {
      if (this.phase === "speaking") {
        return (this.labels.speaking || "") + " · " + (this.labels.stopHint || "");
      }
      if (this.phase === "listening") return this.labels.listening || "";
      if (this.phase === "connecting") return this.labels.connecting || "";
      if (this.sessionActive) return this.labels.listening || "";
      return this.labels.tapToSpeak || "";
    },

    init() {
      const node = document.getElementById("live-config");
      try {
        this.config = node ? JSON.parse(node.textContent) : {};
      } catch (e) {
        this.config = {};
      }
      this.labels = this.config.labels || {};
      const self = this;
      window.addEventListener("message", function (event) {
        if (event.origin !== window.location.origin) return;
        const data = event.data || {};
        if (data.type === "dishari:context-check") self.refreshContext();
      });
    },

    micTap() {
      if (this._connecting || this.sessionActive || this.phase === "connecting") return;
      this.startSession();
    },

    endSession() {
      this.logTurn();
      this.sessionActive = false;
      this.phase = "idle";
      this._ready = false;
      this._micOn = false;
      this.flushPlayback();
      this.stopMic();
      const ws = this._ws;
      this._ws = null;
      if (ws) {
        try {
          ws.close();
        } catch (e) {}
      }
    },

    replayLast() {},

    async startSession() {
      this._connecting = true;
      this.voiceMessage = "";
      this.phase = "connecting";
      this._ready = false;
      this._micOn = false;

      let data;
      try {
        const response = await fetch(this.config.tokenUrl, {
          method: "POST",
          headers: { "X-CSRFToken": this.config.csrf },
        });
        if (!response.ok) throw new Error("token_http_" + response.status);
        data = await response.json();
      } catch (e) {
        this._connecting = false;
        this.fallbackToPipeline();
        return;
      }
      this._connecting = false;
      this._ctxHash = data.ctx_hash || "none";

      if (!this._outCtx) {
        this._outCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this._outCtx.state === "suspended") this._outCtx.resume();

      const ws = new WebSocket(data.ws_url + "?access_token=" + encodeURIComponent(data.token));
      this._ws = ws;
      const self = this;
      let opened = false;

      ws.onopen = function () {
        opened = true;
        const setup = Object.assign({ model: "models/" + data.model }, data.config);
        ws.send(JSON.stringify({ setup: setup }));
        self.startMic().then(
          function () {
            self._micOn = true;
            self.sessionActive = true;
            self.maybeStartListening();
          },
          function () {
            self.voiceMessage = self.labels.micError || "";
            self.phase = "idle";
          }
        );
      };

      ws.onmessage = async function (event) {
        let text;
        if (typeof event.data === "string") text = event.data;
        else if (event.data instanceof Blob) text = await event.data.text();
        else if (event.data instanceof ArrayBuffer) text = new TextDecoder().decode(event.data);
        else return;
        try {
          self.handleServerMessage(JSON.parse(text));
        } catch (e) {}
      };

      ws.onerror = function () {};

      ws.onclose = function () {
        if (ws !== self._ws) return;
        self._ws = null;
        self.sessionActive = false;
        self._ready = false;
        self._micOn = false;
        self.flushPlayback();
        self.stopMic();
        self.logTurn();
        self.phase = "idle";
        if (!opened) {
          self.fallbackToPipeline();
        } else {
          self.voiceMessage = self.labels.connLost || "";
        }
      };
    },

    fallbackToPipeline() {
      this.voiceMessage = this.labels.fallback || "";
      const url = this.config.fallbackUrl || "?voice=tts&fallback=1";
      setTimeout(function () {
        window.location.replace(url);
      }, 900);
    },

    maybeStartListening() {
      if (this._ready && this._micOn && this.phase !== "speaking") {
        this.phase = "listening";
      }
    },

    async refreshContext() {
      if (!this._ready || !this._micOn || !this._ws || this._ws.readyState !== WebSocket.OPEN) return;
      let data;
      try {
        const response = await fetch(this.config.contextUrl);
        if (!response.ok) return;
        data = await response.json();
      } catch (e) {
        return;
      }
      if (!data.context || data.hash === this._ctxHash) return;
      this._ctxHash = data.hash;
      this._ws.send(
        JSON.stringify({
          clientContent: {
            turns: [
              {
                role: "user",
                parts: [
                  {
                    text:
                      "[সিস্টেম: অপারেশনাল ডেটা আপডেট — উত্তর দেবেন না]\n" + data.context,
                  },
                ],
              },
            ],
            turnComplete: false,
          },
        })
      );
    },
