/** 对话主页面 —— 消息列表 + 流式 SSE + 输入栏 + 会话管理 */

import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete } from "../lib/api";
import { consumeGenerateStream } from "../lib/streamConsumer";
import SessionSelector from "../components/SessionSelector";
import KnowledgeSelector from "../components/KnowledgeSelector";
import MessageBubble from "../components/MessageBubble";
import ChatInput from "../components/ChatInput";
import ApiKeyRequiredDialog from "../components/ApiKeyRequiredDialog";
import { useToast } from "../components/Toast";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  thinking?: string | null;
  command?: string | null;
  type: string;
}

interface Props {
  activeSessionId: number | null;
  onSessionChange: (id: number) => void;
  isActive: boolean;
}

export default function ConversationPage({ activeSessionId, onSessionChange, isActive }: Props) {
  const toast = useToast();
  const [generating, setGenerating] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [streamType, setStreamType] = useState<string>("");
  const [thinkingText, setThinkingText] = useState("");
  const [fastMode, setFastMode] = useState(false);
  const [showApiKeyDialog, setShowApiKeyDialog] = useState(false);
  const msgEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const qc = useQueryClient();

  // Auto-select first non-mock session
  const { data: allSessions = [] } = useQuery<{ id: number; name: string; mode?: string }[]>({
    queryKey: ["sessions"],
    queryFn: () => apiGet("/api/sessions"),
  });
  const sessions = allSessions.filter(s => s.mode !== "mock");
  useEffect(() => {
    if (!activeSessionId && sessions.length > 0) onSessionChange(sessions[0].id);
  }, [sessions, activeSessionId]);

  // Messages
  const { data: messages = [], isLoading: msgsLoading, refetch: refetchMsgs } = useQuery<Message[]>({
    queryKey: ["messages", activeSessionId],
    queryFn: () =>
      activeSessionId ? apiGet(`/api/sessions/${activeSessionId}/messages`) : Promise.resolve([]),
    enabled: !!activeSessionId,
  });

  // Smart scroll: only auto-scroll when user is near bottom
  const [isNearBottom, setIsNearBottom] = useState(true);
  const msgContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isActive || !isNearBottom) return;
    const frameId = requestAnimationFrame(() => {
      msgEndRef.current?.scrollIntoView({ behavior: "instant" as ScrollBehavior });
    });
    return () => cancelAnimationFrame(frameId);
  }, [messages, streamingText, isNearBottom, isActive]);

  const handleScroll = useCallback(() => {
    const el = msgContainerRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    setIsNearBottom(dist < 80);
  }, []);

  // Check if API key is configured (must be before handleSend for closure)
  const { data: llmSettings } = useQuery<{ provider: string; api_key: string; model: string }>({
    queryKey: ["settings", "llm"],
    queryFn: () => apiGet("/api/settings/llm"),
  });
  const hasApiKey = !!(llmSettings?.api_key);

  const handleSend = useCallback(
    async (text: string) => {
      if (generating) return;
      if (!hasApiKey) { setShowApiKeyDialog(true); return; }
      // Auto-create session if none exists
      let sid = activeSessionId;
      if (!sid) {
        try {
          const s = await apiPost("/api/sessions", { name: "会话 1", mode: "normal" }) as { id: number };
          sid = s.id;
          onSessionChange(sid);
          qc.invalidateQueries({ queryKey: ["sessions"] });
        } catch {
          toast.error("创建会话失败");
          return;
        }
      }

      // Parse command
      const cmdMatch = text.match(/^\/(intro|scenario|followup|technical)\b/);
      const command = cmdMatch ? `/${cmdMatch[1]}` : null;
      const msgType = command === "/intro" ? "self_intro" : command === "/scenario" ? "scenario" : command === "/technical" ? "technical" : "free_text";

      // Clear any previous streaming
      setStreamingText("");
      setStreamType(msgType);
      setThinkingText("");

      // Optimistic user message
      qc.setQueryData(["messages", sid], (old: Message[] = []) => [
        ...old,
        { id: Date.now(), role: "user", content: text, command, type: "free_text" },
      ]);

      setGenerating(true);

      // rAF throttle: avoid re-rendering react-markdown on every token
      let tokenRafId: number | null = null;
      let latestText = "";

      // Create abort controller for this request
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await consumeGenerateStream(sid, text, command, null, {
          onMeta: (meta) => {
            setFastMode(!!meta.fast_mode);
          },
          onThinking: (text) => {
            setThinkingText(text);
          },
          onToken: (partial) => {
            latestText = partial;
            if (tokenRafId === null) {
              tokenRafId = requestAnimationFrame(() => {
                tokenRafId = null;
                setStreamingText(latestText);
              });
            }
          },
          onDone: () => {
            if (tokenRafId !== null) cancelAnimationFrame(tokenRafId);
            setStreamingText(latestText);
            setTimeout(() => {
              setStreamingText("");
              setThinkingText("");
            }, 50);
            setGenerating(false);
            abortRef.current = null;
            refetchMsgs();
          },
          onError: (err) => {
            if (tokenRafId !== null) cancelAnimationFrame(tokenRafId);
            // AbortError from user cancellation — not a real error
            if (err.includes("aborted") || err.includes("AbortError")) {
              setStreamingText("");
              setThinkingText("");
              setGenerating(false);
              abortRef.current = null;
              return;
            }
            setStreamingText("");
            setThinkingText("");
            setGenerating(false);
            abortRef.current = null;
            const errMsg = err.includes("Failed to fetch")
              ? "无法连接到后端服务，请确认后端已启动"
              : err.includes("DEEPSEEK_API_KEY 未配置") || err.includes("API_KEY")
              ? "API Key 未配置，请先在设置中配置。"
              : err;
            qc.setQueryData(["messages", sid], (old: Message[] = []) => [
              ...old,
              { id: Date.now(), role: "assistant", content: err.includes("DEEPSEEK_API_KEY") || err.includes("API_KEY")
                ? `⚠️ **API Key 未配置**\n\n请先前往 [⚙️ 设置](#) 页面配置 DeepSeek API Key，然后即可开始使用。\n\n> 获取 Key: https://platform.deepseek.com`
                : `❌ 生成失败: ${errMsg}`, command: null, type: "system" },
            ]);
          },
        }, controller.signal);
      } catch {
        if (tokenRafId !== null) cancelAnimationFrame(tokenRafId);
        setStreamingText("");
        setThinkingText("");
        setGenerating(false);
        abortRef.current = null;
      }
    },
    [activeSessionId, generating, qc, refetchMsgs, hasApiKey]
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const handleDeleteMessage = async (msgId: number) => {
    if (!activeSessionId || !confirm("删除此轮对话（用户消息 + AI 回复）？")) return;
    try {
      await apiDelete(`/api/sessions/${activeSessionId}/messages/${msgId}`);
      refetchMsgs();
      toast.success("已删除");
    } catch { toast.error("删除失败"); }
  };

  const isFirstMessage = !msgsLoading && messages.length === 0 && !streamingText;

  // ── Copilot overlay ──
  const [overlayVisible, setOverlayVisible] = useState(false);
  const sw = window.speakwise;
  const hasOverlay = !!sw?.overlay;

  const toggleOverlay = async () => {
    if (!sw?.overlay) return;
    if (overlayVisible) {
      await sw.overlay.hide();
    } else {
      await sw.overlay.show();
    }
    setOverlayVisible(!overlayVisible);
  };

  // Sync latest assistant message to overlay
  useEffect(() => {
    if (!sw?.overlay || !overlayVisible) return;
    const text = streamingText || (messages.length > 0 ? messages[messages.length - 1]?.content : "");
    sw.overlay.setContent(text);
  }, [streamingText, messages, overlayVisible]);

  // Check if profile and JD are set up (for onboarding guide)
  const { data: profileStatus } = useQuery<{internship_count:number;project_count:number;skill_count:number}>({
    queryKey: ["profile"],
    queryFn: () => apiGet("/api/profile"),
  });
  const { data: jdStatus } = useQuery<{found:boolean}>({
    queryKey: ["jd-latest"],
    queryFn: () => apiGet("/api/jd/latest"),
  });
  const hasProfile = !!(profileStatus && (profileStatus.skill_count > 0 || profileStatus.project_count > 0));
  const hasJD = !!(jdStatus?.found);

  return (
    <div className="flex flex-col h-full">
      {/* Top toolbar */}
      <div className="px-6 py-3 border-b border-zinc-200 bg-white flex items-center gap-3 text-sm">
        <SessionSelector activeId={activeSessionId} onSelect={onSessionChange} />

      {/* API Key not configured warning */}
      {!hasApiKey && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 max-w-md">
          <span>⚠️ 未配置 API Key</span>
          <a href="#" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("navigate", {detail: "settings"})); }}
            className="text-amber-800 underline font-medium whitespace-nowrap">前往设置 →</a>
        </div>
      )}

        <span className="flex-1" />
        {hasOverlay && (
          <button
            onClick={toggleOverlay}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
              overlayVisible
                ? "bg-indigo-100 text-indigo-700 border border-indigo-200"
                : "bg-zinc-100 text-zinc-500 border border-zinc-200 hover:bg-zinc-200"
            }`}
            title={overlayVisible ? "关闭提词器" : "打开提词器"}
          >
            {overlayVisible ? "📋 提词器已开" : "📋 提词器"}
          </button>
        )}
      </div>

      {/* Knowledge Selector — resume / JD / materials */}
      <KnowledgeSelector />

      {/* Messages area */}
      <div className="flex-1 overflow-auto px-6 py-5" ref={msgContainerRef} onScroll={handleScroll}>
        {msgsLoading && (
          <div className="text-center pt-28 pb-16">
            <p className="text-5xl mb-5 animate-pulse">⏳</p>
            <p className="text-sm text-zinc-400">加载会话中…</p>
          </div>
        )}

        {isFirstMessage && (
          <div className="text-center pt-20 pb-16">
            <p className="text-5xl mb-5">💬</p>
            <p className="text-base font-semibold text-zinc-600 mb-1">面试准备对话</p>

            {/* Onboarding guide — only shows incomplete steps */}
            {(!hasProfile || !hasJD) && (
              <div className="inline-flex flex-col gap-2 mt-4 mb-6 text-left">
                {!hasProfile && (
                  <a href="#" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("navigate", {detail: "profile"})); }}
                    className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-xl text-sm hover:bg-amber-100 transition-colors">
                    <span className="w-5 h-5 rounded-full bg-amber-200 text-amber-700 text-xs flex items-center justify-center font-bold">1</span>
                    <span className="text-amber-800">填写个人知识库 <span className="text-amber-500 text-xs ml-1">简历、技能、项目经历</span></span>
                    <span className="text-amber-400 text-xs ml-auto">→</span>
                  </a>
                )}
                {!hasJD && (
                  <a href="#" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("navigate", {detail: "jd"})); }}
                    className="flex items-center gap-2 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-xl text-sm hover:bg-blue-100 transition-colors">
                    <span className="w-5 h-5 rounded-full bg-blue-200 text-blue-700 text-xs flex items-center justify-center font-bold">{hasProfile ? "2" : "2"}</span>
                    <span className="text-blue-800">设置岗位上下文 <span className="text-blue-500 text-xs ml-1">解析目标岗位 JD</span></span>
                    <span className="text-blue-400 text-xs ml-auto">→</span>
                  </a>
                )}
              </div>
            )}

            <p className="text-sm text-zinc-400 leading-relaxed">
              输入 <code className="bg-zinc-100 px-1.5 py-0.5 rounded text-zinc-500 text-xs font-mono">/intro</code> 生成自我介绍<br />
              输入 <code className="bg-zinc-100 px-1.5 py-0.5 rounded text-zinc-500 text-xs font-mono">/scenario &lt;问题&gt;</code> 生成场景题<br />
              输入 <code className="bg-zinc-100 px-1.5 py-0.5 rounded text-zinc-500 text-xs font-mono">/technical &lt;题目&gt;</code> 技术面试题<br />
              输入 <code className="bg-zinc-100 px-1.5 py-0.5 rounded text-zinc-500 text-xs font-mono">/followup</code> 模拟追问<br />
              <span className="text-zinc-300">面试模式下直接打字自动识别类型</span>
            </p>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} role={m.role} content={m.content} thinking={m.thinking ?? undefined}
            command={m.command} type={m.type} messageId={m.id} onDelete={handleDeleteMessage} />
        ))}

        {/* Streaming bubble with thinking */}
        {(streamingText || thinkingText.length > 0) && (
          <MessageBubble role="assistant" content={streamingText} type={streamType}
            streaming thinking={thinkingText} fastMode={fastMode} />
        )}

        <div ref={msgEndRef} />
      </div>

      {/* Input bar */}
      <div className="px-6 py-3 border-t border-zinc-200 bg-white">
        <ChatInput onSend={handleSend} generating={generating} onStop={handleStop} />
      </div>

      <ApiKeyRequiredDialog
        open={showApiKeyDialog}
        onClose={() => setShowApiKeyDialog(false)}
        featureName="对话"
        highlight="llm"
      />
    </div>
  );
}
