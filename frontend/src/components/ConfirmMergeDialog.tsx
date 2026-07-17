/** 知识库更新确认弹窗 — 逐项浮现 + 勾选确认 */

import { useState, useEffect } from "react";

interface Change {
  id: string;
  op: string;
  target: string;
  value: Record<string, unknown>;
  conflict: boolean;
}

const TARGET_LABELS: Record<string, string> = {
  profile: "个人信息",
  internship: "工作/实习经历",
  project: "项目经历",
  skill: "专业技能",
};

function formatValue(target: string, value: Record<string, unknown>): string {
  switch (target) {
    case "profile": return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(", ");
    case "internship": return `${value.company || ""} · ${value.position || ""} (${value.start_date || ""} – ${value.end_date || ""})\n${((value.achievements as string[]) || []).join(" | ")}`;
    case "project": return `${value.name || ""}（${value.role || ""}）\n技术栈: ${((value.tech_stack as string[]) || []).join(", ")}\n挑战: ${value.challenge} · 方案: ${value.solution} · 结果: ${value.result}`;
    case "skill": return `${value.name || ""}（${value.proficiency || ""}）`;
    default: return JSON.stringify(value).slice(0, 100);
  }
}

interface Props {
  changes: Change[];
  clearExisting?: boolean;
  onConfirm: (acceptedIds: string[]) => void;
  onCancel: () => void;
}

export default function ConfirmMergeDialog({ changes, clearExisting, onConfirm, onCancel }: Props) {
  const [visible, setVisible] = useState<number>(0);

  // Progressive reveal: show items one by one with 200ms delay
  useEffect(() => {
    setVisible(0);
    if (changes.length === 0) return;
    const timer = setInterval(() => {
      setVisible((prev) => {
        if (prev >= changes.length) { clearInterval(timer); return prev; }
        return prev + 1;
      });
    }, 200);
    return () => clearInterval(timer);
  }, [changes]);

  const [checked, setChecked] = useState<Set<string>>(new Set());
  useEffect(() => {
    setChecked(new Set(changes.filter((c) => !c.conflict).map((c) => c.id)));
  }, [changes]);

  const toggle = (id: string) => {
    const next = new Set(checked);
    next.has(id) ? next.delete(id) : next.add(id);
    setChecked(next);
  };

  const allVisible = visible >= changes.length;
  const showing = allVisible ? changes.length : visible;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-auto">
        {/* Header */}
        <div className="px-5 py-4 border-b border-zinc-200">
          <div className="flex justify-between items-center">
            <h3 className="font-semibold text-base">
              {allVisible ? "确认知识库更新" : "解析中…"}
            </h3>
            <span className="text-xs text-zinc-400">
              {allVisible ? `共 ${changes.length} 项` : `${showing}/${changes.length}`}
            </span>
          </div>
          {clearExisting && (
            <div className="mt-2 text-xs bg-amber-50 border border-amber-200 text-amber-700 rounded-lg px-3 py-2">
              ⚠️ 替换模式：确认后将<b>清空</b>现有实习/项目/技能，仅保留本次导入的数据
            </div>
          )}
          {!allVisible && (
            <div className="mt-2 w-full bg-zinc-100 rounded-full h-1">
              <div className="bg-zinc-800 h-1 rounded-full transition-all duration-300"
                   style={{ width: `${(showing / changes.length) * 100}%` }} />
            </div>
          )}
        </div>

        {/* Items — progressive reveal */}
        <div className="p-4 space-y-2">
          {changes.slice(0, visible).map((ch, i) => (
            <label key={ch.id}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all duration-300 ${
                ch.conflict ? "border-amber-200 bg-amber-50/50" : "border-zinc-200 hover:bg-zinc-50"
              }`}
              style={{ animation: `fadeIn 0.3s ease ${i * 0.05}s both` }}
            >
              <input type="checkbox" checked={checked.has(ch.id)} onChange={() => toggle(ch.id)}
                className="mt-0.5 w-4 h-4 accent-indigo-600" />
              <div className="text-sm flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                    ch.op === "add" ? "bg-green-50 text-green-600" : "bg-indigo-50 text-indigo-600"
                  }`}>
                    {ch.op === "add" ? "新增" : "更新"}
                  </span>
                  <span className="font-medium text-zinc-700">
                    {TARGET_LABELS[ch.target] || ch.target}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 whitespace-pre-wrap leading-relaxed">
                  {formatValue(ch.target, ch.value)}
                </p>
              </div>
            </label>
          ))}
          {!allVisible && changes.length > visible && (
            <div className="text-center py-6 text-zinc-400 text-sm">
              <div className="inline-block w-5 h-5 border-2 border-zinc-300 border-t-zinc-600 rounded-full animate-spin mr-2 align-middle" />
              正在解析第 {visible + 1}/{changes.length} 项…
            </div>
          )}
        </div>

        {/* Footer */}
        {allVisible && (
          <div className="px-5 py-3 border-t border-zinc-200 flex justify-between items-center">
            <button onClick={() => { setChecked(new Set(changes.map((c) => c.id))); }}
              className="text-xs text-zinc-400 hover:text-zinc-600">全选</button>
            <div className="flex gap-2">
              <button onClick={onCancel} className="px-4 py-2 border border-zinc-200 rounded-lg text-sm hover:bg-zinc-50">取消</button>
              <button onClick={() => onConfirm(Array.from(checked))}
                className="px-4 py-2 bg-zinc-800 text-white rounded-lg text-sm hover:bg-zinc-700">
                确认写入所选 ({checked.size})
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
