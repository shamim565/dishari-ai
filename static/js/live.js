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

    handleServerMessage(msg) {
      if (msg.setupComplete) {
        this._ready = true;
        this.maybeStartListening();
        return;
      }
      const sc = msg.serverContent;
      if (!sc) return;
      if (sc.interrupted) {
        this.flushPlayback();
        if (this.sessionActive) this.phase = "listening";
      }
      if (sc.inputTranscription && sc.inputTranscription.text) {
        this._turnInput += sc.inputTranscription.text;
      }
      if (sc.outputTranscription && sc.outputTranscription.text) {
        this._turnOutput += sc.outputTranscription.text;
        if (this.sessionActive && this.phase !== "speaking") this.phase = "speaking";
      }
      if (sc.modelTurn && sc.modelTurn.parts) {
        for (const part of sc.modelTurn.parts) {
          if (part.inlineData && part.inlineData.data) {
            this.playPcmChunk(part.inlineData.data);
            if (this.sessionActive && this.phase !== "speaking") this.phase = "speaking";
          }
        }
      }
      if (sc.turnComplete) {
        this.logTurn();
        if (this.sessionActive) this.phase = "listening";
      }
    },

    logTurn() {
      const input = this._turnInput.trim();
      const output = this._turnOutput.trim();
      this._turnInput = "";
      this._turnOutput = "";
      if (!input && !output) return;
      const self = this;
      try {
        fetch(this.config.logUrl, {
          method: "POST",
          headers: {
            "X-CSRFToken": this.config.csrf,
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: new URLSearchParams({ input: input, output: output }),
        })
          .then(function (r) {
            return r.ok ? r.json() : null;
          })
          .then(function (payload) {
            if (payload && payload.event && payload.event.emergency) {
              self.voiceMessage = payload.event.emergency.text || "";
            }
          })
          .catch(function () {});
      } catch (e) {}
    },

    async startMic() {
      const self = this;
      this._micStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      this._micCtx = new (window.AudioContext || window.webkitAudioContext)();
      this._micSource = this._micCtx.createMediaStreamSource(this._micStream);
      this._processor = this._micCtx.createScriptProcessor(4096, 1, 1);
      const mute = this._micCtx.createGain();
      mute.gain.value = 0;
      this._processor.onaudioprocess = function (e) {
        if (!self._ready || !self._micOn || !self._ws || self._ws.readyState !== WebSocket.OPEN) return;
        const input = e.inputBuffer.getChannelData(0);
        const pcm = self._floatToPcm16(self._resampleTo16k(input, self._micCtx.sampleRate));
        self._ws.send(
          JSON.stringify({
            realtimeInput: {
              audio: { data: self._b64FromBytes(pcm), mimeType: "audio/pcm;rate=16000" },
            },
          })
        );
      };
      this._micSource.connect(this._processor);
      this._processor.connect(mute);
      mute.connect(this._micCtx.destination);
      if (this._micCtx.state === "suspended") this._micCtx.resume();
    },

    stopMic() {
      if (this._processor) {
        this._processor.disconnect();
        this._processor.onaudioprocess = null;
        this._processor = null;
      }
      if (this._micSource) {
        this._micSource.disconnect();
        this._micSource = null;
      }
      if (this._micStream) {
        this._micStream.getTracks().forEach(function (t) {
          t.stop();
        });
        this._micStream = null;
      }
      if (this._micCtx) {
        this._micCtx.close();
        this._micCtx = null;
      }
    },

    playPcmChunk(b64) {
      if (!this._outCtx) this._outCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (this._outCtx.state === "suspended") this._outCtx.resume();
      const raw = atob(b64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      const samples = new Int16Array(bytes.buffer);
      const buf = this._outCtx.createBuffer(1, samples.length, 24000);
      const ch = buf.getChannelData(0);
      for (let i = 0; i < samples.length; i++) ch[i] = samples[i] / 32768;
      const src = this._outCtx.createBufferSource();
      src.buffer = buf;
      src.connect(this._outCtx.destination);
      const t = Math.max(this._outCtx.currentTime + 0.02, this._nextTime);
      src.start(t);
      this._nextTime = t + buf.duration;
      this._scheduled.push(src);
      const self = this;
      src.onended = function () {
        self._scheduled = self._scheduled.filter(function (s) {
          return s !== src;
        });
      };
    },

    flushPlayback() {
      this._scheduled.forEach(function (s) {
        try {
          s.stop();
        } catch (e) {}
      });
      this._scheduled = [];
      this._nextTime = 0;
    },

    _b64FromBytes(bytes) {
      let binary = "";
      const step = 0x8000;
      for (let i = 0; i < bytes.length; i += step) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
      }
      return btoa(binary);
    },

    _floatToPcm16(input) {
      const out = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      return new Uint8Array(out.buffer);
    },

    _resampleTo16k(input, inRate) {
      if (inRate === 16000) return input;
      const ratio = inRate / 16000;
      const outLen = Math.floor(input.length / ratio);
      const out = new Float32Array(outLen);
      for (let i = 0; i < outLen; i++) {
        const pos = i * ratio;
        const idx = Math.floor(pos);
        const frac = pos - idx;
        const a = input[idx] || 0;
        const b = input[idx + 1] || a;
        out[i] = a + (b - a) * frac;
      }
      return out;
    },
  };
}
