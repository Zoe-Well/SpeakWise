// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProfilePage from "./ProfilePage";

const api = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));

vi.mock("../lib/api", () => ({
  apiGet: api.apiGet,
  apiPost: api.apiPost,
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));
vi.mock("../lib/useLLMStatus", () => ({ useLLMStatus: () => ({ isConfigured: true }) }));
vi.mock("../components/DocumentImport", () => ({ default: () => null }));
vi.mock("../components/ConfirmMergeDialog", () => ({ default: () => null }));
vi.mock("../components/ApiKeyRequiredDialog", () => ({ default: () => null }));
vi.mock("../components/EditableItem", () => ({
  EditableInternship: () => null,
  EditableProject: () => null,
}));
vi.mock("../components/Toast", () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn() }) }));

const skills = [
  { id: 1, category: "agent_llm", name: "LangGraph", proficiency: "熟悉" },
  { id: 2, category: "programming_language", name: "Python", proficiency: "精通" },
  { id: 3, category: "unknown", name: "Custom", proficiency: "了解" },
];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ProfilePage /></QueryClientProvider>);
}

describe("ProfilePage skills", () => {
  afterEach(cleanup);

  beforeEach(() => {
    api.apiPost.mockReset().mockResolvedValue({});
    api.apiGet.mockImplementation((path: string) => {
      if (path === "/api/skills") return Promise.resolve(skills);
      if (path === "/api/profile") return Promise.resolve({ id: 1, name: "测试用户" });
      return Promise.resolve([]);
    });
  });

  it("groups skills in the fixed category order, hides empty groups, and puts unknown categories in other", async () => {
    renderPage();

    await screen.findByText("LangGraph");

    const headings = screen.getAllByRole("heading", { level: 4 }).map((heading) => heading.textContent);
    expect(headings).toEqual(["编程语言", "Agent 与 LLM 应用", "其他"]);
    expect(screen.queryByRole("heading", { name: "前端与客户端" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Agent 与 LLM 应用" })).not.toBeNull();
    expect(screen.getByText("Custom")).not.toBeNull();
  });

  it("submits the selected category when manually adding a skill", async () => {
    renderPage();

    await screen.findByText("LangGraph");
    const input = screen.getByPlaceholderText("技能名");
    const form = input.parentElement!;
    fireEvent.change(within(form).getByLabelText("技能分类"), { target: { value: "agent_llm" } });
    fireEvent.change(input, { target: { value: "CrewAI" } });
    fireEvent.click(within(form).getByRole("button", { name: "添加" }));

    await waitFor(() => expect(api.apiPost).toHaveBeenCalledWith(
      "/api/skills",
      { category: "agent_llm", name: "CrewAI", proficiency: "熟悉" },
    ));
  });
});
