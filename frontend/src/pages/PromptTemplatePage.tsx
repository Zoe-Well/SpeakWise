/** 提示词模板管理页面 —— 查看/新建/编辑/删除 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut, apiDelete } from "../lib/api";
import { Plus, Copy, Trash2, Edit3, X, Star } from "lucide-react";
import { useToast } from "../components/Toast";

interface Template {
  id: string;
  scope: string;
  name: string;
  is_builtin: boolean;
  structure_rules?: string;
  style_rules?: string;
}

const SCOPE_CONFIG: Record<string, { label: string; badge: string }> = {
  self_intro: { label: "自我介绍", badge: "bg-indigo-50 text-indigo-600" },
  scenario:   { label: "场景题", badge: "bg-green-50 text-green-600" },
  technical:  { label: "技术题", badge: "bg-blue-50 text-blue-600" },
};

export default function PromptTemplatePage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => apiGet("/api/prompt-templates"),
  });

  // Per-scope defaults
  const { data: defaults = {} } = useQuery<Record<string, string>>({
    queryKey: ["template-defaults"],
    queryFn: () => apiGet("/api/prompt-templates/defaults"),
  });

  const cloneMut = useMutation({
    mutationFn: (t: Template) => apiPost("/api/prompt-templates", {
      scope: t.scope,
      name: `${t.name} (副本)`,
      structure_rules: t.structure_rules,
      style_rules: t.style_rules,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["templates"] }); toast.success("副本已创建"); },
    onError: () => toast.error("复制失败"),
  });

  const setDefaultMut = useMutation({
    mutationFn: ({ scope, template_id }: { scope: string; template_id: string }) =>
      apiPut("/api/prompt-templates/defaults", { scope, template_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["template-defaults"] });
      toast.success("已设为默认");
    },
    onError: () => toast.error("设置失败"),
  });

  const [newTemplateScope, setNewTemplateScope] = useState("self_intro");

  const createMut = useMutation({
    mutationFn: () => apiPost("/api/prompt-templates", { scope: newTemplateScope, name: "新模板" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["templates"] }); toast.success("模板已创建"); },
    onError: () => toast.error("创建失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiDelete(`/api/prompt-templates/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["templates"] }); toast.success("模板已删除"); },
    onError: () => toast.error("删除失败"),
  });

  // Edit modal state
  const [editing, setEditing] = useState<Template | null>(null);
  const [editName, setEditName] = useState("");
  const [editStructure, setEditStructure] = useState("");
  const [editStyle, setEditStyle] = useState("");

  const openEdit = (t: Template) => {
    setEditing(t);
    setEditName(t.name);
    setEditStructure(t.structure_rules || "");
    setEditStyle(t.style_rules || "");
  };

  const saveEdit = async () => {
    if (!editing) return;
    try {
      await apiPut(`/api/prompt-templates/${editing.id}`, {
        name: editName,
        structure_rules: editStructure,
        style_rules: editStyle,
      });
      qc.invalidateQueries({ queryKey: ["templates"] });
      setEditing(null);
      toast.success("模板已保存");
    } catch { toast.error("保存失败"); }
  };

  const selfIntro = templates.filter((t) => t.scope === "self_intro");
  const scenario = templates.filter((t) => t.scope === "scenario");
  const technical = templates.filter((t) => t.scope === "technical");

  const SCOPE_CONFIG: Record<string, { label: string; badge: string; desc: string }> = {
    self_intro: { label: "自我介绍", badge: "bg-indigo-50 text-indigo-600", desc: "自我介绍" },
    scenario: { label: "场景题", badge: "bg-green-50 text-green-600", desc: "场景题" },
    technical: { label: "技术题", badge: "bg-blue-50 text-blue-600", desc: "技术题" },
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">提示词模板管理</h2>
      <p className="text-sm text-zinc-500 mb-6">集中管理自我介绍、场景题与技术题的回答结构/风格。内置模板不可编辑，可复制副本后自定义。</p>

      {[
        { label: "自我介绍模板", items: selfIntro, scopeBadge: "bg-indigo-50 text-indigo-600", scope: "self_intro" as const },
        { label: "场景题模板", items: scenario, scopeBadge: "bg-green-50 text-green-600", scope: "scenario" as const },
        { label: "技术题模板", items: technical, scopeBadge: "bg-blue-50 text-blue-600", scope: "technical" as const },
      ].map((group) => (
        <section key={group.label} className="mb-5">
          <h3 className="text-sm font-semibold text-zinc-500 mb-2">{group.label}</h3>
          {group.items.map((t) => (
            <div key={t.id} className="bg-white border border-zinc-200 rounded-xl p-4 mb-3">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium text-sm">
                    {t.name}
                    <span className={`text-xs px-1.5 py-0.5 rounded ml-2 ${group.scopeBadge}`}>
                      {SCOPE_CONFIG[t.scope]?.label || t.scope}
                    </span>
                    {t.is_builtin && (
                      <span className="text-xs px-1.5 py-0.5 rounded ml-1 bg-zinc-100 text-zinc-500">内置</span>
                    )}
                    {defaults[t.scope] === t.id && (
                      <span className="text-xs px-1.5 py-0.5 rounded ml-1 bg-amber-50 text-amber-600 inline-flex items-center gap-0.5">
                        <Star size={10} /> 当前默认
                      </span>
                    )}
                  </p>
                  {(t.structure_rules || t.style_rules) && (
                    <p className="text-xs text-zinc-400 mt-2 font-mono">
                      {t.structure_rules && `结构: ${t.structure_rules.slice(0, 80)}${t.structure_rules.length > 80 ? "…" : ""}`}
                      {t.style_rules && ` | 风格: ${t.style_rules.slice(0, 60)}${t.style_rules.length > 60 ? "…" : ""}`}
                    </p>
                  )}
                </div>
                <div className="flex gap-1">
                  {defaults[t.scope] !== t.id && (
                    <button
                      onClick={() => setDefaultMut.mutate({ scope: t.scope, template_id: t.id })}
                      className="text-xs border border-amber-200 rounded-lg px-2 py-1 hover:bg-amber-50 text-amber-600 flex items-center gap-1"
                    >
                      <Star size={11} /> 设为默认
                    </button>
                  )}
                  {t.is_builtin ? (
                    <button
                      onClick={() => cloneMut.mutate(t)}
                      className="text-xs border border-zinc-200 rounded-lg px-2 py-1 hover:bg-zinc-50 flex items-center gap-1"
                    >
                      <Copy size={11} /> 复制副本
                    </button>
                  ) : (
                    <button
                      onClick={() => openEdit(t)}
                      className="text-xs border border-zinc-200 rounded-lg px-2 py-1 hover:bg-zinc-50 flex items-center gap-1"
                    >
                      <Edit3 size={11} /> 编辑
                    </button>
                  )}
                  {!t.is_builtin && (
                    <button
                      onClick={() => { if (confirm("删除此模板？")) deleteMut.mutate(t.id); }}
                      className="text-xs border border-zinc-200 rounded-lg px-2 py-1 hover:bg-red-50 text-zinc-400 hover:text-red-500"
                    >
                      <Trash2 size={11} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </section>
      ))}

      {/* New template with scope selector */}
      <div className="flex gap-2">
        <select
          value={newTemplateScope}
          onChange={(e) => setNewTemplateScope(e.target.value)}
          className="text-sm border border-zinc-200 rounded-lg px-2.5 py-2.5 bg-white"
        >
          <option value="self_intro">自我介绍模板</option>
          <option value="scenario">场景题模板</option>
          <option value="technical">技术题模板</option>
        </select>
        <button
          onClick={() => createMut.mutate()}
          className="flex-1 py-2.5 border border-zinc-200 rounded-lg text-sm font-medium hover:bg-zinc-50 flex items-center justify-center gap-1"
        >
          <Plus size={14} /> 新建模板
        </button>
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[85vh] overflow-auto">
            <div className="px-5 py-4 border-b border-zinc-200 flex items-center justify-between">
              <h3 className="font-semibold">编辑模板: {editing.name}</h3>
              <button onClick={() => setEditing(null)} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1">名称</label>
                <input value={editName} onChange={(e) => setEditName(e.target.value)}
                  className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">
                  结构规则 (JSON) <span className="text-zinc-400 font-normal">— 如 sections / length / step_min</span>
                </label>
                <textarea rows={4} value={editStructure} onChange={(e) => setEditStructure(e.target.value)}
                  className="w-full border border-zinc-200 rounded-lg p-3 text-sm font-mono"
                  placeholder='{"sections":["概述","技能+证据","业务匹配"],"length":"300-400"}' />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">
                  风格规则 (JSON) <span className="text-zinc-400 font-normal">— 如 tone / fallback_angle</span>
                </label>
                <textarea rows={3} value={editStyle} onChange={(e) => setEditStyle(e.target.value)}
                  className="w-full border border-zinc-200 rounded-lg p-3 text-sm font-mono"
                  placeholder='{"tone":"专业自然","fallback_angle":"学习角度"}' />
              </div>
              {editing.is_builtin && (
                <p className="text-xs text-amber-600 bg-amber-50 rounded-lg p-2">
                  ⚠ 这是内置模板，保存后将自动生成副本（copy-on-edit），原件不变。
                </p>
              )}
            </div>
            <div className="px-5 py-3 border-t border-zinc-200 flex justify-end gap-2">
              <button onClick={() => setEditing(null)}
                className="px-4 py-2 border border-zinc-200 rounded-lg text-sm hover:bg-zinc-50">取消</button>
              <button onClick={saveEdit}
                className="px-4 py-2 bg-zinc-800 text-white rounded-lg text-sm hover:bg-zinc-700">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
