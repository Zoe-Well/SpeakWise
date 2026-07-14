/** 个人知识库页面 —— 录入/编辑/删除 + 文档导入与解析确认 */

import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut, apiDelete } from "../lib/api";
import { Plus, Trash2, Save, Edit3 } from "lucide-react";
import DocumentImport from "../components/DocumentImport";
import ConfirmMergeDialog from "../components/ConfirmMergeDialog";
import { EditableInternship, EditableProject } from "../components/EditableItem";
import { useToast } from "../components/Toast";

interface Profile { id: number; name: string; phone?: string; email?: string; }
interface Internship { id: number; company: string; position: string; start_date: string; end_date?: string; achievements: string[]; }
interface Project { id: number; type: string; name: string; role: string; tech_stack: string[]; challenge: string; solution: string; result: string; }
interface Skill { id: number; category: string; name: string; proficiency: string; }

export default function ProfilePage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: profile } = useQuery<Profile>({ queryKey: ["profile"], queryFn: () => apiGet("/api/profile") });
  const { data: internships = [] } = useQuery<Internship[]>({ queryKey: ["internships"], queryFn: () => apiGet("/api/experiences?type=internship") });
  const { data: projects = [] } = useQuery<Project[]>({ queryKey: ["projects"], queryFn: () => apiGet("/api/experiences?type=project") });
  const { data: skills = [] } = useQuery<Skill[]>({ queryKey: ["skills"], queryFn: () => apiGet("/api/skills") });
  const { data: allDocs = [] } = useQuery<{id:number;filename:string;scope:string;usage:string;file_type:string;parse_status:string;created_at:string}[]>({
    queryKey: ["documents","all"],
    queryFn: () => apiGet("/api/documents"),
  });
  const profileDocs = allDocs.filter(d => d.scope === "profile");
  const jdDocs = allDocs.filter(d => d.scope === "jd");

  // 文档解析确认弹窗
  const [mergeChanges, setMergeChanges] = useState<Array<{id:string;op:string;target:string;value:Record<string,unknown>;conflict:boolean}> | null>(null);
  const [mergeProposalId, setMergeProposalId] = useState<number | null>(null);

  // Poll for pending resume parse proposals (page may have been navigated away during upload)
  const { data: pendingProposals } = useQuery({
    queryKey: ["profile-proposals"],
    queryFn: () => apiGet<Array<{proposal_id:number;changes:Array<{id:string;op:string;target:string;value:Record<string,unknown>;conflict:boolean}>}>>("/api/profile/proposals"),
    refetchInterval: 5000, // poll every 5s while on this page
  });
  useEffect(() => {
    if (pendingProposals && pendingProposals.length > 0) {
      const p = pendingProposals[0]; // take the latest
      if (!mergeChanges) {
        setMergeProposalId(p.proposal_id);
        setMergeChanges(p.changes);
      }
    }
  }, [pendingProposals]);

  const handleDocSuccess = (result: Record<string, unknown>) => {
    const proposal = result?.proposal as Record<string, unknown> | undefined;
    if (proposal && Array.isArray(proposal.changes) && proposal.changes.length > 0) {
      setMergeProposalId(proposal.proposal_id as number);
      setMergeChanges(proposal.changes as Array<{id:string;op:string;target:string;value:Record<string,unknown>;conflict:boolean}>);
    } else {
      qc.invalidateQueries({ queryKey: ["documents","all"] });
      qc.invalidateQueries({ queryKey: ["profile-proposals"] });
    }
  };

  const handleMergeConfirm = async (acceptedIds: string[]) => {
    if (mergeProposalId && acceptedIds.length > 0) {
      await apiPost("/api/profile/merge", { proposal_id: mergeProposalId, accepted_change_ids: acceptedIds });
    } else if (mergeProposalId) {
      // User cancelled — dismiss the proposal
      await apiPost("/api/profile/merge", { proposal_id: mergeProposalId, accepted_change_ids: [] });
    }
    setMergeChanges(null);
    setMergeProposalId(null);
    qc.invalidateQueries({ queryKey: ["internships"] });
    qc.invalidateQueries({ queryKey: ["projects"] });
    qc.invalidateQueries({ queryKey: ["skills"] });
    qc.invalidateQueries({ queryKey: ["documents","all"] });
    qc.invalidateQueries({ queryKey: ["profile-proposals"] });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">📋 个人知识库</h2>
      <p className="text-sm text-zinc-500 mb-6">录入并管理你的简历、实习、项目与技术栈。支持 TXT / DOC / PDF 文档导入。</p>

      {/* 文档导入 */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
        <h3 className="font-semibold mb-3">文档导入</h3>
        <div className="flex gap-4">
          <div className="flex-1">
            <DocumentImport scope="profile" usage="parse" onSuccess={handleDocSuccess} />
          </div>
          <div className="flex-1">
            <DocumentImport scope="profile" usage="attach" onSuccess={() => qc.invalidateQueries({ queryKey: ["documents","all"] })} />
          </div>
        </div>
        {profileDocs.length > 0 && (
          <div className="flex gap-2 mt-3 flex-wrap">
            {profileDocs.map((d) => (
              <span key={d.id} className="text-xs bg-zinc-100 border border-zinc-200 rounded-lg px-2.5 py-1.5 inline-flex items-center gap-1">
                📎 {d.filename}
                <button onClick={() => { if(confirm("删除此文档？")) { apiDelete(`/api/documents/${d.id}`).then(() => { qc.invalidateQueries({ queryKey: ["documents","all"] }); toast.success("已删除"); }).catch(() => toast.error("删除失败")); }}}
                  className="text-zinc-400 hover:text-red-500 font-bold ml-1">×</button>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* 解析确认弹窗 */}
      {mergeChanges && (
        <ConfirmMergeDialog
          changes={mergeChanges}
          onConfirm={handleMergeConfirm}
          onCancel={async () => {
            if (mergeProposalId) {
              await apiPost("/api/profile/merge", { proposal_id: mergeProposalId, accepted_change_ids: [] });
            }
            setMergeChanges(null); setMergeProposalId(null);
            qc.invalidateQueries({ queryKey: ["profile-proposals"] });
          }}
        />
      )}

      {/* Profile */}
      <ProfileForm profile={profile} onSaved={() => qc.invalidateQueries({ queryKey: ["profile"] })} />

      {/* Internships */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-semibold">💼 实习经历</h3>
          <AddInternshipBtn onAdded={() => qc.invalidateQueries({ queryKey: ["internships"] })} />
        </div>
        {internships.length === 0 && <p className="text-sm text-zinc-400">暂无实习经历。</p>}
        {internships.map((i) => (
          <EditableInternship key={i.id} item={i}
            onUpdated={() => qc.invalidateQueries({ queryKey: ["internships"] })}
            onDeleted={() => qc.invalidateQueries({ queryKey: ["internships"] })} />
        ))}
      </section>

      {/* Projects */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-semibold">🔬 科研 / 项目经历</h3>
          <AddProjectBtn onAdded={() => qc.invalidateQueries({ queryKey: ["projects"] })} />
        </div>
        {projects.length === 0 && <p className="text-sm text-zinc-400">暂无项目经历。</p>}
        {projects.map((p) => (
          <EditableProject key={p.id} item={p}
            onUpdated={() => qc.invalidateQueries({ queryKey: ["projects"] })}
            onDeleted={() => qc.invalidateQueries({ queryKey: ["projects"] })} />
        ))}
      </section>

      {/* Skills */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-semibold">🛠 技术栈</h3>
          <AddSkillBtn onAdded={() => qc.invalidateQueries({ queryKey: ["skills"] })} />
        </div>
        <div className="flex flex-wrap gap-2">
          {skills.map((s) => (
            <span key={s.id} className="inline-flex items-center gap-1 text-xs bg-zinc-100 border border-zinc-200 rounded-lg px-2.5 py-1.5">
              {s.name} <span className="text-zinc-400">·{s.proficiency}</span>
              <button onClick={() => { if(confirm("删除此技能？")) { apiDelete(`/api/skills/${s.id}`).then(() => { qc.invalidateQueries({ queryKey: ["skills"] }); toast.success("已删除"); }).catch(() => toast.error("删除失败")); } }}
                className="text-zinc-300 hover:text-red-400 ml-1 font-bold">×</button>
            </span>
          ))}
          {skills.length === 0 && <span className="text-sm text-zinc-400">暂无技能记录。</span>}
        </div>
      </section>

      {/* ── 文档素材管理 ── */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5">
        <h3 className="font-semibold mb-3">📎 文档素材</h3>
        <p className="text-xs text-zinc-400 mb-3">已上传的简历解析、附加素材和公司介绍文档。可在知识库对话中作为参考。</p>
        {allDocs.length === 0 ? (
          <p className="text-sm text-zinc-400">暂无文档素材。</p>
        ) : (
          <div className="space-y-2">
            {allDocs.map((d) => (
              <div key={d.id} className="flex items-center justify-between text-sm border border-zinc-100 rounded-lg px-3 py-2 hover:bg-zinc-50">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-base">
                    {d.file_type === "pdf" ? "📄" : d.file_type === "docx" || d.file_type === "doc" ? "📝" : "📃"}
                  </span>
                  <span className="truncate font-medium text-zinc-700">{d.filename}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${
                    d.scope === "profile" ? "bg-indigo-50 text-indigo-600" : "bg-blue-50 text-blue-600"
                  }`}>{d.scope === "profile" ? "个人" : "公司"}</span>
                  <span className="text-xs text-zinc-400 flex-shrink-0">{d.usage === "parse" ? "解析" : "附加"}</span>
                  {d.parse_status === "failed" && (
                    <span className="text-xs px-1 py-0.5 rounded bg-amber-50 text-amber-600 flex-shrink-0">解析失败</span>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs text-zinc-400">{d.created_at?.slice(0, 10)}</span>
                  <button
                    onClick={() => {
                      if (confirm("删除此文档？")) {
                        apiDelete(`/api/documents/${d.id}`)
                          .then(() => { qc.invalidateQueries({ queryKey: ["documents","all"] }); toast.success("已删除"); })
                          .catch(() => toast.error("删除失败"));
                      }
                    }}
                    className="text-xs text-zinc-400 hover:text-red-500 border border-zinc-200 rounded px-1.5 py-0.5 hover:border-red-200"
                  >删除</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ProfileForm({ profile, onSaved }: { profile?: Profile; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  useEffect(() => { setName(profile?.name || ""); setPhone(profile?.phone || ""); setEmail(profile?.email || ""); }, [profile?.id]);
  const save = () => { if (!profile) return; apiPut(`/api/profile/${profile.id}`, { name, phone, email }).then(onSaved).then(() => toast.success("保存成功")).catch(() => toast.error("保存失败")); };
  return (
    <section className="bg-white border border-zinc-200 rounded-xl p-5 mb-5">
      <h3 className="font-semibold mb-3">👤 基础信息</h3>
      <div className="grid grid-cols-3 gap-4 mb-3">
        <div><label className="block text-xs font-medium mb-1">姓名</label><input className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div><label className="block text-xs font-medium mb-1">电话</label><input className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" value={phone} onChange={(e) => setPhone(e.target.value)} /></div>
        <div><label className="block text-xs font-medium mb-1">邮箱</label><input className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
      </div>
      <button onClick={save} className="flex items-center gap-1 text-xs bg-zinc-800 text-white rounded-lg px-3 py-1.5 hover:bg-zinc-700"><Save size={13} /> 保存</button>
    </section>
  );
}

function AddInternshipBtn({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const add = () => {
    apiPost("/api/experiences?type=internship", { company: "新公司", position: "实习岗位", start_date: "2025.01", achievements: ["在此填写可量化成果"] }).then(onAdded).then(() => toast.success("已添加")).catch(() => toast.error("添加失败"));
  };
  return <button onClick={add} className="text-xs text-zinc-500 hover:text-zinc-700 border border-zinc-200 rounded-lg px-3 py-1"><Plus size={13} className="inline mr-1" />添加</button>;
}

function AddProjectBtn({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const add = () => {
    apiPost("/api/experiences?type=project", { type: "project", name: "新项目", role: "开发", tech_stack: ["技术栈"], challenge: "挑战", solution: "方案", result: "结果" }).then(onAdded).then(() => toast.success("已添加")).catch(() => toast.error("添加失败"));
  };
  return <button onClick={add} className="text-xs text-zinc-500 hover:text-zinc-700 border border-zinc-200 rounded-lg px-3 py-1"><Plus size={13} className="inline mr-1" />添加</button>;
}

function AddSkillBtn({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [proficiency, setProficiency] = useState("熟悉");
  const add = () => {
    if (!name.trim()) return;
    apiPost("/api/skills", { category: "language", name, proficiency }).then(() => { setName(""); onAdded(); toast.success("已添加"); }).catch(() => toast.error("添加失败"));
  };
  return (
    <div className="flex gap-2 items-center">
      <input placeholder="技能名" value={name} onChange={(e) => setName(e.target.value)} className="text-xs border border-zinc-200 rounded-lg px-2 py-1 w-28" />
      <select value={proficiency} onChange={(e) => setProficiency(e.target.value)} className="text-xs border border-zinc-200 rounded-lg px-2 py-1">
        <option>了解</option><option>熟悉</option><option>精通</option>
      </select>
      <button onClick={add} className="text-xs border border-zinc-200 rounded-lg px-2 py-1 hover:bg-zinc-50">添加</button>
    </div>
  );
}
