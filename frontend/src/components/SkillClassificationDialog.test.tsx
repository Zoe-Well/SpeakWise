// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SkillClassificationDialog from "./SkillClassificationDialog";

afterEach(cleanup);

describe("SkillClassificationDialog", () => {
  it("groups suggested categories in the fixed Chinese label order and maps unknown suggestions to other", () => {
    render(
      <SkillClassificationDialog
        preview={[
          { id: 1, name: "LangGraph", current_category: "other", suggested_category: "agent_llm" },
          { id: 2, name: "Python", current_category: "other", suggested_category: "programming_language" },
          { id: 3, name: "Custom", current_category: "other", suggested_category: "unknown" },
        ]}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("heading", { level: 4 }).map((heading) => heading.textContent))
      .toEqual(["编程语言", "Agent 与 LLM 应用", "其他"]);
    expect(screen.queryByRole("heading", { name: "前端与客户端" })).toBeNull();
  });

  it("normalizes unknown suggestions to other only when the user confirms", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <SkillClassificationDialog
        preview={[{ id: 1, name: "Python", current_category: "other", suggested_category: "unknown" }]}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "确认保存" }));
    expect(onConfirm).toHaveBeenCalledWith([{ id: 1, category: "other" }]);
  });

  it("disables both actions while saving", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <SkillClassificationDialog
        preview={[{ id: 1, name: "Python", current_category: "other", suggested_category: "programming_language" }]}
        onCancel={onCancel}
        onConfirm={onConfirm}
        saving
      />,
    );

    const cancel = screen.getByRole("button", { name: "取消" }) as HTMLButtonElement;
    const confirm = screen.getByRole("button", { name: "确认保存" }) as HTMLButtonElement;
    expect(cancel.disabled).toBe(true);
    expect(confirm.disabled).toBe(true);
    fireEvent.click(cancel);
    fireEvent.click(confirm);
    expect(onCancel).not.toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
