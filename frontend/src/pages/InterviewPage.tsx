/** 模拟面试页面 — 含会话管理 */

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { consumeSSE, apiGet, apiPost, apiDelete } from "../lib/api";
import MarkdownRenderer from "../components/MarkdownRenderer";
import ApiKeyRequiredDialog from "../components/ApiKeyRequiredDialog";
import { useLLMStatus } from "../lib/useLLMStatus";
import { useToast } from "../components/Toast";
import { Play, Square, FileText, Copy, Send, Loader2, Plus, Trash2 } from "lucide-react";

type Phase = "idle" | "streaming" | "waiting" | "reviewed" | "done";

interface MsgItem {
  role: "interviewer" | "user";
  content: string;
  type?: string;
}

interface SessionItem {
  id: number; name: string; mode: string; updated_at: string;
}

export default function InterviewPage({ isActive }: { isActive: boolean }) {
  const toast = useToast();
  const qc = useQueryClient();
  const { isConfigured: llmConfigured } = useLLMStatus();
  const [showApiKeyDialog, setShowApiKeyDialog] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<MsgItem[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [userInput, setUserInput] = useState("");
  const [showInput, setShowInput] = useState(false);
  const [summary, setSummary] = useState("");
  const [showSummary, setShowSummary] = useState(false);
  const [ending, setEnding] = useState(false); // prevent double-end
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── Session management ──
  const { data: sessions = [] } = useQuery<SessionItem[]>({
    queryKey: ["sessions"],
    queryFn: () => apiGet("/api/sessions"),
  });
  const mockSessions = sessions.filter(s => s.mode === "mock");

  const handleSelectSession = useCallback(async (sid: number) => {
    setSessionId(sid);
    setShowSummary(false);
    setStreamingText("");
    setEnding(false);

    try {
      const msgs = await apiGet<{id:number;role:string;content:string;type:string}[]>(`/api/sessions/${sid}/messages`);
      // Convert to MsgItem and determine phase from last message
      const items: MsgItem[] = [];
      for (const m of msgs) {
        if (m.type === "interview_question") {
          items.push({ role: "interviewer", content: m.content, type: "question" });
        } else if (m.type === "interview_eval") {
          items.push({ role: "interviewer", content: m.content, type: "eval" });
        } else if (m.type === "interview_reference") {
          items.push({ role: "interviewer", content: m.content, type: "reference" });
        } else if (m.type === "interview_summary") {
          setSummary(m.content);
          setPhase("done");
        } else if (m.role === "user") {
          items.push({ role: "user", content: m.content });
        }
      }
      setMessages(items);

      // Determine phase
      const last = items[items.length - 1];
      if (last?.type === "question") {
        setPhase("waiting");
      } else if (last?.type === "eval" || last?.type === "reference") {
        setPhase("reviewed");
      } else if (msgs.some(m => m.type === "interview_summary")) {
        setPhase("done");
      } else {
        setPhase("idle");
      }
    } catch {
      toast.error("加载会话失败");
      setPhase("idle");
    }
  }, [toast]);

  const handleNewSession = useCallback(async () => {
    setSessionId(null);
    setMessages([]);
    setPhase("idle");
    setStreamingText("");
    setSummary("");
    setShowSummary(false);
    setEnding(false);
    setShowInput(false);
  }, []);

  const handleDeleteSession = useCallback(async (sid: number) => {
    if (!confirm("删除此模拟面试记录？")) return;
    try {
      await apiDelete(`/api/sessions/${sid}`);
      qc.invalidateQueries({ queryKey: ["sessions"] });
      if (sid === sessionId) handleNewSession();
      toast.success("已删除");
    } catch { toast.error("删除失败"); }
  }, [sessionId, qc, toast, handleNewSession]);

  // Auto-scroll
  useEffect(() => {
    if (!isActive) return;
    const frameId = requestAnimationFrame(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "instant" });
    });
    return () => cancelAnimationFrame(frameId);
  }, [messages, streamingText, isActive]);

  // ── Start interview ──
  const handleStart = useCallback(async () => {
    if (!llmConfigured) { setShowApiKeyDialog(true); return; }
    setPhase("streaming");
    setMessages([]);
    setStreamingText("");
    setShowInput(false);
    setSummary("");
    setShowSummary(false);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    let full = "";
    try {
      await consumeSSE("/api/interview/start", {}, (event, data) => {
        if (event === "token") { full += data; setStreamingText(full); }
        else if (event === "done") {
          const p = JSON.parse(data);
          setSessionId(p.session_id);
          qc.invalidateQueries({ queryKey: ["sessions"] });
          setMessages([{ role: "interviewer", content: p.content, type: "question" }]);
          setStreamingText("");
          setPhase("waiting");
        } else if (event === "error") { toast.error(data || "启动失败"); setPhase("idle"); }
      }, ctrl.signal);
    } catch { setPhase("idle"); }
  }, [toast, qc, llmConfigured]);

  // ── User action: answer / reference / skip ──
  const handleAction = useCallback(async (action: "answer" | "reference" | "skip", answer?: string) => {
    if (!sessionId) return;
    setPhase("streaming");
    setShowInput(false);
    setStreamingText("");

    if (action === "answer" && answer) {
      setMessages(prev => [...prev, { role: "user", content: answer }]);
    }

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    let full = "";
    try {
      await consumeSSE("/api/interview/respond", { session_id: sessionId, action, answer: answer || "" },
        (event, data) => {
          if (event === "token") { full += data; setStreamingText(full); }
          else if (event === "done") {
            const p = JSON.parse(data);
            const t = action === "answer" ? "eval" : action === "reference" ? "reference" : "question";
            setMessages(prev => [...prev, { role: "interviewer", content: p.content, type: t }]);
            setStreamingText("");
            setPhase(action === "skip" ? "waiting" : "reviewed");
          } else if (event === "error") { toast.error(data || "请求失败"); setPhase("waiting"); }
        }, ctrl.signal);
    } catch { setPhase("waiting"); }
  }, [sessionId, toast]);

  // ── Next question ──
  const handleNext = useCallback(async () => {
    if (!sessionId) return;
    setPhase("streaming");
    setStreamingText("");

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    let full = "";
    try {
      await consumeSSE("/api/interview/next", { session_id: sessionId }, (event, data) => {
        if (event === "token") { full += data; setStreamingText(full); }
        else if (event === "done") {
          const p = JSON.parse(data);
          setMessages(prev => [...prev, { role: "interviewer", content: p.content, type: "question" }]);
          setStreamingText("");
          setPhase("waiting");
        } else if (event === "error") { toast.error(data || "请求失败"); setPhase("reviewed"); }
      }, ctrl.signal);
    } catch { setPhase("reviewed"); }
  }, [sessionId, toast]);

  // ── End interview ──
  const handleEnd = useCallback(async () => {
    if (!sessionId || ending) return;
    setEnding(true);
    setPhase("streaming");
    setStreamingText("");

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    let full = "";
    try {
      await consumeSSE("/api/interview/summary", { session_id: sessionId }, (event, data) => {
        if (event === "token") { full += data; setStreamingText(full); }
        else if (event === "done") {
          const p = JSON.parse(data);
          setSummary(p.content || "");
          setStreamingText("");
          setPhase("done");
          setShowSummary(true);
          setEnding(false);
        } else if (event === "error") {
          toast.error(data || "汇总失败");
          setPhase("reviewed");
          setEnding(false);
        }
      }, ctrl.signal);
    } catch {
      setPhase("reviewed");
      setEnding(false);
    }
  }, [sessionId, ending, toast]);

  const handleSubmitAnswer = () => {
    if (!userInput.trim()) return;
    handleAction("answer", userInput.trim());
    setUserInput("");
  };

  const isLoading = phase === "streaming";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-3 border-b border-zinc-200 bg-white flex items-center gap-3 flex-shrink-0 flex-wrap">
        <h2 className="font-semibold text-base">🎤 模拟面试</h2>

        {/* Session selector */}
        <select
          value={sessionId || ""}
          onChange={e => { const id = parseInt(e.target.value); if (id) handleSelectSession(id); }}
          className="text-xs border border-zinc-200 rounded-lg px-2 py-1.5 max-w-[180px]"
        >
          <option value="">新建面试…</option>
          {mockSessions.map(s => (
            <option key={s.id} value={s.id}>{s.name} ({s.updated_at?.slice(0,10)})</option>
          ))}
        </select>
        <button onClick={handleNewSession}
          className="text-xs border border-zinc-200 rounded-lg px-2 py-1.5 hover:bg-zinc-50 flex-shrink-0">
          <Plus size={13} className="inline mr-1" />新建
        </button>
        {sessionId && (
          <button onClick={() => handleDeleteSession(sessionId)}
            className="text-xs border border-red-200 text-red-500 rounded-lg px-2 py-1.5 hover:bg-red-50 flex-shrink-0">
            <Trash2 size={13} />
          </button>
        )}

        <span className="text-xs text-zinc-400">
          {phase === "idle" && "点击开始，AI 将依次提问"}
          {phase === "streaming" && "正在生成…"}
          {phase === "waiting" && "请选择回应方式"}
          {phase === "reviewed" && "评审完成，点击下一题"}
          {phase === "done" && "面试结束"}
        </span>
        <span className="flex-1" />
        {phase === "idle" && (
          <button onClick={handleStart}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg font-medium hover:bg-indigo-700">
            <Play size={15} /> 开始面试
          </button>
        )}
        {(phase === "streaming" || phase === "waiting" || phase === "reviewed") && (
          <button onClick={handleEnd} disabled={ending}
            className="flex items-center gap-2 px-3 py-1.5 border border-red-200 text-red-600 text-sm rounded-lg hover:bg-red-50 disabled:opacity-50">
            <Square size={14} /> 结束面试
          </button>
        )}
        {phase === "done" && (
          <button onClick={() => setShowSummary(true)}
            className="flex items-center gap-2 px-3 py-1.5 border border-zinc-200 text-sm rounded-lg hover:bg-zinc-50">
            <FileText size={14} /> 查看汇总
          </button>
        )}
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
              {msg.role === "interviewer" && (
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 text-sm">🎤</div>
              )}
              <div className={`max-w-[85%] ${msg.role === "user" ? "order-first" : ""}`}>
                <div className={`rounded-2xl px-4 py-3 text-sm ${
                  msg.role === "user" ? "bg-indigo-600 text-white rounded-br-md"
                    : msg.type === "question" ? "bg-white border border-indigo-200 rounded-bl-md shadow-sm"
                    : msg.type === "eval" ? "bg-white border border-amber-200 rounded-bl-md shadow-sm"
                    : "bg-white border border-zinc-200 rounded-bl-md shadow-sm"
                }`}>
                  <MarkdownRenderer content={msg.content} />
                </div>
                {msg.type === "question" && i === messages.length - 1 && phase === "waiting" && (
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => { setShowInput(true); setTimeout(() => inputRef.current?.focus(), 100); }}
                      className="text-xs px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100">✏️ 输入回答</button>
                    <button onClick={() => handleAction("reference")}
                      className="text-xs px-3 py-1.5 rounded-lg bg-zinc-50 text-zinc-600 border border-zinc-200 hover:bg-zinc-100">📋 参考答案</button>
                    <button onClick={() => handleAction("skip")}
                      className="text-xs px-3 py-1.5 rounded-lg bg-zinc-50 text-zinc-500 border border-zinc-200 hover:bg-zinc-100">⏭ 忽略换题</button>
                  </div>
                )}
                {(msg.type === "eval" || msg.type === "reference") && i === messages.length - 1 && phase === "reviewed" && (
                  <div className="mt-2">
                    <button onClick={handleNext}
                      className="text-xs px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 font-medium">下一题 →</button>
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center flex-shrink-0 text-sm text-white">👤</div>
              )}
            </div>
          ))}

          {/* Streaming indicator */}
          {isLoading && streamingText && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 text-sm">🎤</div>
              <div className="bg-white border border-zinc-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm max-w-[85%]">
                <MarkdownRenderer content={streamingText} streaming />
              </div>
            </div>
          )}
          {isLoading && !streamingText && (
            <div className="flex items-center gap-3 text-zinc-400 text-sm py-8 justify-center">
              <Loader2 size={16} className="animate-spin" /> 正在思考…
            </div>
          )}

          {/* Input area */}
          {showInput && phase === "waiting" && (
            <div className="flex gap-3 justify-end">
              <div className="max-w-[75%] w-full">
                <textarea ref={inputRef} value={userInput} onChange={e => setUserInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmitAnswer(); } }}
                  placeholder="输入你的回答…（Enter 发送，Shift+Enter 换行）"
                  className="w-full border border-zinc-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300" rows={3} />
                <div className="flex justify-end mt-2 gap-2">
                  <button onClick={() => setShowInput(false)} className="text-xs px-3 py-1.5 text-zinc-500 hover:text-zinc-700">取消</button>
                  <button onClick={handleSubmitAnswer} disabled={!userInput.trim()}
                    className="flex items-center gap-1 text-xs px-4 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"><Send size={12} /> 发送</button>
                </div>
              </div>
            </div>
          )}

          {/* Done state — show summary inline + modal */}
          {phase === "done" && summary && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 text-sm">🎤</div>
              <div className="bg-white border border-green-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm max-w-[85%]">
                <p className="text-xs text-green-600 font-medium mb-2">✅ 面试汇总已生成</p>
                <div className="max-h-[500px] overflow-auto">
                  <MarkdownRenderer content={summary} />
                </div>
                <div className="mt-3 flex gap-2">
                  <button onClick={() => { navigator.clipboard?.writeText(summary); toast.success("已复制"); }}
                    className="text-xs border border-zinc-200 rounded-lg px-3 py-1.5 hover:bg-zinc-50 flex items-center gap-1"><Copy size={12} /> 复制</button>
                  <button onClick={() => setShowSummary(true)}
                    className="text-xs border border-zinc-200 rounded-lg px-3 py-1.5 hover:bg-zinc-50">🔍 大屏查看</button>
                </div>
              </div>
            </div>
          )}

          {/* Idle prompt */}
          {phase === "idle" && (
            <div className="text-center py-20">
              <p className="text-4xl mb-4">🎤</p>
              <p className="text-zinc-500 text-sm mb-6">
                AI 将根据你的简历和岗位要求，依次提出面试问题。<br />
                你可以选择文字回答（获得评审）、查看参考答案、或跳过换题。
              </p>
              <button onClick={handleStart}
                className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors text-sm">
                <Play size={16} className="inline mr-2" />开始模拟面试
              </button>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Full-screen summary modal */}
      {showSummary && summary && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowSummary(false)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-auto m-4" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-zinc-200 px-6 py-4 flex items-center justify-between">
              <h3 className="font-semibold">📋 面试汇总</h3>
              <button onClick={() => setShowSummary(false)} className="text-xs border border-zinc-200 rounded-lg px-3 py-1.5 hover:bg-zinc-50">关闭</button>
            </div>
            <div className="p-6"><MarkdownRenderer content={summary} /></div>
          </div>
        </div>
      )}

      <ApiKeyRequiredDialog
        open={showApiKeyDialog}
        onClose={() => setShowApiKeyDialog(false)}
        featureName="模拟面试"
        highlight="llm"
      />
    </div>
  );
}
