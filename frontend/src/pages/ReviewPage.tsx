/** 简历评审页面 —— 简历评审 + 岗位解析 */

import { useState, useRef, useCallback } from "react";
import { consumeSSE } from "../lib/api";
import MarkdownRenderer from "../components/MarkdownRenderer";
import ApiKeyRequiredDialog from "../components/ApiKeyRequiredDialog";
import { useLLMStatus } from "../lib/useLLMStatus";
import { useToast } from "../components/Toast";
import { FileSearch, Briefcase, Loader2, Square } from "lucide-react";

type Tab = "resume" | "job";

export default function ReviewPage() {
  const [tab, setTab] = useState<Tab>("resume");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");
  const [thinking, setThinking] = useState("");
  const [showApiKeyDialog, setShowApiKeyDialog] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const toast = useToast();
  const { isConfigured: llmConfigured } = useLLMStatus();

  const startReview = useCallback(async (endpoint: string) => {
    if (loading) return;
    if (!llmConfigured) { setShowApiKeyDialog(true); return; }
    setLoading(true);
    setResult("");
    setThinking("");

    const controller = new AbortController();
    abortRef.current = controller;

    let full = "";
    let thinkingAcc = "";

    try {
      await consumeSSE(
        endpoint,
        {}, // no body needed — backend reads active knowledge base
        (event, data) => {
          if (event === "thinking") {
            thinkingAcc += data;
            setThinking(thinkingAcc);
          } else if (event === "token") {
            full += data;
            setResult(full);
          } else if (event === "done") {
            // final content already captured
          } else if (event === "error") {
            toast.error(data || "分析失败");
          }
        },
        controller.signal,
      );
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      const msg = e instanceof Error ? e.message : "请求失败";
      if (msg.includes("Failed to fetch")) {
        toast.error("无法连接后端，请确认服务已启动");
      } else {
        toast.error(msg);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }, [loading, toast, llmConfigured]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  }, []);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">📋 简历评审</h2>
      <p className="text-sm text-zinc-500 mb-6">
        基于当前选中的简历、岗位 JD 和素材文档，进行智能评审和面试策略分析。
      </p>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 bg-zinc-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab("resume")}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === "resume"
              ? "bg-white text-zinc-900 shadow-sm"
              : "text-zinc-500 hover:text-zinc-700"
          }`}
        >
          <FileSearch size={16} />
          简历评审
        </button>
        <button
          onClick={() => setTab("job")}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            tab === "job"
              ? "bg-white text-zinc-900 shadow-sm"
              : "text-zinc-500 hover:text-zinc-700"
          }`}
        >
          <Briefcase size={16} />
          岗位解析
        </button>
      </div>

      {/* Tab content */}
      {tab === "resume" && (
        <ReviewTab
          title="简历评审"
          description="AI 将从结构、量化数据、技术栈匹配、项目描述、语言表达五个维度全面评审你的简历，给出具体改进建议和示例写法。"
          endpoint="/api/review/resume"
          loading={loading}
          thinking={thinking}
          result={result}
          onStart={startReview}
          onStop={handleStop}
        />
      )}
      {tab === "job" && (
        <ReviewTab
          title="岗位解析"
          description="AI 将深度解读岗位要求，分析你的简历匹配度，并给出面试策略：该突出什么能力、弱化什么方向、准备哪些 STAR 话术。"
          endpoint="/api/review/job"
          loading={loading}
          thinking={thinking}
          result={result}
          onStart={startReview}
          onStop={handleStop}
        />
      )}

      <ApiKeyRequiredDialog
        open={showApiKeyDialog}
        onClose={() => setShowApiKeyDialog(false)}
        featureName="简历评审"
        highlight="llm"
      />
    </div>
  );
}

function ReviewTab({
  title, description, endpoint,
  loading, thinking, result,
  onStart, onStop,
}: {
  title: string; description: string; endpoint: string;
  loading: boolean; thinking: string; result: string;
  onStart: (endpoint: string) => void;
  onStop: () => void;
}) {
  return (
    <div>
      {/* Control bar */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
        <h3 className="font-semibold mb-2">{title}</h3>
        <p className="text-sm text-zinc-500 mb-4">{description}</p>
        <div className="flex gap-3">
          {!loading ? (
            <button
              onClick={() => onStart(endpoint)}
              className="px-4 py-2 bg-zinc-800 text-white text-sm rounded-lg font-medium hover:bg-zinc-700 transition-colors"
            >
              开始分析
            </button>
          ) : (
            <button
              onClick={onStop}
              className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white text-sm rounded-lg font-medium hover:bg-red-600 transition-colors"
            >
              <Square size={14} /> 停止
            </button>
          )}
        </div>
      </section>

      {/* Result area */}
      {(loading || result) && (
        <section className="bg-white border border-zinc-200 rounded-xl p-5">
          {/* Thinking panel */}
          {thinking && (
            <details className="mb-4">
              <summary className="text-xs text-zinc-400 cursor-pointer hover:text-zinc-600 select-none">
                查看分析过程
              </summary>
              <div className="mt-2 p-3 bg-amber-50 border border-amber-100 rounded-lg text-xs text-amber-800 whitespace-pre-wrap max-h-48 overflow-y-auto">
                {thinking}
              </div>
            </details>
          )}

          {/* Streaming indicator */}
          {loading && !result && (
            <div className="flex items-center gap-2 text-sm text-zinc-400 py-8 justify-center">
              <Loader2 size={18} className="animate-spin" />
              AI 正在分析中...
            </div>
          )}

          {/* Result content */}
          {result && (
            <MarkdownRenderer content={result} streaming={loading} />
          )}
        </section>
      )}
    </div>
  );
}
