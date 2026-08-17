// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProfilePage from "./ProfilePage";

const api = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));

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
vi.mock("../components/Toast", () => ({ useToast: () => toast }));

const skills = [
  { id: 1, category: "agent_llm", name: "LangGraph", proficiency: "熟悉" },
  { id: 2, category: "programming_language", name: "Python", proficiency: "精通" },
  { id: 3, category: "unknown", name: "Custom", proficiency: "了解" },
];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(<QueryClientProvider client={client}><ProfilePage /></QueryClientProvider>) };
}

describe("ProfilePage skills", () => {
  afterEach(cleanup);

  beforeEach(() => {
    toast.success.mockReset();
    toast.error.mockReset();
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

  it("previews the complete skill list before saving AI classifications", async () => {
    api.apiPost.mockImplementation((path: string) => {
      if (path === "/api/skills/classification/preview") {
        return Promise.resolve([
          { id: 1, name: "LangGraph", current_category: "agent_llm", suggested_category: "agent_llm" },
          { id: 2, name: "Python", current_category: "programming_language", suggested_category: "programming_language" },
          { id: 3, name: "Custom", current_category: "unknown", suggested_category: "unrecognized" },
        ]);
      }
      return Promise.resolve({});
    });
    renderPage();

    await screen.findByText("LangGraph");
    fireEvent.click(screen.getByRole("button", { name: "AI 智能整理" }));

    await waitFor(() => expect(api.apiPost).toHaveBeenCalledWith(
      "/api/skills/classification/preview",
      { skills: skills.map(({ id, name }) => ({ id, name })) },
    ));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("编程语言")).not.toBeNull();
    expect(within(dialog).getByText("Agent 与 LLM 应用")).not.toBeNull();
    expect(within(dialog).getByText("其他")).not.toBeNull();
    expect(api.apiPost).not.toHaveBeenCalledWith(
      "/api/skills/classification/apply",
      expect.anything(),
    );
  });

  it("closes an AI classification preview without applying when cancelled", async () => {
    api.apiPost.mockImplementation((path: string) => path === "/api/skills/classification/preview"
      ? Promise.resolve([{ id: 1, name: "LangGraph", current_category: "agent_llm", suggested_category: "agent_llm" }])
      : Promise.resolve({}));
    renderPage();

    await screen.findByText("LangGraph");
    fireEvent.click(screen.getByRole("button", { name: "AI 智能整理" }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.apiPost).not.toHaveBeenCalledWith(
      "/api/skills/classification/apply",
      expect.anything(),
    );
  });

  it("applies every suggested category, refreshes skills, and confirms success", async () => {
    const preview = [
      { id: 1, name: "LangGraph", current_category: "agent_llm", suggested_category: "agent_llm" },
      { id: 2, name: "Python", current_category: "programming_language", suggested_category: "programming_language" },
      { id: 3, name: "Custom", current_category: "unknown", suggested_category: "other" },
    ];
    api.apiPost.mockImplementation((path: string) => path === "/api/skills/classification/preview"
      ? Promise.resolve(preview)
      : Promise.resolve({}));
    const { client } = renderPage();
    const invalidateQueries = vi.spyOn(client, "invalidateQueries");

    await screen.findByText("LangGraph");
    fireEvent.click(screen.getByRole("button", { name: "AI 智能整理" }));
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

    await waitFor(() => expect(api.apiPost).toHaveBeenCalledWith(
      "/api/skills/classification/apply",
      { assignments: preview.map(({ id, suggested_category: category }) => ({ id, category })) },
    ));
    await waitFor(() => expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["skills"] }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(toast.success).toHaveBeenCalledWith("技能分类已保存");
  });

  it("disables preview actions and submits apply only once while saving", async () => {
    const preview = [{ id: 1, name: "LangGraph", current_category: "agent_llm", suggested_category: "agent_llm" }];
    let resolveApply!: () => void;
    const applyPending = new Promise<void>((resolve) => { resolveApply = resolve; });
    api.apiPost.mockImplementation((path: string) => {
      if (path === "/api/skills/classification/preview") return Promise.resolve(preview);
      if (path === "/api/skills/classification/apply") return applyPending;
      return Promise.resolve({});
    });
    renderPage();

    await screen.findByText("LangGraph");
    fireEvent.click(screen.getByRole("button", { name: "AI 智能整理" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "确认保存" }));

    await waitFor(() => {
      expect((within(dialog).getByRole("button", { name: "取消" }) as HTMLButtonElement).disabled).toBe(true);
      expect((within(dialog).getByRole("button", { name: "确认保存" }) as HTMLButtonElement).disabled).toBe(true);
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "确认保存" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "取消" }));
    expect(api.apiPost.mock.calls.filter(([path]) => path === "/api/skills/classification/apply")).toHaveLength(1);
    expect(screen.getByRole("dialog")).not.toBeNull();

    resolveApply();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
