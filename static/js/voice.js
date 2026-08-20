const VoiceIO = (function () {
  const ttsCache = new Map();
  let currentAudio = null;
  let currentSource = null;
  let activeDone = null;

  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get("voicedebug") === "1") {
      window.__VOICE_DEBUG__ = true;
      localStorage.setItem("voiceDebug", "1");
    } else if (params.get("voicedebug") === "0") {
      window.__VOICE_DEBUG__ = false;
      localStorage.removeItem("voiceDebug");
    }
  } catch (e) {}

  function vlog() {
    const enabled =
      window.__VOICE_DEBUG__ === true ||
      (function () {
        try {
          return localStorage.getItem("voiceDebug") === "1";
        } catch (e) {
          return false;
        }
      })();
    if (enabled) console.log("[voice]", ...arguments);
  }

  function sttSupported() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  function stopSpeaking() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
    if (currentSource) {
      try {
        currentSource.stop();
      } catch (e) {}
      currentSource = null;
    }
    if (window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {}
    }
  }

  function cancelSpeaking() {
    stopSpeaking();
    const done = activeDone;
    activeDone = null;
    if (done) done();
  }

  function pickVoice(lang) {
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices();
    const preferences =
      lang === "bn"
        ? ["bn-bd", "bn-in", "bn", "en-us", "en"]
        : ["en-us", "en-gb", "en-in", "en"];
    for (const tag of preferences) {
      const found = voices.find((v) => (v.lang || "").replace("_", "-").toLowerCase().startsWith(tag));
      if (found) return found;
    }
    return null;
  }

  function speakLocal(text, lang, finish) {
    if (!window.speechSynthesis) {
      vlog("synthesis unavailable -> complete");
      finish();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = pickVoice(lang);
    if (voice) utterance.voice = voice;
    utterance.lang = voice ? voice.lang : lang === "bn" ? "bn-BD" : "en-US";
    utterance.rate = 0.95;

    let started = false;
    utterance.onstart = () => {
      started = true;
      vlog("synthesis started");
    };
    utterance.onend = finish;
    utterance.onerror = finish;

    let canceled = false;
    try {
      if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
        window.speechSynthesis.cancel();
        canceled = true;
      }
    } catch (e) {}

    setTimeout(
      () => {
        if (!started) {
          vlog("synthesis never started -> complete");
          try {
            window.speechSynthesis.cancel();
          } catch (e) {}
          finish();
        }
      },
      canceled ? 1600 : 1200
    );

    const doSpeak = () => {
      try {
        window.speechSynthesis.speak(utterance);
      } catch (e) {
        vlog("synthesis speak threw", String(e));
        finish();
      }
    };
    if (canceled) {
      setTimeout(doSpeak, 100);
    } else {
      doSpeak();
    }
  }

  async function fetchTtsBlob(text, lang, ttsUrl, csrf) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const body = new URLSearchParams({ text: text, lang: lang });
      const response = await fetch(ttsUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrf, "Content-Type": "application/x-www-form-urlencoded" },
        body: body,
        signal: controller.signal,
      });
      if (response.status === 200) {
        return await response.blob();
      }
      vlog("tts status", response.status);
      return null;
    } catch (e) {
      vlog("tts fetch failed", String(e));
      return null;
    } finally {
      clearTimeout(timer);
    }
  }

  async function prefetch(text, lang, ttsUrl, csrf) {
    if (!text || !ttsUrl) return;
    const key = lang + "|" + text;
    if (ttsCache.has(key)) return;
    const blob = await fetchTtsBlob(text, lang, ttsUrl, csrf);
    if (blob) {
      ttsCache.set(key, blob);
      vlog("prefetched", blob.size, "bytes");
    }
  }

  async function speak(text, lang, ttsUrl, csrf, onDone) {
    cancelSpeaking();
    activeDone = null;
    let finished = false;
    let watchdog = null;
    const finish = () => {
      if (finished) return;
      finished = true;
      if (watchdog) {
        clearTimeout(watchdog);
        watchdog = null;
      }
      if (activeDone === finish) activeDone = null;
      if (typeof onDone === "function") onDone();
    };
    activeDone = finish;

    if (!text) {
      finish();
      return;
    }

    const budget = Math.min(45000, 4000 + text.length * 110);
    watchdog = setTimeout(() => {
      vlog("watchdog fired after", budget, "ms");
      stopSpeaking();
      finish();
    }, budget);
    vlog("speak start", "lang=" + lang, "budget=" + budget);

    const key = lang + "|" + text;
    let blob = ttsCache.get(key);
    if (!blob && ttsUrl) {
      blob = await fetchTtsBlob(text, lang, ttsUrl, csrf);
      if (blob) {
        ttsCache.set(key, blob);
        vlog("tts blob", blob.size, "bytes");
      }
    }

    if (blob && activeDone === finish) {
      const audio = new Audio(URL.createObjectURL(blob));
      currentAudio = audio;
      audio.addEventListener("ended", () => {
        vlog("audio ended");
        finish();
      });
      audio.addEventListener("error", () => {
        vlog("audio error");
        finish();
      });
      try {
        await audio.play();
        vlog("audio playing");
        return;
      } catch (e) {
        vlog("audio.play rejected", String(e));
      }
    }
    if (activeDone === finish) {
      vlog("falling back to device synthesis");
      speakLocal(text, lang, finish);
    }
  }

  function encodeWav(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const writeString = (offset, str) => {
      for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    };
    writeString(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, samples.length * 2, true);
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Blob([view], { type: "audio/wav" });
  }
