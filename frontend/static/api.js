/**
 * SwasthyaVaani — Frontend API Client
 * 
 * HARD RULE: Base URL is configured in a SINGLE place below so it can be changed in one line.
 * The backend FastAPI application runs on port 8000 by default and allows all CORS origins.
 */

// ── SINGLE BASE URL CONFIGURATION ──────────────────────────────────────────
const BACKEND_BASE_URL = (typeof window !== 'undefined' && window.__SW_BACKEND_URL__) || 'http://localhost:8000';
// ───────────────────────────────────────────────────────────────────────────

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.AshaAPI = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function getBaseUrl() {
    return BACKEND_BASE_URL.replace(/\/+$/, '');
  }

  function getWsVoiceUrl(lang) {
    const base = getBaseUrl();
    const wsProto = base.startsWith('https://') ? 'wss://' : 'ws://';
    const host = base.replace(/^https?:\/\//, '');
    const activeLang = lang || 'auto';
    return `${wsProto}${host}/ws/voice?lang=${encodeURIComponent(activeLang)}`;
  }

  // ── REST Endpoints ───────────────────────────────────────────────────────

  async function checkHealth() {
    try {
      const res = await fetch(`${getBaseUrl()}/health`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      return { ok: true, data };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  async function getBeneficiaries() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/beneficiaries`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      return { ok: true, beneficiaries: data.beneficiaries || [] };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err), beneficiaries: [] };
    }
  }

  async function getLanguages() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/languages`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      return { ok: true, data };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err), data: null };
    }
  }

  async function getRecords() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/records`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      return { ok: true, records: data.records || [] };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err), records: [] };
    }
  }

  async function purgeAll() {
    try {
      const res = await fetch(`${getBaseUrl()}/api/admin/purge`, {
        method: 'DELETE',
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      return { ok: true, data };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  // ── Web Audio Resampler & Streaming PCM Player ───────────────────────────

  function downsampleBuffer(buffer, inputSampleRate, outputSampleRate = 16000) {
    if (inputSampleRate === outputSampleRate) return buffer;
    const ratio = inputSampleRate / outputSampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0, count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  class VoiceStreamingSession {
    constructor(callbacks = {}) {
      this.callbacks = callbacks;
      this.ws = null;
      this.micStream = null;
      this.audioContext = null;
      this.audioProcessor = null;
      this.playContext = null;
      this.nextPlayTime = 0;
      this.activeAudioSources = [];
      this.isRecording = false;
      this.isPttActive = false;
      this.isAgentSpeaking = false;
      this.chunkBuffer = [];
      this.language = 'hi-IN';
      this.sessionId = null;
    }

    _emit(cbName, ...args) {
      if (typeof this.callbacks[cbName] === 'function') {
        try {
          this.callbacks[cbName](...args);
        } catch (e) {
          console.error(`Error in callback ${cbName}:`, e);
        }
      }
    }

    async connect(lang = 'hi-IN') {
      this.language = lang;
      const url = getWsVoiceUrl(this.language);
      this._emit('status', 'connecting');

      return new Promise((resolve, reject) => {
        try {
          this.ws = new WebSocket(url);
          this.ws.binaryType = 'arraybuffer';

          this.ws.onopen = () => {
            this._emit('status', 'listening');
            resolve();
          };

          this.ws.onmessage = (event) => {
            if (typeof event.data === 'string') {
              try {
                const parsed = JSON.parse(event.data);
                this._handleJsonEvent(parsed);
              } catch (e) {
                console.error('Failed to parse WebSocket JSON event:', e);
              }
            } else if (event.data instanceof ArrayBuffer) {
              this._playPcmChunk(event.data);
            }
          };

          this.ws.onerror = (err) => {
            const msg = 'WebSocket connection error to SwasthyaVaani server.';
            this._emit('error', msg);
            this._emit('status', 'error');
            reject(new Error(msg));
          };

          this.ws.onclose = () => {
            this._stopMic();
            this._stopAudioPlayback();
            this._emit('status', 'idle');
          };
        } catch (err) {
          this._emit('status', 'error');
          this._emit('error', err instanceof Error ? err.message : String(err));
          reject(err);
        }
      });
    }

    _handleJsonEvent(ev) {
      const type = ev.type || '';
      const payload = ev.payload || {};
      this._emit('event', ev);

      switch (type) {
        case 'session_ready':
          this.sessionId = payload.session_id;
          this._emit('session_ready', payload);
          break;
        case 'agent_speaking':
          this.isAgentSpeaking = Boolean(payload.speaking);
          this._emit('agent_speaking', payload);
          if (this.isAgentSpeaking) {
            this._emit('status', 'speaking');
          } else {
            this._emit('status', this.isRecording ? 'listening' : 'idle');
          }
          break;
        case 'transcript_partial':
          this._emit('transcript_partial', payload);
          break;
        case 'transcript_final':
          this._emit('transcript_final', payload);
          break;
        case 'danger_alert':
          this._emit('danger_alert', payload);
          break;
        case 'record_draft':
          this._emit('record_draft', payload);
          break;
        case 'record_confirmed':
          this._emit('record_confirmed', payload);
          break;
        case 'save_blocked':
          this._emit('save_blocked', payload);
          break;
        case 'language_detected':
          this._emit('language_detected', payload);
          break;
        case 'barge_in_ack':
          this._stopAudioPlayback();
          this._emit('barge_in_ack', payload);
          break;
        case 'session_purged':
          this._emit('session_purged', payload);
          break;
        case 'error':
          this._emit('error', payload.message || 'Server error');
          break;
        default:
          break;
      }
    }

    _playPcmChunk(arrayBuffer) {
      try {
        if (!this.playContext) {
          const AudioCtx = window.AudioContext || window.webkitAudioContext;
          if (AudioCtx) this.playContext = new AudioCtx();
        }
        if (!this.playContext) return;

        if (this.playContext.state === 'suspended') {
          void this.playContext.resume();
        }

        const int16Array = new Int16Array(arrayBuffer);
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
          float32Array[i] = int16Array[i] / 32768.0;
        }

        const audioBuffer = this.playContext.createBuffer(1, float32Array.length, 16000);
        audioBuffer.getChannelData(0).set(float32Array);

        const sourceNode = this.playContext.createBufferSource();
        sourceNode.buffer = audioBuffer;
        sourceNode.connect(this.playContext.destination);

        const now = this.playContext.currentTime;
        const startTime = Math.max(now, this.nextPlayTime);
        sourceNode.start(startTime);
        this.nextPlayTime = startTime + audioBuffer.duration;

        this.activeAudioSources.push(sourceNode);
        sourceNode.onended = () => {
          const idx = this.activeAudioSources.indexOf(sourceNode);
          if (idx !== -1) this.activeAudioSources.splice(idx, 1);
        };
      } catch (err) {
        console.debug('Error playing PCM audio chunk:', err);
      }
    }

    _stopAudioPlayback() {
      for (const src of this.activeAudioSources) {
        try {
          src.stop();
        } catch {
          // Ignore
        }
      }
      this.activeAudioSources = [];
      if (this.playContext) {
        this.nextPlayTime = this.playContext.currentTime;
      }
    }

    async startMic() {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!this.playContext && AudioCtx) {
          this.playContext = new AudioCtx();
        }
        if (this.playContext && this.playContext.state === 'suspended') {
          await this.playContext.resume();
        }

        this.micStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        this.audioContext = new AudioCtx();
        if (this.audioContext.state === 'suspended') {
          await this.audioContext.resume();
        }

        const nativeSampleRate = this.audioContext.sampleRate;
        const source = this.audioContext.createMediaStreamSource(this.micStream);
        this.audioProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);

        const zeroGain = this.audioContext.createGain();
        zeroGain.gain.value = 0.0;

        this.chunkBuffer = [];

        this.audioProcessor.onaudioprocess = (e) => {
          if (!this.isRecording && !this.isPttActive) return;
          if (this.isAgentSpeaking && !this.isPttActive) return;

          const inputFloat32 = e.inputBuffer.getChannelData(0);

          // Calculate RMS for live visualizer
          let sumSquares = 0;
          for (let i = 0; i < inputFloat32.length; i++) {
            sumSquares += inputFloat32[i] * inputFloat32[i];
          }
          const rms = Math.sqrt(sumSquares / inputFloat32.length);
          this._emit('volume', rms);

          // Resample to 16,000 Hz
          const resampledFloat32 = downsampleBuffer(inputFloat32, nativeSampleRate, 16000);
          const int16 = new Int16Array(resampledFloat32.length);
          for (let i = 0; i < resampledFloat32.length; i++) {
            const s = Math.max(-1, Math.min(1, resampledFloat32[i]));
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }

          for (let i = 0; i < int16.length; i++) {
            this.chunkBuffer.push(int16[i]);
          }

          while (this.chunkBuffer.length >= 512) {
            const chunk = new Int16Array(this.chunkBuffer.splice(0, 512));
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(chunk.buffer);
            }
          }
        };

        source.connect(this.audioProcessor);
        this.audioProcessor.connect(zeroGain);
        zeroGain.connect(this.audioContext.destination);

        this.isRecording = true;
        this._emit('status', 'listening');
        return true;
      } catch (err) {
        console.error('Mic initialization failed:', err);
        this._emit('error', 'Microphone permission denied or not supported.');
        return false;
      }
    }

    _stopMic() {
      this.isRecording = false;
      if (this.audioProcessor) {
        try {
          this.audioProcessor.disconnect();
        } catch {}
        this.audioProcessor = null;
      }
      if (this.audioContext) {
        try {
          void this.audioContext.close();
        } catch {}
        this.audioContext = null;
      }
      if (this.micStream) {
        try {
          this.micStream.getTracks().forEach((t) => t.stop());
        } catch {}
        this.micStream = null;
      }
    }

    sendJson(type, payload = {}) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        const frame = JSON.stringify({
          type,
          timestamp: Date.now(),
          payload,
        });
        this.ws.send(frame);
        return true;
      }
      return false;
    }

    sendTextTurn(text) {
      return this.sendJson('text_turn_debug', { text });
    }

    bargeIn() {
      this._stopAudioPlayback();
      return this.sendJson('barge_in', { reason: 'manual_stop' });
    }

    changeLanguage(language) {
      this.language = language;
      return this.sendJson('language_change', { language });
    }

    setPttState(active) {
      this.isPttActive = active;
      return this.sendJson('ptt_state', { active });
    }

    sessionPurge() {
      return this.sendJson('session_purge', {});
    }

    disconnect() {
      this._stopMic();
      this._stopAudioPlayback();
      if (this.ws) {
        try {
          this.ws.close();
        } catch {}
        this.ws = null;
      }
      this._emit('status', 'idle');
    }
  }

  return {
    BASE_URL: getBaseUrl(),
    getWsVoiceUrl,
    checkHealth,
    getBeneficiaries,
    getLanguages,
    getRecords,
    purgeAll,
    createVoiceSession: (callbacks) => new VoiceStreamingSession(callbacks),
  };
});
