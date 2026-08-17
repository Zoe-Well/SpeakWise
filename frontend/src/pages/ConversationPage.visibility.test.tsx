// @vitest-environment jsdom

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ConversationPage from "./ConversationPage";

const stream = vi.hoisted(() => ({ handlers: null as null | Record<string, (value?: unknown) => void> }));
const animation = vi.hoisted(() => ({
  nextId: 0,
  callbacks: new Map<number, FrameRequestCallback>(),
}));

function flushAnimationFrames() {
  while (animation.callbacks.size > 0) {
    const [id, callback] = animation.callbacks.entries().next().value as [number, FrameRequestCallback];
    animation.callbacks.delete(id);
    callback(0);
  }
}

vi.mock("../lib/api", () => ({
  apiGet: vi.fn((path: string) => {
    if (path === "/api/sessions") return Promise.resolve([{ id: 1, name: "测试会话" }]);
    if (path.includes("/messages")) return Promise.resolve([]);
    if (path === "/api/settings/llm") return Promise.resolve({ provider: "test", api_key: "configured", model: "test" });
    if (path === "/api/profile") return Promise.resolve({ internship_count: 0, project_count: 1, skill_count: 0 });
    if (path === "/api/jd/latest") return Promise.resolve({ found: true });
    return Promise.resolve(null);
  }),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../lib/streamConsumer", () => ({
  consumeGenerateStream: vi.fn((_sid, _text, _command, _context, handlers) => {
    stream.handlers = handlers;
    return new Promise(() => {});
  }),
}));

vi.mock("../components/SessionSelector", () => ({ default: () => <div /> }));
vi.mock("../components/KnowledgeSelector", () => ({ default: () => <div /> }));
vi.mock("../components/MessageBubble", () => ({
  default: ({ content, thinking }: { content: string; thinking?: string }) => <div>{thinking}{content}</div>,
}));
vi.mock("../components/ChatInput", () => ({
  default: ({ onSend }: { onSend: (text: string) => void }) => <button onClick={() => onSend("测试流式输出")}>发送</button>,
}));
vi.mock("../components/ApiKeyRequiredDialog", () => ({ default: () => null }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }));

function Harness({ active, client }: { active: boolean; client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <div className={active ? "" : "hidden"}>
        <ConversationPage activeSessionId={1} onSessionChange={() => {}} isActive={active} />
      </div>
    </QueryClientProvider>
  );
}

describe("ConversationPage visibility", () => {
  beforeEach(() => {
    stream.handlers = null;
    animation.nextId = 0;
    animation.callbacks.clear();
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      const id = ++animation.nextId;
      animation.callbacks.set(id, callback);
      return id;
    });
    vi.stubGlobal("cancelAnimationFrame", (id: number) => animation.callbacks.delete(id));
  });

  it("scrolls to the live response when the page becomes active again", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<Harness active client={client} />);

    await waitFor(() => expect(screen.queryByText("⚠️ 未配置 API Key")).toBeNull());
    act(flushAnimationFrames);
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    expect(stream.handlers).not.toBeNull();

    act(() => stream.handlers?.onToken("第一段"));
    act(flushAnimationFrames);
    const callsWhileActive = scrollIntoView.mock.calls.length;

    view.rerender(<Harness active={false} client={client} />);
    act(() => stream.handlers?.onToken("第一段 第二段"));
    act(flushAnimationFrames);
    expect(screen.getByText("第一段 第二段")).not.toBeNull();
    expect(scrollIntoView.mock.calls.length).toBe(callsWhileActive);
    const callsBeforeReturn = scrollIntoView.mock.calls.length;

    view.rerender(<Harness active client={client} />);
    act(flushAnimationFrames);

    expect(scrollIntoView.mock.calls.length).toBeGreaterThan(callsBeforeReturn);
  });

  it("does not force-scroll after returning when the user was reading older messages", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<Harness active client={client} />);

    await waitFor(() => expect(screen.queryByText("⚠️ 未配置 API Key")).toBeNull());
    act(flushAnimationFrames);
    const messageArea = view.container.querySelector(".overflow-auto") as HTMLDivElement;
    Object.defineProperties(messageArea, {
      scrollHeight: { configurable: true, value: 1000 },
      clientHeight: { configurable: true, value: 400 },
      scrollTop: { configurable: true, value: 100, writable: true },
    });
    fireEvent.scroll(messageArea);
    const callsBeforeNavigation = scrollIntoView.mock.calls.length;

    view.rerender(<Harness active={false} client={client} />);
    view.rerender(<Harness active client={client} />);
    act(flushAnimationFrames);

    expect(scrollIntoView.mock.calls.length).toBe(callsBeforeNavigation);
  });
});
