// @vitest-environment jsdom

import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InterviewPage from "./InterviewPage";

const stream = vi.hoisted(() => ({ onEvent: null as null | ((event: string, data: string) => void) }));
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
  apiGet: vi.fn(() => Promise.resolve([])),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
  consumeSSE: vi.fn((_path, _body, onEvent) => {
    stream.onEvent = onEvent;
    return new Promise(() => {});
  }),
}));
vi.mock("../lib/useLLMStatus", () => ({ useLLMStatus: () => ({ isConfigured: true }) }));
vi.mock("../components/MarkdownRenderer", () => ({ default: ({ content }: { content: string }) => <div>{content}</div> }));
vi.mock("../components/ApiKeyRequiredDialog", () => ({ default: () => null }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }));

function Harness({ active, client }: { active: boolean; client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <div className={active ? "" : "hidden"}>
        <InterviewPage isActive={active} />
      </div>
    </QueryClientProvider>
  );
}

describe("InterviewPage visibility", () => {
  beforeEach(() => {
    stream.onEvent = null;
    animation.nextId = 0;
    animation.callbacks.clear();
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      const id = ++animation.nextId;
      animation.callbacks.set(id, callback);
      return id;
    });
    vi.stubGlobal("cancelAnimationFrame", (id: number) => animation.callbacks.delete(id));
  });

  it("shows the latest streaming question and scrolls when the page becomes active again", () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scrollIntoView });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<Harness active client={client} />);
    act(flushAnimationFrames);

    fireEvent.click(screen.getByRole("button", { name: "开始面试" }));
    expect(stream.onEvent).not.toBeNull();
    act(() => stream.onEvent?.("token", "第一段"));
    act(flushAnimationFrames);
    const callsWhileActive = scrollIntoView.mock.calls.length;

    view.rerender(<Harness active={false} client={client} />);
    act(() => stream.onEvent?.("token", " 第二段"));
    act(flushAnimationFrames);
    expect(screen.getByText("第一段 第二段")).not.toBeNull();
    expect(scrollIntoView.mock.calls.length).toBe(callsWhileActive);

    view.rerender(<Harness active client={client} />);
    act(flushAnimationFrames);
    expect(scrollIntoView.mock.calls.length).toBeGreaterThan(callsWhileActive);
  });
});
