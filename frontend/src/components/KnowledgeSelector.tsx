/** 知识选择栏：简历（必选）+ JD（可选）+ 个人素材（多选）+ 公司素材（多选） */

import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut, apiPostForm } from "../lib/api";
import { useLLMStatus } from "../lib/useLLMStatus";
import ApiKeyRequiredDialog from "./ApiKeyRequiredDialog";
import { useToast } from "./Toast";
import { ChevronDown, Check, PlusCircle } from "lucide-react";

interface Resume {
  id: number; name: string; is_active: boolean;
  internship_count: number; project_count: number; skill_count: number;
}

interface JDContext {
  id: number; name: string; is_active: boolean;
  core_skills: string[]; duties: string[];
  created_at: string | null;
}

interface Material {
  id: number; filename: string; file_type: string;
  scope: string; is_active: boolean;
}

export default function KnowledgeSelector() {
  const qc = useQueryClient();
  const toast = useToast();
  const { isConfigured: llmConfigured } = useLLMStatus();
  const [showApiKeyDialog, setShowApiKeyDialog] = useState(false);

  const { data: resumes = [] } = useQuery<Resume[]>({
    queryKey: ["resumes"],
    queryFn: () => apiGet("/api/resumes"),
  });
  const { data: jdList = [] } = useQuery<JDContext[]>({
    queryKey: ["jd-list"],
    queryFn: () => apiGet("/api/jd/list"),
  });
  const { data: personalMaterials = [] } = useQuery<Material[]>({
    queryKey: ["materials", "profile"],
    queryFn: () => apiGet("/api/materials?scope=profile&usage=attach"),
  });
  const { data: companyMaterials = [] } = useQuery<Material[]>({
    queryKey: ["materials", "jd"],
    queryFn: () => apiGet("/api/materials?scope=jd&usage=attach"),
  });

  const activeResume = resumes.find(r => r.is_active);
  const activeJD = jdList.find(j => j.is_active);
  const selectedPersonal = personalMaterials.filter(m => m.is_active);
  const selectedCompany = companyMaterials.filter(m => m.is_active);

  const handleActivateResume = async (id: number) => {
    try {
      await apiPost(`/api/resumes/${id}/activate`);
      qc.invalidateQueries({ queryKey: ["resumes"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["internships"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["skills"] });
      qc.invalidateQueries({ queryKey: ["documents","all"] });
      qc.invalidateQueries({ queryKey: ["jd-list"] });
      qc.invalidateQueries({ queryKey: ["jd-latest"] });
      qc.invalidateQueries({ queryKey: ["materials","profile"] });
      qc.invalidateQueries({ queryKey: ["materials","jd"] });
      toast.success("简历已切换");
    } catch { toast.error("切换失败"); }
  };

  const handleActivateJD = async (id: number | null) => {
    try {
      if (id) {
        await apiPost(`/api/jd/${id}/activate`);
      } else {
        await apiPost("/api/jd/deactivate");
      }
      qc.invalidateQueries({ queryKey: ["jd-list"] });
      qc.invalidateQueries({ queryKey: ["jd-latest"] });
      toast.success(id ? "JD 已切换" : "已取消 JD 选择");
    } catch { toast.error("操作失败"); }
  };

  const handleToggleMaterial = async (id: number, scope: string) => {
    try {
      await apiPut(`/api/materials/${id}/toggle`);
      qc.invalidateQueries({ queryKey: ["materials", scope] });
    } catch { toast.error("操作失败"); }
  };

  const handleInlineUpload = async (file: File, scope: "profile" | "jd") => {
    if (!llmConfigured) { setShowApiKeyDialog(true); return; }
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("scope", scope);
      form.append("usage", "attach");
      await apiPostForm("/api/documents", form);
      qc.invalidateQueries({ queryKey: ["materials", scope] });
      qc.invalidateQueries({ queryKey: ["documents", "all"] });
      toast.success("素材已上传");
    } catch { toast.error("上传失败"); }
  };

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-white border-b border-zinc-200 overflow-x-auto text-sm flex-shrink-0">
      {/* Resume Selector (Required) */}
      <DropdownSelect
        label="📋 简历"
        value={activeResume ? `${activeResume.name} (${activeResume.internship_count}实习·${activeResume.project_count}项目·${activeResume.skill_count}技能)` : "无"}
        required
      >
        {resumes.map(r => (
          <button
            key={r.id}
            onClick={() => handleActivateResume(r.id)}
            className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-50 flex items-center justify-between ${
              r.is_active ? "bg-indigo-50 text-indigo-700 font-medium" : "text-zinc-700"
            }`}
          >
            <span>{r.name} <span className="text-zinc-400 text-xs">({r.internship_count}实习·{r.project_count}项目)</span></span>
            {r.is_active && <Check size={14} className="text-indigo-600" />}
          </button>
        ))}
      </DropdownSelect>

      {/* JD Selector (Optional) */}
      <DropdownSelect
        label="💼 岗位"
        value={activeJD ? activeJD.name : "不使用"}
        optional
      >
        <button
          onClick={() => handleActivateJD(null as unknown as number)}
          className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-50 flex items-center justify-between ${
            !activeJD ? "bg-amber-50 text-amber-700 font-medium" : "text-zinc-500"
          }`}
        >
          <span>不使用 JD</span>
          {!activeJD && <Check size={14} className="text-amber-600" />}
        </button>
        {jdList.map(j => (
          <button
            key={j.id}
            onClick={() => handleActivateJD(j.id)}
            className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-50 flex items-center justify-between ${
              j.is_active ? "bg-indigo-50 text-indigo-700 font-medium" : "text-zinc-700"
            }`}
          >
            <span>{j.name}</span>
            {j.is_active && <Check size={14} className="text-indigo-600" />}
          </button>
        ))}
      </DropdownSelect>

      {/* Personal Materials (Multi-Select) */}
      <MultiSelect
        label="📎 个人素材"
        items={personalMaterials}
        selected={selectedPersonal}
        onToggle={(id) => handleToggleMaterial(id, "profile")}
        onUpload={(file) => handleInlineUpload(file, "profile")}
        emptyText="无素材"
        llmConfigured={llmConfigured}
        onApiKeyRequired={() => setShowApiKeyDialog(true)}
      />

      {/* Company Materials (Multi-Select) */}
      <MultiSelect
        label="🏢 公司素材"
        items={companyMaterials}
        selected={selectedCompany}
        onToggle={(id) => handleToggleMaterial(id, "jd")}
        onUpload={(file) => handleInlineUpload(file, "jd")}
        emptyText="无素材"
        llmConfigured={llmConfigured}
        onApiKeyRequired={() => setShowApiKeyDialog(true)}
      />

      <ApiKeyRequiredDialog
        open={showApiKeyDialog}
        onClose={() => setShowApiKeyDialog(false)}
        featureName="素材上传"
        highlight="llm"
      />
    </div>
  );
}

/** Simple dropdown selector */
function DropdownSelect({ label, value, children, required, optional }: {
  label: string; value: string; children: React.ReactNode;
  required?: boolean; optional?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-colors ${
          required ? "border-indigo-300 bg-indigo-50 text-indigo-700" :
          "border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300"
        }`}
      >
        <span className="text-xs font-medium">{label}</span>
        <span className="max-w-[180px] truncate">{value}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 min-w-[260px] bg-white border border-zinc-200 rounded-lg shadow-lg z-50 py-1 max-h-64 overflow-y-auto">
          {children}
        </div>
      )}
    </div>
  );
}

/** Multi-select with checkboxes in a dropdown */
function MultiSelect({ label, items, selected, onToggle, onUpload, emptyText, llmConfigured, onApiKeyRequired }: {
  label: string; items: Material[]; selected: Material[];
  onToggle: (id: number) => void;
  onUpload?: (file: File) => void;
  emptyText: string;
  llmConfigured?: boolean;
  onApiKeyRequired?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const hasSelection = selected.length > 0;

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-colors ${
          hasSelection ? "border-green-300 bg-green-50 text-green-700" :
          "border-zinc-200 bg-white text-zinc-400 hover:border-zinc-300"
        }`}
      >
        <span className="text-xs font-medium">{label}</span>
        <span className="max-w-[120px] truncate">
          {hasSelection ? `已选 ${selected.length} 份` : emptyText}
        </span>
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-1 right-0 min-w-[240px] bg-white border border-zinc-200 rounded-lg shadow-lg z-50 py-1 max-h-64 overflow-y-auto">
          {items.length === 0 ? (
            <div className="px-3 py-3 text-xs text-zinc-400 text-center">{emptyText}</div>
          ) : (
            items.map(m => {
              const isSel = selected.some(s => s.id === m.id);
              return (
                <button
                  key={m.id}
                  onClick={() => onToggle(m.id)}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-50 flex items-center gap-2 ${
                    isSel ? "text-green-700" : "text-zinc-600"
                  }`}
                >
                  <span className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                    isSel ? "bg-green-500 border-green-500 text-white" : "border-zinc-300"
                  }`}>
                    {isSel && <Check size={10} />}
                  </span>
                  <span className="truncate">{m.filename}</span>
                </button>
              );
            })
          )}
          {onUpload && (
            <span
              className="flex items-center gap-1.5 px-3 py-2 text-xs text-zinc-400 hover:text-zinc-600 hover:bg-zinc-50 cursor-pointer border-t border-zinc-100"
              onClick={() => {
                if (!llmConfigured) { onApiKeyRequired?.(); return; }
                fileRef.current?.click();
              }}
            >
              <PlusCircle size={13} />
              上传素材
              <input type="file" ref={fileRef} className="hidden" accept=".txt,.doc,.docx,.pdf"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) { onUpload(f); setOpen(false); } }} />
            </span>
          )}
        </div>
      )}
    </div>
  );
}
