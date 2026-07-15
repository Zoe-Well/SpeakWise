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
  } catch(e) { callbacks.onError("音频初始化失败"); callbacks.onStateChange("error"); return; }

  ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    console.log("[voice] WS connected");
    callbacks.onStateChange("listening");

    ws!.send(JSON.stringify({
      common: { app_id: appId },
      business: { language: "zh_cn", domain: "iat", accent: "mandarin" },
      data: { status: 0, format: "audio/L16;rate=16000", encoding: "raw" }
    }));

    const wn = new AudioWorkletNode(audioCtx!, "pcm");
    const src = audioCtx!.createMediaStreamSource(stream!);
    src.connect(wn);
    const g = audioCtx!.createGain(); g.gain.value = 0;
    wn.connect(g); g.connect(audioCtx!.destination);

    let ready = false;

    wn.port.onmessage = (e) => {
      if (!ready || ws?.readyState !== WebSocket.OPEN) return;
      ws!.send(e.data);
    };

    ws!.addEventListener("message", (e) => {
      if (!ready) { ready = true; console.log("[voice] server ready"); }
      try {
        const msg = JSON.parse(e.data);
        if (msg.code !== 0 && msg.message) { callbacks.onError(msg.message); stopListening(); return; }
        if (msg.data?.result) {
          let text = "";
          for (const w of msg.data.result.ws || []) for (const c of w.cw || []) text += c.w;
          if (text) { console.log("[voice] text:", text); callbacks.onResult(text, msg.data.status === 2); }
        }
      } catch { /* */ }
    });
  };

  ws.onerror = () => { callbacks.onError("连接失败"); callbacks.onStateChange("error"); };
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
