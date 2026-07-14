/** 对话输入栏 —— 斜杠命令 + 语音占位 + 发送/中止 */

import { useState, useRef, useEffect, useCallback } from "react";
import { Mic, Send, Square } from "lucide-react";

const COMMANDS = [
  { cmd: "/intro", desc: "生成自我介绍", hint: "/intro [要求]" },
  { cmd: "/scenario", desc: "生成场景题回答", hint: "/scenario <问题>" },
  { cmd: "/technical", desc: "技术面试题解答", hint: "/technical <题目>" },
  { cmd: "/followup", desc: "AI 模拟追问", hint: "/followup" },
];

interface Props {
  onSend: (text: string) => void;
  onStop?: () => void;
  generating?: boolean;
}

export default function ChatInput({ onSend, onStop, generating }: Props) {
  const [text, setText] = useState("");
  const [showSlash, setShowSlash] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filter based on typed prefix
  const filtered = text.startsWith("/")
    ? COMMANDS.filter(c => c.cmd.startsWith(text.split(" ")[0]))
    : [];

  const handleInput = (val: string) => {
    setText(val);
    setShowSlash(val.startsWith("/") && filtered.length > 0);
    setActiveIdx(0);
  };

  const fillSlash = useCallback((cmd: string) => {
    setText(cmd + " ");
    setShowSlash(false);
    inputRef.current?.focus();
  }, []);

  const send = () => {
    const trimmed = text.trim();
    if (!trimmed || generating) return;
    onSend(trimmed);
    setText("");
    setShowSlash(false);
  };

  // Keyboard: Escape to close, Arrow keys + Enter to navigate
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showSlash && filtered.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((activeIdx + 1) % filtered.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((activeIdx - 1 + filtered.length) % filtered.length);
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        fillSlash(filtered[activeIdx].cmd);
        return;
      }
      if (e.key === "Escape") {
        setShowSlash(false);
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey && !generating) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="relative">
      {/* Slash command autocomplete */}
      {showSlash && filtered.length > 0 && (
        <div className="absolute bottom-full left-0 mb-1 bg-white border border-zinc-200 rounded-xl shadow-lg p-1.5 min-w-[260px] z-20">
          {filtered.map((c, i) => (
            <button
              key={c.cmd}
              onMouseDown={(e) => { e.preventDefault(); fillSlash(c.cmd); }}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex justify-between items-center transition-colors ${
                i === activeIdx ? "bg-indigo-50 text-indigo-700" : "hover:bg-zinc-50"
              }`}
            >
              <span>
                <span className="font-mono font-semibold">{c.cmd}</span>
                <span className={i === activeIdx ? "text-indigo-400 ml-2" : "text-zinc-400 ml-2"}>{c.desc}</span>
              </span>
              <span className="text-xs text-zinc-300 font-mono">{c.hint}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex gap-2 items-center">
        <button
          disabled
          className="p-2 rounded-lg text-zinc-300 cursor-not-allowed"
          title="语音输入（需配置扩展）"
        >
          <Mic size={18} />
        </button>
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => handleInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={generating ? "AI 正在回复中…" : "输入 / 查看命令，或直接打字追问…"}
          className="flex-1 px-4 py-2.5 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
        {generating ? (
          <button
            onClick={onStop}
            className="p-2.5 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
            title="停止生成"
          >
            <Square size={18} fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={send}
            disabled={!text.trim()}
            className="p-2.5 bg-zinc-800 text-white rounded-lg hover:bg-zinc-700 transition-colors disabled:opacity-40"
          >
            <Send size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
