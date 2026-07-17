/** 文档导入组件 —— TXT/DOC/PDF 拖拽上传 + 已有文档展示 + 替换模式弹窗 */

import { useState, useRef } from "react";
import { Upload, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { apiPostForm, ApiError } from "../lib/api";
import ImportModeDialog from "./ImportModeDialog";

interface DocInfo {
  id: number;
  filename: string;
  created_at?: string;
}

interface Props {
  scope?: "profile" | "jd";
  usage?: "parse" | "attach";
  onSuccess?: (result: Record<string, unknown>) => void;
  onDelete?: (docId: number) => void;
  existingDocs?: DocInfo[];
  /** 当前简历是否已有结构化数据（实习/项目/技能），用于决定是否弹出替换模式弹窗 */
  hasExistingData?: boolean;
  /** LLM 是否已配置，未配置时上传会被拦截 */
  llmConfigured?: boolean;
  /** LLM 未配置时的回调 */
  onApiKeyRequired?: () => void;
}

export default function DocumentImport({ scope = "profile", usage = "parse", onSuccess, onDelete, existingDocs = [], hasExistingData = false, llmConfigured = true, onApiKeyRequired }: Props) {
  const [state, setState] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [showModeDialog, setShowModeDialog] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const doUpload = async (file: File, clearExisting: boolean) => {
    setState("uploading");
    setStatusMsg("上传中…");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("scope", scope);
      form.append("usage", usage);
      if (clearExisting) form.append("clear_existing", "true");
      const result = await apiPostForm<Record<string, unknown>>("/api/documents", form);

      if (result.parse_status === "success") {
        if (usage === "parse") {
          const prop = result.proposal as Record<string, unknown> | undefined;
          const changes = prop?.changes as Array<unknown> | undefined;
          const count = changes?.length || 0;
          if (result.parse_error) {
            setState("error");
            setStatusMsg(result.parse_error as string || "解析服务暂时不可用，请稍后重试");
            setTimeout(() => setState("idle"), 6000);
          } else if (count > 0) {
            setState("success");
            setStatusMsg(`已上传，解析出 ${count} 项`);
            onSuccess?.(result);
            setTimeout(() => setState("idle"), 5000);
          } else {
            setState("success");
            setStatusMsg("文本已提取，但未发现可结构化字段（请检查文件是否为简历）");
            onSuccess?.(result);
            setTimeout(() => setState("idle"), 5000);
          }
        } else {
          // attach 模式：素材上传成功，无需解析
          setState("success");
          setStatusMsg("已上传");
          onSuccess?.(result);
          setTimeout(() => setState("idle"), 3000);
        }
      } else {
        setStatusMsg("无法提取文本，请检查文件格式");
        setState("error");
        setTimeout(() => setState("idle"), 4000);
      }
    } catch (e: unknown) {
      setState("error");
      if (e instanceof ApiError) {
        if (e.status === 413) setStatusMsg("文件过大，最大支持 10MB");
        else if (e.status >= 500) setStatusMsg("服务器错误，请稍后重试");
        else setStatusMsg(e.message || "上传失败，请重试");
      } else {
        setStatusMsg("网络错误，请检查后端是否启动");
      }
      setTimeout(() => setState("idle"), 4000);
    }
  };

  const handleFile = (file: File) => {
    // LLM 未配置时拦截（所有上传都需要 LLM）
    if (!llmConfigured) {
      onApiKeyRequired?.();
      return;
    }
    // 如果是解析模式且已有数据，弹出替换模式选择弹窗
    if (usage === "parse" && scope === "profile" && (existingDocs.length > 0 || hasExistingData)) {
      setPendingFile(file);
      setShowModeDialog(true);
    } else {
      doUpload(file, false);
    }
  };

  const label = usage === "parse"
    ? `${scope === "jd" ? "JD" : "简历"}文档`
    : `${scope === "jd" ? "公司介绍" : "个人"}素材`;

  const hasDocs = existingDocs.length > 0;

  return (
    <div>
      <div
        className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors ${
          state === "success" ? "border-green-300 bg-green-50/50" :
          state === "error" ? "border-amber-300 bg-amber-50/50" :
          "border-zinc-200 hover:border-zinc-400"
        }`}
        onClick={() => {
          if (state !== "uploading") {
            if (!llmConfigured) { onApiKeyRequired?.(); return; }
            fileRef.current?.click();
          }
        }}
        onDrop={(e) => { e.preventDefault(); if (state !== "uploading") { const f = e.dataTransfer.files[0]; if (f) handleFile(f); } }}
        onDragOver={(e) => e.preventDefault()}
      >
        <input type="file" ref={fileRef} className="hidden" accept=".txt,.doc,.docx,.pdf"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
        {state === "uploading" && <Loader2 size={22} className="mx-auto text-zinc-400 mb-2 animate-spin" />}
        {state === "success" && <CheckCircle size={22} className="mx-auto text-green-500 mb-2" />}
        {state === "error" && <AlertCircle size={22} className="mx-auto text-amber-500 mb-2" />}
        {state === "idle" && <Upload size={22} className="mx-auto text-zinc-400 mb-2" />}
        <p className="text-sm font-medium">{state === "uploading" ? "上传中…" : state === "idle" ? `导入${label}` : statusMsg}</p>
        {state === "idle" && <p className="text-xs text-zinc-400 mt-1">支持 TXT / DOC / PDF，拖拽或点击上传</p>}
      </div>

      {/* 已有文档展示 */}
      {hasDocs && (
        <div className="flex gap-1.5 mt-2 flex-wrap">
          {existingDocs.map((doc) => (
            <span key={doc.id} className="text-xs bg-zinc-100 border border-zinc-200 rounded-lg px-2.5 py-1 inline-flex items-center gap-1">
              📎 {doc.filename.length > 28 ? doc.filename.slice(0, 28) + "…" : doc.filename}
              {onDelete && (
                <button
                  onClick={() => onDelete(doc.id)}
                  className="text-zinc-400 hover:text-red-500 font-bold ml-0.5"
                >×</button>
              )}
            </span>
          ))}
        </div>
      )}

      {/* 替换模式选择弹窗 */}
      {showModeDialog && pendingFile && (
        <ImportModeDialog
          onConfirm={(mode) => {
            setShowModeDialog(false);
            doUpload(pendingFile, mode === "replace");
            setPendingFile(null);
          }}
          onCancel={() => {
            setShowModeDialog(false);
            setPendingFile(null);
          }}
        />
      )}
    </div>
  );
}
