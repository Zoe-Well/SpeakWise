/** 文档导入组件 —— TXT/DOC/PDF 拖拽上传 */

import { useState, useRef } from "react";
import { Upload, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { apiPostForm, ApiError } from "../lib/api";

interface Props {
  scope?: "profile" | "jd";
  usage?: "parse" | "attach";
  onSuccess?: (result: Record<string, unknown>) => void;
}

export default function DocumentImport({ scope = "profile", usage = "parse", onSuccess }: Props) {
  const [state, setState] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async (file: File) => {
    setState("uploading");
    setStatusMsg("上传中…");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("scope", scope);
      form.append("usage", usage);
      const result = await apiPostForm<Record<string, unknown>>("/api/documents", form);

      if (result.parse_status === "success") {
        const prop = result.proposal as Record<string, unknown> | undefined;
        const changes = prop?.changes as Array<unknown> | undefined;
        const count = changes?.length || 0;
        // 立刻显示上传成功，然后渐进展示解析结果
        setState("success");
        setStatusMsg(`已上传，${count > 0 ? `解析出 ${count} 项` : "无可提取字段"}`);
        onSuccess?.(result);
        setTimeout(() => setState("idle"), 5000);
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

  const label = usage === "parse"
    ? `导入${scope === "jd" ? "JD" : "简历"}文档`
    : `附加${scope === "jd" ? "公司介绍" : "个人"}素材`;

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors ${
        state === "success" ? "border-green-300 bg-green-50/50" :
        state === "error" ? "border-amber-300 bg-amber-50/50" :
        "border-zinc-200 hover:border-zinc-400"
      }`}
      onClick={() => { if (state !== "uploading") fileRef.current?.click(); }}
      onDrop={(e) => { e.preventDefault(); if (state !== "uploading") { const f = e.dataTransfer.files[0]; if (f) upload(f); } }}
      onDragOver={(e) => e.preventDefault()}
    >
      <input type="file" ref={fileRef} className="hidden" accept=".txt,.doc,.docx,.pdf"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }} />
      {state === "uploading" && <Loader2 size={22} className="mx-auto text-zinc-400 mb-2 animate-spin" />}
      {state === "success" && <CheckCircle size={22} className="mx-auto text-green-500 mb-2" />}
      {state === "error" && <AlertCircle size={22} className="mx-auto text-amber-500 mb-2" />}
      {state === "idle" && <Upload size={22} className="mx-auto text-zinc-400 mb-2" />}
      <p className="text-sm font-medium">{state === "uploading" ? "上传中…" : state === "idle" ? label : statusMsg}</p>
      {state === "idle" && <p className="text-xs text-zinc-400 mt-1">支持 TXT / DOC / PDF</p>}
    </div>
  );
}
