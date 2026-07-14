/** 全局 Toast 通知系统 */

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { CheckCircle, AlertCircle, X } from "lucide-react";

interface ToastItem {
  id: number;
  type: "success" | "error";
  message: string;
}

interface ToastContextType {
  success: (msg: string) => void;
  error: (msg: string) => void;
}

const ToastCtx = createContext<ToastContextType>({ success: () => {}, error: () => {} });

let _nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const add = useCallback((type: "success" | "error", message: string) => {
    const id = ++_nextId;
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3000);
  }, []);

  const success = useCallback((msg: string) => add("success", msg), [add]);
  const error = useCallback((msg: string) => add("error", msg), [add]);

  return (
    <ToastCtx.Provider value={{ success, error }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id}
            className={`pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-lg text-sm animate-[fadeIn_0.2s_ease-out] ${
              t.type === "success"
                ? "bg-green-50 border border-green-200 text-green-700"
                : "bg-red-50 border border-red-200 text-red-700"
            }`}>
            {t.type === "success"
              ? <CheckCircle size={15} className="text-green-500 flex-shrink-0" />
              : <AlertCircle size={15} className="text-red-500 flex-shrink-0" />
            }
            <span>{t.message}</span>
            <button onClick={() => setToasts(prev => prev.filter(item => item.id !== t.id))}
              className="ml-2 text-current opacity-50 hover:opacity-100">
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  return useContext(ToastCtx);
}
