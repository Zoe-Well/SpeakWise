/** SpeakWise API 客户端 — fetch 封装 + SSE 流式解析 */

// 动态获取后端地址：优先 env → window.speakwise → 默认
function getBaseUrl(): string {
  if (import.meta.env?.VITE_API_URL) return import.meta.env.VITE_API_URL as string;
  if (typeof window !== "undefined" && window.speakwise?.backendPort) {
    return `http://${window.speakwise.backendHost}:${window.speakwise.backendPort}`;
  }
  // Browser production is served by FastAPI on the same origin. Electron and
  // local development still use the bundled/local backend on port 8001.
  return import.meta.env.DEV ? "http://127.0.0.1:8001" : "";
}
const BASE_URL = getBaseUrl();

export async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function apiPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function apiPostForm<T = unknown>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", body: formData });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function apiPut<T = unknown>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status, await res.text());
}

/** SSE 流式消费 — 逐个 token 回调，不做行缓冲阻塞 */
export async function consumeSSE(
  path: string,
  body: unknown,
  onEvent: (event: string, data: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new ApiError(res.status, errText);
  }
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Process lines: look for complete SSE events
    while (buffer.includes("\n")) {
      const nl = buffer.indexOf("\n");
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);

      if (line.startsWith("event: ")) {
        // Store event type, next data: line will complete the event
        const eventType = line.slice(7);
        // Peek ahead for data line
        if (buffer.startsWith("data: ")) {
          const nl2 = buffer.indexOf("\n");
          const dataLine = buffer.slice(0, nl2 === -1 ? buffer.length : nl2).trim();
          buffer = buffer.slice(nl2 === -1 ? buffer.length : nl2 + 1);
          const data = dataLine.startsWith("data: ") ? dataLine.slice(6) : dataLine;
          onEvent(eventType, data);
        }
      } else if (line.startsWith("data: ")) {
        // Standalone data line (without event: prefix = default "message" event)
        const data = line.slice(6);
        onEvent("message", data);
      }
    }

    // Yield to browser event loop so React can re-render
    await new Promise((r) => setTimeout(r, 0));
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}
