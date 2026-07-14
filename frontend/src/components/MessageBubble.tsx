/** 对话消息气泡 — AI 头像 + 流式呼吸动画 + 思考过程 + Markdown 渲染 */

import { Copy, Check, Bot, User, ChevronDown, ChevronRight, Brain, Trash2 } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import MarkdownRenderer from "./MarkdownRenderer";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";

interface Props {
  role: "user" | "assistant";
  content: string;
  command?: string | null;
  type?: string;
  streaming?: boolean;
  thinking?: string;  // 思考过程的完整累积文本
  fastMode?: boolean;  // 使用了轻量模型
  messageId?: number;
  onDelete?: (id: number) => void;
}

const TYPE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  self_intro: { label: "自我介绍", icon: "🎙", color: "bg-indigo-50 text-indigo-600 border-indigo-200" },
  scenario: { label: "STAR 回答", icon: "🎯", color: "bg-green-50 text-green-600 border-green-200" },
  technical: { label: "技术面试", icon: "💻", color: "bg-blue-50 text-blue-600 border-blue-200" },
  follow_up: { label: "追问练习", icon: "🎓", color: "bg-amber-50 text-amber-600 border-amber-200" },
};

export default function MessageBubble({ role, content, command, type, streaming, thinking, fastMode, messageId, onDelete }: Props) {
  const [copied, setCopied] = useState(false);
  const [thinkingPhase, setThinkingPhase] = useState(streaming ? "thinking" : "done");
  const [thinkingOpen, setThinkingOpen] = useState(!!streaming);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  // Thinking animation phases: thinking → streaming → done
  useEffect(() => {
    if (streaming && content.length === 0) {
      setThinkingPhase("thinking");
    } else if (streaming && content.length > 0) {
      setThinkingPhase("streaming");
    } else {
      setThinkingPhase("done");
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [streaming, content.length]);

  const handleCopy = () => {
    navigator.clipboard?.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const cfg = type ? TYPE_CONFIG[type] : null;
  const hasContent = content.length > 0;

  // ── User bubble ──────────────────────────────────────
  if (role === "user") {
    return (
      <div className="flex justify-end mb-5 gap-3 group">
        <div className="flex-1" />
        {/* Delete button — visible on hover */}
        {messageId && onDelete && !streaming && (
          <button onClick={() => onDelete(messageId)}
            className="self-center opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-50 text-zinc-400 hover:text-red-500 flex-shrink-0"
            title="删除此轮对话">
            <Trash2 size={13} />
          </button>
        )}
        <div className="max-w-[75%]">
          <div className="bg-zinc-800 text-white px-4 py-3 rounded-2xl rounded-br-md text-sm whitespace-pre-wrap break-words shadow-sm">
            {content}
            {command && (
              <div className="text-xs text-zinc-400 mt-1 font-mono">{command}</div>
            )}
          </div>
        </div>
        <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center flex-shrink-0 mt-0.5">
          <User size={15} className="text-zinc-300" />
        </div>
      </div>
    );
  }

  // ── AI bubble ──────────────────────────────────────
  return (
    <div className="flex gap-3 mb-5 group">
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 transition-all duration-700 ${
        thinkingPhase === "thinking" ? "bg-indigo-100 animate-pulse ring-2 ring-indigo-200" :
        thinkingPhase === "streaming" ? "bg-indigo-100 ring-1 ring-indigo-300" :
        "bg-indigo-50"
      }`}>
        <Bot size={16} className={`transition-colors duration-500 ${
          thinkingPhase === "thinking" ? "text-indigo-400" :
          thinkingPhase === "streaming" ? "text-indigo-500" :
          "text-indigo-400"
        }`} />
      </div>

      <div className="flex-1 max-w-[85%]">
        {/* Thinking section — expandable */}
        {thinking && thinking.length > 0 && (
          <div className="mb-2 bg-white border border-indigo-100 rounded-2xl overflow-hidden shadow-sm">
            <button
              onClick={() => setThinkingOpen(!thinkingOpen)}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-xs font-medium text-indigo-600 bg-gradient-to-r from-indigo-50 to-transparent hover:from-indigo-100 hover:to-indigo-50/30 transition-colors"
            >
              <Brain size={13} className={streaming ? "animate-pulse" : ""} />
              <span>思考过程{thinking.length > 0 && ` (${thinking.length}字)`}</span>
              <span className="flex-1" />
              {thinkingOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            {thinkingOpen && (
              <div className="px-4 py-3 max-h-52 overflow-auto text-xs text-zinc-500 leading-relaxed border-l-2 border-l-indigo-400 ml-3 my-2">
                <p className="whitespace-pre-wrap break-words animate-[fadeIn_0.3s_ease-out]">{thinking}</p>
                {streaming && (
                  <div className="flex items-center gap-2 text-indigo-400 animate-pulse pt-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-300" />
                    <span>思考中…</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Thinking indicator */}
        {thinkingPhase === "thinking" && !thinking?.length && (
          <div className="bg-white border border-zinc-200 rounded-2xl rounded-bl-md px-5 py-3 shadow-sm mb-1">
            <div className="flex items-center gap-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
              <span className="text-sm text-zinc-400">
                {type === "self_intro" ? "正在构思自我介绍…" :
                 type === "scenario" ? "正在分析问题并组织 STAR 回答…" :
                 "正在思考…"}
              </span>
            </div>
          </div>
        )}

        {/* Content bubble */}
        {(hasContent || thinkingPhase === "streaming") && (
          <div className={`bg-white border rounded-2xl rounded-bl-md px-5 py-4 shadow-sm transition-all ${
            cfg ? cfg.color.split(" ")[0] + " border-l-2 border-l-indigo-400" : "border-zinc-200"
          }`}>
            {/* Type badge */}
            {cfg && (
              <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-md font-medium mb-3 border ${cfg.color}`}>
                {cfg.icon} {cfg.label}
              </span>
            )}

            {/* Fast model indicator */}
            {fastMode && (
              <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-md font-medium mb-3 ml-2 bg-amber-50 text-amber-600 border border-amber-200">
                ⚡ 快速响应
              </span>
            )}

            {/* Content — Markdown 渲染 */}
            <MarkdownRenderer content={content} streaming={streaming} />

            {/* Streaming breathing ring */}
            {streaming && hasContent && (
              <div className="mt-3 flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-300 animate-ping" />
                <span className="text-[11px] text-indigo-400 animate-pulse">生成中…</span>
              </div>
            )}
          </div>
        )}

        {/* Actions (after streaming done) */}
        {!streaming && hasContent && (
          <div className="mt-1.5 flex gap-3 text-xs text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity ml-1">
            <button onClick={handleCopy} className="flex items-center gap-1 hover:text-zinc-600">
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "已复制" : "复制"}
            </button>
            {messageId && onDelete && (
              <button onClick={() => onDelete(messageId)}
                className="flex items-center gap-1 hover:text-red-500">
                <Trash2 size={12} /> 删除
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
