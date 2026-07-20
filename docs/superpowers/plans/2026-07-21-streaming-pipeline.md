# Streaming Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让对话、简历评审、岗位分析和模拟面试共用一套可靠的 JSON SSE 协议，并确保流式阶段与完成阶段使用同一套 Markdown 渲染结果。

**Architecture:** 后端只负责产生带序号的结构化事件；前端先以标准 SSE 帧边界解码，再交给统一的流状态累加器。页面不再自行拼字符串，Markdown 始终走同一个渲染器，`done.content` 作为最终权威内容。

**Tech Stack:** FastAPI, sse-starlette, Python 3.12, React 18, TypeScript, Vitest, Testing Library, ReactMarkdown

## Global Constraints

- 保持现有事件名 `meta`、`thinking`、`token`、`done`、`error`，仅把 `data` 统一为 JSON。
- 所有文本通过 `JSON.stringify(payload)` / `json.dumps(payload, ensure_ascii=False)` 传输，绝不手工拼接 `data:`。
- 流式和最终态不得使用两条 Markdown 渲染路径。
- 断流保留已生成内容，并显示“生成中断”，不得清空。
- 每完成一个任务只提交该任务涉及的文件，不混入工作区现有改动。

---

## Task 1: 固化后端 SSE 事件契约

**Files:**

- Modify: `backend/src/llm/streaming.py`
- Create: `backend/tests/unit/test_sse_streaming.py`

- [ ] **Step 1: 写失败测试，覆盖 Unicode、换行和错误载荷**

```python
from backend.src.llm.streaming import sse_event


def test_token_event_is_json_and_preserves_text():
    event = sse_event("token", {"seq": 3, "text": "第一行\n第二行 data: 原文"})
    assert event["event"] == "token"
    assert '"seq": 3' in event["data"]
    assert "第一行\\n第二行 data: 原文" in event["data"]


def test_error_event_has_stable_shape():
    event = sse_event(
        "error",
        {"code": "UPSTREAM_FAILED", "message": "生成失败，请重试", "retryable": True},
    )
    assert event["event"] == "error"
    assert "UPSTREAM_FAILED" in event["data"]
```

- [ ] **Step 2: 运行测试并确认因缺少 `sse_event` 失败**

Run: `uv run pytest backend/tests/unit/test_sse_streaming.py -q`

Expected: `ImportError` 或 `cannot import name 'sse_event'`。

- [ ] **Step 3: 实现最小事件编码器和公共载荷构造器**

在 `backend/src/llm/streaming.py` 提供以下稳定接口：

需要实现以下四个明确签名：

- `sse_event(event: str, payload: dict) -> dict[str, str]`
- `token_payload(seq: int, text: str) -> dict`
- `done_payload(content: str) -> dict`
- `error_payload(code: str, message: str, retryable: bool) -> dict`

实现要求：`sse_event()` 使用 `json.dumps(payload, ensure_ascii=False)`；`done_payload()` 自动计算字符长度；不得写日志记录正文。

- [ ] **Step 4: 运行测试并确认通过**

Run: `uv run pytest backend/tests/unit/test_sse_streaming.py -q`

Expected: `2 passed`。

- [ ] **Step 5: 提交**

```powershell
git add backend/src/llm/streaming.py backend/tests/unit/test_sse_streaming.py
git commit -m "test: define structured SSE event contract"
```

## Task 2: 让全部后端流接口遵守同一协议

**Files:**

- Modify: `backend/src/api/generate.py`
- Modify: `backend/src/api/review.py`
- Modify: `backend/src/api/interview.py`
- Create: `backend/tests/contract/test_stream_event_contract.py`

- [ ] **Step 1: 写契约测试，枚举每类允许事件**

测试直接消费各模块抽出的事件生成器，并断言：

```python
payload = json.loads(event["data"])
assert event["event"] in {"meta", "thinking", "token", "done", "error"}
if event["event"] in {"thinking", "token"}:
    assert payload.keys() == {"seq", "text"}
if event["event"] == "done":
    assert payload == {"content": payload["content"], "length": len(payload["content"])}
```

使用假异步 LLM 流 `iter(["你好", "\n世界"])`，不要请求真实模型。

- [ ] **Step 2: 运行并确认现有纯文本 `data` 使测试失败**

Run: `uv run pytest backend/tests/contract/test_stream_event_contract.py -q`

Expected: JSON 解码失败或载荷字段断言失败。

- [ ] **Step 3: 改造 `/api/generate`**

- `meta` 使用对象载荷，保留 `command/session_id/session_mode/fast_mode`。
- `thinking` 与 `token` 分别维护独立递增 `seq`。
- `done` 返回完整正文与长度。
- `error` 仅返回稳定错误码、用户消息、是否可重试。
- `_wrapped_stream()` 继续释放并发锁，但不再改写事件内容。

- [ ] **Step 4: 改造评审和模拟面试的所有流接口**

覆盖：

- `/api/review/resume`
- `/api/review/job`
- `/api/interview/start`
- `/api/interview/respond`
- `/api/interview/next`
- `/api/interview/summary`

这些接口使用同一个事件辅助函数；缺少参数统一为 `INVALID_REQUEST`，上游异常统一为 `UPSTREAM_FAILED`。

- [ ] **Step 5: 运行后端契约测试和全量测试**

Run: `uv run pytest backend/tests/contract/test_stream_event_contract.py -q`

Expected: all passed。

Run: `uv run pytest backend/tests -q`

Expected: all passed，无真实网络请求。

- [ ] **Step 6: 提交**

```powershell
git add backend/src/api/generate.py backend/src/api/review.py backend/src/api/interview.py backend/tests/contract/test_stream_event_contract.py
git commit -m "fix: standardize all streaming endpoints"
```

## Task 3: 实现符合标准帧边界的前端 SSE 解码器

**Files:**

- Create: `frontend/src/lib/sseDecoder.ts`
- Create: `frontend/src/lib/sseDecoder.test.ts`
- Create: `frontend/src/test/setup.ts`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 配置现有 Vitest/Testing Library 依赖**

在 `vite.config.ts` 增加 `test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"] }`，`setup.ts` 仅导入 `@testing-library/jest-dom/vitest`。这是测试基础设施接线，不单独测试。

- [ ] **Step 2: 写表驱动失败测试**

至少覆盖：单字节拆包、中文 UTF-8 中间拆包、`\r\n`、多行 `data:`、一个 chunk 含多个事件、尾部无空行、正文包含字面量 `data:`。

```ts
it("waits for a blank line before emitting", () => {
  const seen: SSEEvent[] = [];
  const decoder = createSSEDecoder((event) => seen.push(event));
  decoder.push(bytes("event: token\ndata: {\"seq\":1,"));
  expect(seen).toEqual([]);
  decoder.push(bytes("\"text\":\"data: hello\"}\n\n"));
  expect(seen).toEqual([{ event: "token", data: '{"seq":1,"text":"data: hello"}' }]);
});
```

- [ ] **Step 3: 运行并确认模块不存在**

Run: `npm test -- src/lib/sseDecoder.test.ts`

Workdir: `frontend`

Expected: cannot resolve `./sseDecoder`。

- [ ] **Step 4: 实现增量解码器**

导出：

```ts
export interface SSEEvent { event: string; data: string; id?: string }
export interface SSEDecoder { push(chunk: Uint8Array): void; finish(): void }
export function createSSEDecoder(onEvent: (event: SSEEvent) => void): SSEDecoder
```

使用一个 `TextDecoder("utf-8")` 并以 `{ stream: true }` 解码；仅遇到空行才派发事件；同一帧多条 `data:` 用 `\n` 合并；忽略以 `:` 开头的注释行；`finish()` 刷新 decoder 和完整尾帧。

- [ ] **Step 5: 让 `consumeSSE()` 使用新解码器**

`consumeSSE()` 只负责 fetch、读取字节、传给 decoder、处理 AbortSignal。删除按普通换行立即处理事件的旧逻辑。

- [ ] **Step 6: 运行测试与类型构建**

Run: `npm test -- src/lib/sseDecoder.test.ts`

Expected: all passed。

Run: `npm run build`

Expected: TypeScript 和 Vite build 成功。

- [ ] **Step 7: 提交**

```powershell
git add frontend/src/lib/sseDecoder.ts frontend/src/lib/sseDecoder.test.ts frontend/src/test/setup.ts frontend/vite.config.ts frontend/src/lib/api.ts
git commit -m "fix: decode SSE by complete event frames"
```

## Task 4: 建立统一的 JSON 流状态累加器

**Files:**

- Modify: `frontend/src/lib/streamConsumer.ts`
- Create: `frontend/src/lib/streamConsumer.test.ts`

- [ ] **Step 1: 写状态转换失败测试**

覆盖 `idle → connecting → thinking → streaming → completed`、服务端 `done.content` 覆盖本地累积、error 保留 partial、abort 标记 interrupted、重复/乱序 seq 不重复追加。

```ts
expect(reduceStream(state, { event: "token", data: { seq: 2, text: "B" } }).content)
  .toBe("B");
expect(reduceStream(state, { event: "token", data: { seq: 2, text: "B" } }).content)
  .toBe(state.content);
```

- [ ] **Step 2: 运行并确认缺少 reducer/类型**

Run: `npm test -- src/lib/streamConsumer.test.ts`

Workdir: `frontend`

Expected: import 或导出失败。

- [ ] **Step 3: 实现类型、JSON 校验与 reducer**

导出：

```ts
export type StreamPhase = "idle" | "connecting" | "thinking" | "streaming" | "completed" | "interrupted" | "failed";
export interface StreamState { phase: StreamPhase; content: string; thinking: string; error?: StreamError }
export function parseStreamEvent(event: SSEEvent): GenerateEvent;
export function reduceStream(state: StreamState, event: GenerateEvent): StreamState;
```

运行期校验至少确认 `token/thinking` 有整数 `seq` 和字符串 `text`，`done` 有字符串 `content`。无法解析的事件转为 `PROTOCOL_ERROR`，不把原始载荷展示给用户。

- [ ] **Step 4: 用 reducer 重写 `consumeGenerateStream()`**

保留兼容页面所需回调，但回调输入来自状态机；加入 `onStateChange`，使后续页面可以逐步迁移。渲染更新通过单个 `requestAnimationFrame` 合并，`done` 到达时立即 flush。

- [ ] **Step 5: 运行单测和前端全量测试**

Run: `npm test -- src/lib/streamConsumer.test.ts`

Expected: all passed。

Run: `npm test`

Expected: all passed。

- [ ] **Step 6: 提交**

```powershell
git add frontend/src/lib/streamConsumer.ts frontend/src/lib/streamConsumer.test.ts
git commit -m "feat: add resilient stream state accumulator"
```

## Task 5: 统一流式与最终 Markdown 渲染路径

**Files:**

- Modify: `frontend/src/components/MarkdownRenderer.tsx`
- Create: `frontend/src/components/MarkdownRenderer.test.tsx`
- Modify: `frontend/src/components/MessageBubble.tsx`

- [ ] **Step 1: 写渲染一致性失败测试**

同一段完整 Markdown 在 `streaming={true}` 与 `streaming={false}` 时，除光标节点外 DOM 结构和文本必须一致；测试标题、列表、代码块、表格。

- [ ] **Step 2: 运行并确认当前“完整段 + 纯文本尾部”分支导致失败**

Run: `npm test -- src/components/MarkdownRenderer.test.tsx`

Workdir: `frontend`

Expected: DOM 结构不一致。

- [ ] **Step 3: 删除双渲染分支**

始终以完整 `content` 调用同一个 `<ReactMarkdown>`。流式光标放在 Markdown 容器之后，使用 `aria-label="正在生成"`。仅允许对未闭合三反引号追加虚拟闭合围栏，并保证该补全文本不进入最终内容。

- [ ] **Step 4: 更新 `MessageBubble` 的状态展示**

`streaming` 只控制光标和状态文案，不改变 Markdown 解析方式；`interrupted` 显示已生成内容及“生成中断，可重试”。这是简单 UI 接线，不单独增加测试。

- [ ] **Step 5: 验证**

Run: `npm test -- src/components/MarkdownRenderer.test.tsx`

Expected: all passed。

Run: `npm run build`

Expected: build succeeded。

- [ ] **Step 6: 提交**

```powershell
git add frontend/src/components/MarkdownRenderer.tsx frontend/src/components/MarkdownRenderer.test.tsx frontend/src/components/MessageBubble.tsx
git commit -m "fix: render streaming markdown consistently"
```

## Task 6: 页面接入统一流状态并消除完成态闪烁

**Files:**

- Modify: `frontend/src/pages/ConversationPage.tsx`
- Modify: `frontend/src/pages/ReviewPage.tsx`
- Modify: `frontend/src/pages/InterviewPage.tsx`
- Create: `frontend/src/pages/ConversationPage.test.tsx`

- [ ] **Step 1: 写对话完成态回归测试**

模拟 token 后紧接 done，断言助手内容从 partial 直接变为 `done.content`，期间不出现空白；随后查询刷新不得产生第二条重复消息。

- [ ] **Step 2: 运行并确认当前 50ms 清空/重取逻辑失败**

Run: `npm test -- src/pages/ConversationPage.test.tsx`

Workdir: `frontend`

Expected: 页面短暂找不到助手正文或出现重复节点。

- [ ] **Step 3: 改造对话页**

- 删除页面自己的 `full += data` 与延时清空逻辑。
- `done.content` 立即写入 React Query 的 messages cache，临时消息使用稳定 client id。
- cache 写入后再 invalidate/refetch；服务端消息按 id 替换临时消息。
- abort/error 保留 partial 和对应 phase。

- [ ] **Step 4: 改造评审页与模拟面试页**

所有入口都使用 `parseStreamEvent + reduceStream`；删除各自的字符串累加。评审和面试无需新增单独页面测试，因为核心状态机已覆盖，改动通过构建和手工冒烟验证。

- [ ] **Step 5: 自动验证**

Run: `npm test`

Expected: all passed。

Run: `npm run build`

Expected: build succeeded。

Run: `uv run pytest backend/tests -q`

Expected: all passed。

- [ ] **Step 6: 本地冒烟验证**

在 `http://localhost:5173/` 依次验证：

1. 对话输出标题、列表、代码块时没有可见 `data:`。
2. 生成结束时正文不闪空、不重新排版。
3. 简历评审与岗位分析表现一致。
4. 模拟面试四个流入口表现一致。
5. 中途停止请求后 partial 保留且显示中断状态。

- [ ] **Step 7: 提交**

```powershell
git add frontend/src/pages/ConversationPage.tsx frontend/src/pages/ConversationPage.test.tsx frontend/src/pages/ReviewPage.tsx frontend/src/pages/InterviewPage.tsx
git commit -m "fix: unify page streaming lifecycle"
```

## Task 7: 阶段一验收

- [ ] 运行 `uv run pytest backend/tests -q`，预期全绿。
- [ ] 在 `frontend` 运行 `npm test`，预期全绿。
- [ ] 在 `frontend` 运行 `npm run build`，预期成功。
- [ ] 搜索旧式拼接：`rg "full \+= data|data:\\s*\$|setTimeout.*50" frontend/src backend/src`，预期无遗留业务用法。
- [ ] 更新设计文档中的阶段一状态为已完成，并记录真实测试命令结果。
- [ ] 提交验收记录：`git commit -m "docs: record streaming pipeline verification"`。
