/** 讯飞语音输入 — 浏览器 AudioWorklet 直连讯飞 WebSocket */

export type VoiceState = "idle" | "connecting" | "listening" | "error";

export interface VoiceCallbacks {
  onResult: (text: string, isFinal: boolean) => void;
  onStateChange: (state: VoiceState) => void;
  onError: (msg: string) => void;
}

let ws: WebSocket | null = null;
let stream: MediaStream | null = null;
let audioCtx: AudioContext | null = null;

// AudioWorklet processor (inline as Blob URL)
const workletBlob = new Blob([`
  class PCM extends AudioWorkletProcessor {
    process(inputs) {
      const ch = inputs[0]?.[0];
      if (ch && ch.length > 0) {
        const pcm = new Int16Array(ch.length);
        for (let i=0;i<ch.length;i++) pcm[i]=Math.max(-32768,Math.min(32767,Math.round(ch[i]*32767)));
        this.port.postMessage(pcm.buffer, [pcm.buffer]);
      }
      return true;
    }
  }
  registerProcessor("pcm", PCM);
`], { type: "application/javascript" });
const workletUrl = URL.createObjectURL(workletBlob);

export async function startListening(wsUrl: string, appId: string, callbacks: VoiceCallbacks) {
  stopListening();
  callbacks.onStateChange("connecting");

  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { callbacks.onError("无法访问麦克风"); callbacks.onStateChange("error"); return; }

  try {
    audioCtx = new AudioContext({ sampleRate: 16000 });
    await audioCtx.resume();
    await audioCtx.audioWorklet.addModule(workletUrl);
  } catch(e) { console.error("[voice] audio init failed:", e); callbacks.onError("音频初始化失败"); callbacks.onStateChange("error"); return; }

  ws = new WebSocket(wsUrl);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    console.log("[voice] WS connected, sending init frame");
    callbacks.onStateChange("listening");

    // Send init frame (use raw encoding — audio will be sent as JSON-wrapped base64)
    ws!.send(JSON.stringify({
      common: { app_id: appId },
      business: { language: "zh_cn", domain: "iat", accent: "mandarin" },
      data: { status: 0, format: "audio/L16;rate=16000", encoding: "raw" }
    }));

    try {
      const wn = new AudioWorkletNode(audioCtx!, "pcm");
      const src = audioCtx!.createMediaStreamSource(stream!);
      src.connect(wn);
      // Keep worklet alive via muted output
      const g = audioCtx!.createGain(); g.gain.value = 0;
      wn.connect(g); g.connect(audioCtx!.destination);

      let serverReady = false;
      let textReceived = false;
      let noTextTimer: ReturnType<typeof setTimeout> | null = null;

      // Convert PCM ArrayBuffer to base64 and send as JSON-wrapped frame
      function arrayBufferToBase64(buffer: ArrayBuffer): string {
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
        return btoa(binary);
      }

      // Send audio chunks as JSON-wrapped base64 (iFlytek requires this format)
      wn.port.onmessage = (e) => {
        if (ws?.readyState !== WebSocket.OPEN) return;
        const b64 = arrayBufferToBase64(e.data as ArrayBuffer);
        ws!.send(JSON.stringify({
          data: { status: 1, format: "audio/L16;rate=16000", encoding: "raw", audio: b64 }
        }));
        if (!serverReady) {
          // Start a timeout: if no text after 5s of sending audio, warn
          if (!noTextTimer) {
            noTextTimer = setTimeout(() => {
              if (!textReceived) {
                console.warn("[voice] no text received after 5s — check credentials or audio");
                callbacks.onError("未识别到语音，请检查麦克风权限或讯飞配置");
                stopListening();
              }
            }, 5000);
          }
        }
      };

      ws!.addEventListener("message", (e) => {
        if (!serverReady) { serverReady = true; console.log("[voice] server ready"); }
        try {
          const msg = JSON.parse(e.data as string);
          const code = msg.code ?? 0;
          if (code !== 0 && msg.message) {
            console.error("[voice] server error:", code, msg.message);
            callbacks.onError(`识别失败: ${msg.message}`);
            stopListening();
            return;
          }
          if (msg.data?.result) {
            let text = "";
            for (const w of msg.data.result.ws || []) for (const c of w.cw || []) text += c.w;
            if (text) {
              textReceived = true;
              if (noTextTimer) { clearTimeout(noTextTimer); noTextTimer = null; }
              console.log("[voice] text:", text);
              callbacks.onResult(text, msg.data.status === 2);
            }
          }
        } catch { /* ignore parse errors */ }
      });
    } catch (e) {
      console.error("[voice] worklet setup failed:", e);
      callbacks.onError("音频处理初始化失败");
      callbacks.onStateChange("error");
    }
  };

  ws.onerror = () => { console.error("[voice] WS error"); callbacks.onError("语音服务连接失败"); callbacks.onStateChange("error"); };
  ws.onclose = () => callbacks.onStateChange("idle");
}

export function stopListening() {
  if (ws?.readyState === WebSocket.OPEN) {
    try { ws.send(JSON.stringify({ data: { status: 2 } })); } catch(e){}
    setTimeout(() => { try { ws?.close(); } catch(e){} }, 200);
  }
  if (stream) { stream.getTracks().forEach(t=>t.stop()); stream = null; }
  if (audioCtx) { try { audioCtx.close(); } catch(e){}; audioCtx = null; }
  ws = null;
}

// For ChatInput compat
export function stopListeningAndTranscribe(cb: VoiceCallbacks): Promise<string> {
  stopListening();
  cb.onStateChange("idle");
  return Promise.resolve("");
}
