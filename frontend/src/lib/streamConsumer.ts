/** SSE 流消费 —— 将 token 流接入 React state，每次 yield 到浏览器 */

import { consumeSSE } from "./api";

export interface StreamCallbacks {
  onMeta?: (meta: Record<string, unknown>) => void;
  onThinking?: (accumulated: string) => void;
  onToken?: (partialText: string) => void;
  onDone?: (fullText: string) => void;
  onError?: (error: string) => void;
}

export async function consumeGenerateStream(
  sessionId: number,
  content: string,
  command: string | null,
  templateId: string | null,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  let full = "";
  let thinking = "";
  const body: Record<string, unknown> = { session_id: sessionId, content, command };
  if (templateId) body.template_id = templateId;
  try {
    await consumeSSE("/api/generate", body, (event, data) => {
        if (event === "meta") {
          callbacks.onMeta?.(JSON.parse(data));
        } else if (event === "thinking") {
          thinking += data;
          callbacks.onThinking?.(thinking);
        } else if (event === "token") {
          full += data;
          callbacks.onToken?.(full);
        } else if (event === "done") {
          callbacks.onDone?.(full);
        } else if (event === "error") {
          callbacks.onError?.(data);
        }
      },
      signal
    );
  } catch (e) {
    callbacks.onError?.(String(e));
  }
}
