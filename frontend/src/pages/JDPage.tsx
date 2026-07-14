/** 岗位上下文页面 —— JD 输入 + 解析 + 文档导入 + 素材附加 */

import { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut, apiDelete } from "../lib/api";
import DocumentImport from "../components/DocumentImport";

interface JDAnalysis {
  parse_status: string;
  core_skills: string[];
  duties: string[];
  culture_values: string[];
  error?: string;
  raw_text?: string;
}

export default function JDPage({ activeSessionId }: { activeSessionId: number | null }) {
  const [jdText, setJdText] = useState("");
  const [result, setResult] = useState<JDAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const qc = useQueryClient();

  const { data: jdDocs = [] } = useQuery<{id:number;filename:string}[]>({
    queryKey: ["documents","jd"],
    queryFn: () => apiGet("/api/documents?scope=jd"),
  });

  // Load saved JD on mount
  const { data: savedJd } = useQuery<{found:boolean;jd_context_id?:number;raw_text?:string;core_skills?:string[];duties?:string[];culture_values?:string[]}>({
    queryKey: ["jd-latest"],
    queryFn: () => apiGet("/api/jd/latest"),
  });

  // Debounced save after chip edits
  const saveTimer = useRef<ReturnType<typeof setTimeout>>();
  const persistJD = (updated: JDAnalysis) => {
    if (!savedJd?.jd_context_id) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      apiPut(`/api/jd/${savedJd.jd_context_id}`, {
        core_skills: updated.core_skills,
        duties: updated.duties,
        culture_values: updated.culture_values,
      });
    }, 800);
  };
  useEffect(() => {
    if (savedJd?.found) {
      setJdText(savedJd.raw_text || "");
      setResult({
        parse_status: "success",
        core_skills: savedJd.core_skills || [],
        duties: savedJd.duties || [],
        culture_values: savedJd.culture_values || [],
      });
    }
  }, [savedJd]);

  const analyze = async () => {
    if (!jdText.trim()) return;
    setLoading(true);
    try {
      const body: Record<string, unknown> = { raw_text: jdText };
      if (activeSessionId) body.session_id = activeSessionId;
      const data = await apiPost<JDAnalysis>("/api/jd/analyze", body);
      setResult(data);
      qc.invalidateQueries({ queryKey: ["jd-latest"] });
    } catch {
      setResult({ parse_status: "failed", core_skills: [], duties: [], culture_values: [], error: "网络错误" });
    }
    setLoading(false);
  };

  // When JD document is imported (parse mode), refresh doc list
  const handleDocParsed = (result: Record<string, unknown>) => {
    // If document was parsed and has extracted text, fill the textarea
    const text = result.extracted_text as string | undefined;
    if (text) {
      setJdText(text);
      // Auto-analyze after filling
      setTimeout(() => analyzeWithText(text), 300);
    }
    qc.invalidateQueries({ queryKey: ["documents","jd"] });
  };

  const analyzeWithText = async (text: string) => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const body: Record<string, unknown> = { raw_text: text };
      if (activeSessionId) body.session_id = activeSessionId;
      const data = await apiPost<JDAnalysis>("/api/jd/analyze", body);
      setResult(data);
      qc.invalidateQueries({ queryKey: ["jd-latest"] });
    } catch {
      setResult({ parse_status: "failed", core_skills: [], duties: [], culture_values: [], error: "网络错误" });
    }
    setLoading(false);
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">💼 岗位上下文</h2>
      <p className="text-sm text-zinc-500 mb-6">粘贴岗位描述或导入 JD 文档——自动提取文本并解析核心技能 / 职责 / 价值观。</p>

      {/* 文档导入 */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
        <h3 className="font-semibold mb-3">📥 文档导入</h3>
        <div className="flex gap-4 mb-3">
          <div className="flex-1">
            <DocumentImport scope="jd" usage="parse" onSuccess={handleDocParsed} />
          </div>
          <div className="flex-1">
            <DocumentImport scope="jd" usage="attach" onSuccess={() => qc.invalidateQueries({ queryKey: ["documents","jd"] })} />
          </div>
        </div>
        {jdDocs.length > 0 && (
          <div className="flex gap-2 flex-wrap">
            {jdDocs.map((d) => (
              <span key={d.id} className="text-xs bg-zinc-100 border border-zinc-200 rounded-lg px-2.5 py-1.5 inline-flex items-center gap-1">
                📎 {d.filename}
                <button onClick={() => { if(confirm("删除此文档？")) { apiDelete(`/api/documents/${d.id}`).then(() => qc.invalidateQueries({ queryKey: ["documents","jd"] })); } }}
                  className="text-zinc-400 hover:text-red-500 font-bold ml-1">×</button>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* JD 文本输入 */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
        <h3 className="font-semibold mb-3">📝 岗位描述</h3>
        <textarea
          rows={7}
          className="w-full border border-zinc-200 rounded-lg p-3 text-sm"
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          placeholder="在此粘贴 JD 文本，或通过上方「文档导入」上传 TXT/PDF/DOCX…"
        />
        <div className="flex gap-3 mt-3">
          <button
            onClick={analyze}
            disabled={loading}
            className="px-4 py-2 bg-zinc-800 text-white text-sm rounded-lg font-medium hover:bg-zinc-700 disabled:opacity-50"
          >
            {loading ? "解析中…" : "解析岗位"}
          </button>
        </div>
      </section>

      {/* 解析结果 */}
      {result && (
        <section className="bg-white border border-zinc-200 rounded-xl p-5">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-semibold">✅ 解析结果</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              result.parse_status === "success" ? "bg-green-50 text-green-600" : "bg-amber-50 text-amber-600"
            }`}>
              {result.parse_status === "success" ? "解析成功" : "解析失败"}
            </span>
          </div>
          {result.parse_status === "success" ? (
            <>
              <ChipGroup label="核心技能要求" items={result.core_skills} color="indigo"
                onRemove={(i) => { const next = {...result, core_skills: result.core_skills.filter((_,j) => j !== i)}; setResult(next); persistJD(next); }}
                onAdd={(v) => { const next = {...result, core_skills: [...result.core_skills, v]}; setResult(next); persistJD(next); }} />
              <ChipGroup label="主要岗位职责" items={result.duties} color="zinc"
                onRemove={(i) => { const next = {...result, duties: result.duties.filter((_,j) => j !== i)}; setResult(next); persistJD(next); }}
                onAdd={(v) => { const next = {...result, duties: [...result.duties, v]}; setResult(next); persistJD(next); }} />
              <ChipGroup label="公司价值观 / 方向" items={result.culture_values} color="green"
                onRemove={(i) => { const next = {...result, culture_values: result.culture_values.filter((_,j) => j !== i)}; setResult(next); persistJD(next); }}
                onAdd={(v) => { const next = {...result, culture_values: [...result.culture_values, v]}; setResult(next); persistJD(next); }} />
            </>
          ) : (
            <p className="text-sm text-amber-600 bg-amber-50 rounded-lg p-3">
              ⚠ {result.error || "解析失败"}——生成自我介绍时将自动降级为通用面试模式。
            </p>
          )}
        </section>
      )}
    </div>
  );
}

function ChipGroup({ label, items, color, onRemove, onAdd }: {
  label: string; items: string[]; color: string;
  onRemove?: (idx: number) => void;
  onAdd?: (value: string) => void;
}) {
  if (!items.length && !onAdd) return null;
  const colorMap: Record<string, string> = {
    indigo: "bg-indigo-50 text-indigo-600",
    green: "bg-green-50 text-green-600",
    zinc: "bg-zinc-100 text-zinc-700",
  };
  const [adding, setAdding] = useState(false);
  const [newVal, setNewVal] = useState("");

  const handleAdd = () => {
    if (newVal.trim() && onAdd) {
      onAdd(newVal.trim());
      setNewVal("");
      setAdding(false);
    }
  };

  return (
    <div className="mb-3">
      <p className="text-xs font-medium text-zinc-500 mb-1.5">{label}</p>
      <div className="flex flex-wrap gap-2 items-center">
        {items.map((item, i) => (
          <span key={i} className={`text-xs px-2.5 py-1 rounded-lg inline-flex items-center gap-1 ${colorMap[color] || colorMap.zinc}`}>
            {item}
            {onRemove && (
              <button onClick={() => onRemove(i)}
                className="ml-0.5 text-zinc-400 hover:text-red-500 font-bold leading-none">&times;</button>
            )}
          </span>
        ))}
        {onAdd && !adding && (
          <button onClick={() => setAdding(true)}
            className="text-xs px-2 py-1 rounded-lg border border-dashed border-zinc-300 text-zinc-400 hover:border-zinc-400 hover:text-zinc-600">
            + 添加
          </button>
        )}
        {onAdd && adding && (
          <input
            autoFocus
            value={newVal}
            onChange={(e) => setNewVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleAdd(); if (e.key === "Escape") setAdding(false); }}
            onBlur={() => { if (!newVal.trim()) setAdding(false); else handleAdd(); }}
            className="text-xs border border-zinc-300 rounded-lg px-2 py-1 w-24 focus:outline-none focus:ring-1 focus:ring-indigo-300"
            placeholder="输入后回车"
          />
        )}
      </div>
    </div>
  );
}
