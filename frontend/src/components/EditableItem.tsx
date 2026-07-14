/** 可编辑的实习/项目卡片 — 解决 ProfilePage 中 hooks-in-map 违规 */

import { useState } from "react";
import { Edit3, Trash2 } from "lucide-react";
import { apiDelete, apiPut } from "../lib/api";
import { useToast } from "./Toast";

// ── Internship ──

interface InternshipData {
  id: number; company: string; position: string;
  start_date: string; end_date?: string; achievements: string[];
}

export function EditableInternship({ item, onUpdated, onDeleted }: {
  item: InternshipData;
  onUpdated: () => void;
  onDeleted: () => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [pos, setPos] = useState(item.position);
  const [comp, setComp] = useState(item.company);
  const [sd, setSd] = useState(item.start_date || "");
  const [ed, setEd] = useState(item.end_date || "");

  if (editing) {
    return (
      <div className="border border-indigo-200 bg-indigo-50/30 rounded-lg p-3 mb-2 space-y-2">
        <div className="flex gap-2">
          <input className="flex-1 text-xs border rounded px-2 py-1" placeholder="职位" value={pos} onChange={e => setPos(e.target.value)} />
          <input className="flex-1 text-xs border rounded px-2 py-1" placeholder="公司" value={comp} onChange={e => setComp(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <input className="text-xs border rounded px-2 py-1 w-28" placeholder="开始" value={sd} onChange={e => setSd(e.target.value)} />
          <input className="text-xs border rounded px-2 py-1 w-28" placeholder="结束" value={ed} onChange={e => setEd(e.target.value)} />
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={() => { setPos(item.position); setComp(item.company); setSd(item.start_date||""); setEd(item.end_date||""); setEditing(false); }}
            className="text-xs border rounded px-2 py-1">取消</button>
          <button onClick={async () => {
            try {
              await apiPut(`/api/experiences/${item.id}?type=internship`, { position: pos, company: comp, start_date: sd, end_date: ed });
              onUpdated();
              setEditing(false);
              toast.success("已更新");
            } catch { toast.error("更新失败"); }
          }} className="text-xs bg-indigo-600 text-white rounded px-2 py-1">保存</button>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-zinc-100 rounded-lg p-3 mb-2 flex justify-between items-start">
      <div>
        <p className="font-medium text-sm">{item.position} · {item.company}</p>
        <p className="text-xs text-zinc-400">{item.start_date} – {item.end_date || "至今"}</p>
        <ul className="text-xs text-zinc-500 mt-1 ml-4 list-disc">
          {item.achievements.map((a, idx) => <li key={idx}>{a}</li>)}
        </ul>
      </div>
      <div className="flex gap-1">
        <button onClick={() => { setPos(item.position); setComp(item.company); setSd(item.start_date||""); setEd(item.end_date||""); setEditing(true); }}
          className="text-zinc-300 hover:text-indigo-500"><Edit3 size={14} /></button>
        <button onClick={() => { if(confirm("删除此实习经历？")) { apiDelete(`/api/experiences/${item.id}?type=internship`).then(onDeleted).then(() => toast.success("已删除")).catch(() => toast.error("删除失败")); }}}
          className="text-zinc-300 hover:text-red-400"><Trash2 size={14} /></button>
      </div>
    </div>
  );
}

// ── Project ──

interface ProjectData {
  id: number; name: string; role: string; tech_stack: string[];
  challenge: string; solution: string; result: string;
}

export function EditableProject({ item, onUpdated, onDeleted }: {
  item: ProjectData;
  onUpdated: () => void;
  onDeleted: () => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [nm, setNm] = useState(item.name);
  const [rl, setRl] = useState(item.role);
  const [ch, setCh] = useState(item.challenge);
  const [sl, setSl] = useState(item.solution);
  const [rs, setRs] = useState(item.result);

  if (editing) {
    return (
      <div className="border border-indigo-200 bg-indigo-50/30 rounded-lg p-3 mb-2 space-y-2">
        <div className="flex gap-2">
          <input className="flex-1 text-xs border rounded px-2 py-1" placeholder="项目名" value={nm} onChange={e => setNm(e.target.value)} />
          <input className="w-24 text-xs border rounded px-2 py-1" placeholder="角色" value={rl} onChange={e => setRl(e.target.value)} />
        </div>
        <input className="w-full text-xs border rounded px-2 py-1" placeholder="挑战" value={ch} onChange={e => setCh(e.target.value)} />
        <input className="w-full text-xs border rounded px-2 py-1" placeholder="方案" value={sl} onChange={e => setSl(e.target.value)} />
        <input className="w-full text-xs border rounded px-2 py-1" placeholder="结果" value={rs} onChange={e => setRs(e.target.value)} />
        <div className="flex gap-2 justify-end">
          <button onClick={() => { setNm(item.name); setRl(item.role); setCh(item.challenge); setSl(item.solution); setRs(item.result); setEditing(false); }}
            className="text-xs border rounded px-2 py-1">取消</button>
          <button onClick={async () => {
            try {
              await apiPut(`/api/experiences/${item.id}?type=project`, { name: nm, role: rl, challenge: ch, solution: sl, result: rs });
              onUpdated();
              setEditing(false);
              toast.success("已更新");
            } catch { toast.error("更新失败"); }
          }} className="text-xs bg-indigo-600 text-white rounded px-2 py-1">保存</button>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-zinc-100 rounded-lg p-3 mb-2">
      <div className="flex justify-between items-start">
        <div>
          <p className="font-medium text-sm">{item.name} <span className="text-xs text-zinc-400">({item.role})</span></p>
          <div className="flex gap-1 mt-1 flex-wrap">{item.tech_stack.map((t) => <span key={t} className="text-xs bg-zinc-100 rounded px-1.5 py-0.5">{t}</span>)}</div>
          <p className="text-xs text-zinc-500 mt-1">挑战：{item.challenge} | 方案：{item.solution} | 结果：{item.result}</p>
        </div>
        <div className="flex gap-1">
          <button onClick={() => { setNm(item.name); setRl(item.role); setCh(item.challenge); setSl(item.solution); setRs(item.result); setEditing(true); }}
            className="text-zinc-300 hover:text-indigo-500"><Edit3 size={14} /></button>
          <button onClick={() => { if(confirm("删除此项目经历？")) { apiDelete(`/api/experiences/${item.id}?type=project`).then(onDeleted).then(() => toast.success("已删除")).catch(() => toast.error("删除失败")); }}}
            className="text-zinc-300 hover:text-red-400"><Trash2 size={14} /></button>
        </div>
      </div>
    </div>
  );
}
