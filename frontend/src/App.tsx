import { useState, useEffect } from "react";
import {
  MessageCircle,
  User,
  FileText,
  BookOpen,
  Settings,
  FileSearch,
  Mic,
} from "lucide-react";
import ConversationPage from "./pages/ConversationPage";
import ProfilePage from "./pages/ProfilePage";
import JDPage from "./pages/JDPage";
import PromptTemplatePage from "./pages/PromptTemplatePage";
import ReviewPage from "./pages/ReviewPage";
import InterviewPage from "./pages/InterviewPage";
import SettingsPage from "./pages/SettingsPage";

type Page = "conversation" | "profile" | "jd" | "prompts" | "review" | "interview" | "settings";

const NAV_ITEMS: { id: Page; label: string; icon: React.ReactNode }[] = [
  { id: "conversation", label: "对话", icon: <MessageCircle size={18} /> },
  { id: "profile", label: "个人知识库", icon: <User size={18} /> },
  { id: "jd", label: "岗位上下文", icon: <FileText size={18} /> },
  { id: "review", label: "简历评审", icon: <FileSearch size={18} /> },
  { id: "interview", label: "模拟面试", icon: <Mic size={18} /> },
  { id: "prompts", label: "提示词管理", icon: <BookOpen size={18} /> },
  { id: "settings", label: "设置", icon: <Settings size={18} /> },
];

export default function App() {
  const [page, setPage] = useState<Page>("conversation");
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [settingsHighlight, setSettingsHighlight] = useState<string | null>(null);

  // Listen for navigation events from child components
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (typeof detail === "object" && detail !== null && "page" in detail && (detail as Record<string,unknown>).page === "settings") {
        setPage("settings");
        setSettingsHighlight((detail as Record<string,unknown>).highlight as string || null);
      } else if (typeof detail === "string") {
        setPage(detail as Page);
        setSettingsHighlight(null);
      }
    };
    window.addEventListener("navigate", handler);
    return () => window.removeEventListener("navigate", handler);
  }, []);

  return (
    <div className="flex h-screen bg-zinc-50">
      {/* Sidebar */}
      <aside className="w-56 border-r border-zinc-200 bg-white flex flex-col">
        <div className="px-5 py-4 border-b border-zinc-200">
          <h1 className="font-semibold text-base">SpeakWise</h1>
          <p className="text-xs text-zinc-400 mt-0.5">智能面试助手</p>
        </div>
        <nav className="flex-1 p-3 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                page === item.id
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-zinc-200">
          <p className="text-xs text-zinc-400">SpeakWise v0.1.0</p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <div key={page} className="animate-[fadeIn_0.2s_ease-out] h-full">
          {page === "conversation" && <ConversationPage activeSessionId={activeSessionId} onSessionChange={setActiveSessionId} />}
          {page === "profile" && <ProfilePage />}
          {page === "jd" && <JDPage activeSessionId={activeSessionId} />}
          {page === "review" && <ReviewPage />}
          {page === "interview" && <InterviewPage />}
          {page === "prompts" && <PromptTemplatePage />}
        {page === "settings" && <SettingsPage highlight={settingsHighlight} />}
        </div>
      </main>
    </div>
  );
}
