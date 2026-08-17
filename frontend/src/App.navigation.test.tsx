// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import App from "./App";

vi.mock("./pages/ConversationPage", () => ({
  default: ({ isActive }: { isActive?: boolean }) => (
    <div>Conversation page <span data-testid="conversation-active">{String(isActive)}</span></div>
  ),
}));
vi.mock("./pages/ProfilePage", () => ({
  default: () => <input aria-label="profile draft" defaultValue="" />,
}));
vi.mock("./pages/JDPage", () => ({
  default: () => <div>JD page</div>,
}));
vi.mock("./pages/PromptTemplatePage", () => ({
  default: () => <div>Prompts page</div>,
}));
vi.mock("./pages/ReviewPage", () => ({
  default: () => <div>Review page</div>,
}));
vi.mock("./pages/InterviewPage", () => ({
  default: ({ isActive }: { isActive?: boolean }) => (
    <div>Interview page <span data-testid="interview-active">{String(isActive)}</span></div>
  ),
}));
vi.mock("./pages/SettingsPage", async () => {
  const React = await import("react");
  return {
    default: ({ highlight }: { highlight?: string | null }) => {
      const [highlightRuns, setHighlightRuns] = React.useState(0);
      React.useEffect(() => {
        if (highlight) setHighlightRuns((count) => count + 1);
      }, [highlight]);
      return <div>Settings page <span data-testid="highlight-runs">{highlightRuns}</span></div>;
    },
  };
});

afterEach(cleanup);

describe("App navigation", () => {
  it("preserves a visited page's local state after switching away and back", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "个人知识库" }));
    const draft = screen.getByLabelText("profile draft");
    fireEvent.change(draft, { target: { value: "正在处理的简历" } });

    fireEvent.click(screen.getByRole("button", { name: "岗位上下文" }));
    fireEvent.click(screen.getByRole("button", { name: "个人知识库" }));

    expect(screen.getByLabelText("profile draft")).toHaveValue("正在处理的简历");
  });

  it("mounts pages lazily and keeps them mounted after their first visit", () => {
    render(<App />);

    expect(screen.queryByText("Settings page")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "设置" }));
    expect(screen.getByText("Settings page")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "对话" }));

    expect(screen.getByText("Settings page")).toBeInTheDocument();
  });

  it("replays the same settings highlight after leaving through the sidebar", () => {
    render(<App />);

    act(() => {
      window.dispatchEvent(new CustomEvent("navigate", {
        detail: { page: "settings", highlight: "llm" },
      }));
    });
    expect(screen.getByTestId("highlight-runs")).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: "对话" }));
    act(() => {
      window.dispatchEvent(new CustomEvent("navigate", {
        detail: { page: "settings", highlight: "llm" },
      }));
    });

    expect(screen.getByTestId("highlight-runs")).toHaveTextContent("2");
  });

  it("notifies streaming pages when they become active or hidden", () => {
    render(<App />);

    expect(screen.getByTestId("conversation-active")).toHaveTextContent("true");
    fireEvent.click(screen.getByRole("button", { name: "模拟面试" }));

    expect(screen.getByTestId("conversation-active")).toHaveTextContent("false");
    expect(screen.getByTestId("interview-active")).toHaveTextContent("true");

    fireEvent.click(screen.getByRole("button", { name: "个人知识库" }));
    expect(screen.getByTestId("interview-active")).toHaveTextContent("false");
  });
});
