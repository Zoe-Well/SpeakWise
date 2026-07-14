/** 会话选择器 — 下拉切换 + 新建（含模式选择） + 单个删除 + 批量删除 */

import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete } from "../lib/api";
import { Plus, Trash2, CheckSquare, X, ChevronDown } from "lucide-react";
import { useToast } from "./Toast";

interface Session {
  id: number;
  name: string;
  mode?: string;
  updated_at: string;
}

const MODE_LABELS: Record<string, { icon: string; label: string; color: string }> = {
  normal:    { icon: "💬", label: "普通", color: "bg-zinc-100 text-zinc-600" },
  interview: { icon: "🎯", label: "面试", color: "bg-indigo-50 text-indigo-600" },
};

interface Props {
  activeId: number | null;
  onSelect: (id: number) => void;
}

export default function SessionSelector({ activeId, onSelect }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: sessions = [] } = useQuery<Session[]>({
    queryKey: ["sessions"],
    queryFn: () => apiGet("/api/sessions"),
    refetchInterval: 5000,
  });

  const [batchMode, setBatchMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [newMode, setNewMode] = useState("interview");
  const [showNewDialog, setShowNewDialog] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Click-outside to dismiss
  useEffect(() => {
    if (!showNewDialog) return;
    const h = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) setShowNewDialog(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [showNewDialog]);

  const activeSession = sessions.find(s => s.id === activeId);
  const activeMode = activeSession?.mode || "normal";

  const createMut = useMutation({
    mutationFn: ({ name, mode }: { name: string; mode: string }) =>
      apiPost("/api/sessions", { name, mode }) as Promise<Session>,
    onSuccess: (s) => { qc.invalidateQueries({ queryKey: ["sessions"] }); onSelect(s.id); setShowNewDialog(false); toast.success("会话已创建"); },
    onError: () => toast.error("创建失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/sessions/${id}`) as Promise<void>,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sessions"] }); toast.success("会话已删除"); },
    onError: () => toast.error("删除失败"),
  });

  const batchDelete = async () => {
    if (selected.size === 0) return;
    if (!confirm(`删除所选 ${selected.size} 个会话及全部消息？`)) return;
    try {
      await apiPost("/api/sessions/batch-delete", { ids: Array.from(selected) });
      setSelected(new Set());
      setBatchMode(false);
      qc.invalidateQueries({ queryKey: ["sessions"] });
      qc.invalidateQueries({ queryKey: ["messages"] });
      toast.success(`已删除 ${selected.size} 个会话`);
    } catch { toast.error("批量删除失败"); }
  };

  const toggleSelect = (id: number) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  };

  return (
    <div className="flex items-center gap-2 w-full">
      {!batchMode ? (
        <>
          {/* Mode badge */}
          {activeSession && (
            <span className={`text-xs px-2 py-1 rounded-md font-medium flex-shrink-0 ${MODE_LABELS[activeMode]?.color || MODE_LABELS.normal.color}`}>
              {MODE_LABELS[activeMode]?.icon} {MODE_LABELS[activeMode]?.label}
            </span>
          )}
          {sessions.length === 0 ? (
            <button onClick={() => setShowNewDialog(true)}
              className="flex-1 text-sm border border-indigo-200 bg-indigo-50 text-indigo-600 rounded-lg px-3 py-1.5 font-medium hover:bg-indigo-100 text-left">
              🎯 创建第一个会话
            </button>
          ) : (
            <select
              value={activeId ?? ""}
              onChange={(e) => onSelect(Number(e.target.value))}
              className="flex-1 text-sm border border-zinc-200 rounded-lg px-2.5 py-1.5 bg-white"
            >
              {sessions.map((s) => {
                const m = MODE_LABELS[s.mode || "normal"];
                return (
                  <option key={s.id} value={s.id}>{m?.icon} {s.name}</option>
                );
              })}
            </select>
          )}

          {/* New session with mode choice */}
          <div className="relative">
            <button onClick={() => setShowNewDialog(!showNewDialog)}
              className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-500" title="新建会话"><Plus size={16} /></button>
            {showNewDialog && (
              <div ref={dialogRef} className="absolute top-full right-0 mt-1 bg-white border border-zinc-200 rounded-xl shadow-lg p-3 w-56 z-20">
                <p className="text-xs font-medium text-zinc-500 mb-2">新建会话</p>
                <div className="flex gap-1.5 mb-2">
                  {(["interview", "normal"] as const).map(m => (
                    <button key={m}
                      onClick={() => setNewMode(m)}
                      className={`flex-1 text-xs px-2 py-1.5 rounded-lg border font-medium transition-colors ${
                        newMode === m
                          ? "bg-indigo-50 border-indigo-200 text-indigo-600"
                          : "bg-white border-zinc-200 text-zinc-500 hover:bg-zinc-50"
                      }`}>
                      {MODE_LABELS[m].icon} {MODE_LABELS[m].label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-zinc-400 mb-3 leading-relaxed">
                  {newMode === "interview"
                    ? "自动识别意图，注入简历/JD/素材，使用提示词模板"
                    : "简洁问答模式，不自动注入知识库和模板"}
                </p>
                <button
                  onClick={() => createMut.mutate({ name: `会话 ${sessions.length + 1}`, mode: newMode })}
                  className="w-full text-xs px-3 py-1.5 bg-zinc-800 text-white rounded-lg font-medium hover:bg-zinc-700"
                >
                  创建 {MODE_LABELS[newMode].label}会话
                </button>
              </div>
            )}
          </div>
          {activeId && sessions.length > 1 && (
            <button onClick={() => { if (confirm("删除此会话及全部消息？")) deleteMut.mutate(activeId); }}
              className="p-1.5 rounded-lg hover:bg-red-50 text-zinc-400 hover:text-red-500" title="删除当前会话"><Trash2 size={14} /></button>
          )}
          <button onClick={() => setBatchMode(true)}
            className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400" title="批量管理"><CheckSquare size={14} /></button>
        </>
      ) : (
        <>
          <div className="flex-1 max-h-40 overflow-auto border border-zinc-200 rounded-lg bg-white p-1">
            {sessions.map((s) => (
              <label key={s.id} className="flex items-center gap-2 px-2 py-1.5 hover:bg-zinc-50 rounded cursor-pointer text-sm">
                <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggleSelect(s.id)}
                  className="w-3.5 h-3.5 accent-indigo-600" />
                <span className={s.id === activeId ? "font-medium" : ""}>{s.name}</span>
              </label>
            ))}
          </div>
          <button onClick={batchDelete} disabled={selected.size === 0}
            className="p-1.5 rounded-lg hover:bg-red-50 text-red-400 disabled:opacity-30 disabled:cursor-not-allowed"
            title={`删除所选 (${selected.size})`}><Trash2 size={16} /></button>
          <button onClick={() => { setBatchMode(false); setSelected(new Set()); }}
            className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400" title="取消"><X size={16} /></button>
        </>
      )}
    </div>
  );
}
