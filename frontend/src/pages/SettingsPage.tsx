/** API Key + LLM 模型 + 数据路径 设置页面 */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut, apiDelete } from "../lib/api";
import { useToast } from "../components/Toast";
import { CheckCircle, AlertCircle, Loader2, Shield, Eye, EyeOff } from "lucide-react";

const PROVIDERS = [
  { key: "deepseek", name: "DeepSeek", desc: "deepseek-v4-pro, deepseek-chat 等", url: "platform.deepseek.com" },
  { key: "openai", name: "OpenAI (GPT)", desc: "gpt-4o, gpt-4o-mini 等", url: "platform.openai.com" },
  { key: "anthropic", name: "Anthropic (Claude)", desc: "claude-sonnet-4, claude-haiku 等", url: "console.anthropic.com" },
];

export default function SettingsPage({ highlight }: { highlight?: string | null }) {
  const toast = useToast();
  const qc = useQueryClient();

  // Brief highlight animation when navigated from a config dialog
  const [flashSection, setFlashSection] = useState<string | null>(null);
  useEffect(() => {
    if (highlight) { setFlashSection(highlight); setTimeout(() => setFlashSection(null), 2500); }
  }, [highlight]);

  const [provider, setProvider] = useState("deepseek");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [validating, setValidating] = useState(false);
  const [valid, setValid] = useState<boolean | null>(null);
  const [showKey, setShowKey] = useState(false);

  const { data: saved } = useQuery({
    queryKey: ["settings", "llm"],
    queryFn: () => apiGet<{ provider: string; api_key: string; model: string }>("/api/settings/llm"),
  });

  const { data: dataDir } = useQuery<{
    data_dir: string; db_file: string;
    summary: Record<string, number>;
  }>({
    queryKey: ["settings", "data-dir"],
    queryFn: () => apiGet("/api/settings/data-dir"),
  });

  // Multi-key management
  const [newKeyName, setNewKeyName] = useState("");

  const { data: apiKeys = [] } = useQuery<{id:number;provider:string;name:string;api_key:string;model?:string;is_active:boolean}[]>({
    queryKey: ["settings", "apikeys"],
    queryFn: () => apiGet("/api/settings/apikeys"),
  });
  const [activatingId, setActivatingId] = useState<number | null>(null);
  const [actModel, setActModel] = useState("");

  const validateStoredKey = async (k: {id:number;provider:string;model?:string}) => {
    setActivatingId(k.id); setValid(null); setModels([]); setValidating(true);
    try {
      const res = await apiPost<{valid:boolean;models:string[]}>(`/api/settings/apikeys/${k.id}/validate`, {});
      setValid(true); setModels(res.models);
      setActModel(k.model || res.models[0] || "");
    } catch (e: any) {
      setValid(false); toast.error(e?.message || "Key 已失效");
    }
    setValidating(false);
  };

  const confirmActivate = () => {
    if (!activatingId || !actModel) return;
    activateMut.mutate({id: activatingId, model: actModel} as any);
    setActivatingId(null); setValid(null); setModels([]);
  };

  const addKeyMut = useMutation({
    mutationFn: (data: {provider:string;name:string;api_key:string;model?:string}) =>
      apiPost<{id:number}>("/api/settings/apikeys", data),
    onSuccess: async (result: {id:number}) => {
      qc.invalidateQueries({ queryKey: ["settings","apikeys"] });
      // Auto-activate the newly added key
      try {
        await apiPut(`/api/settings/apikeys/${result.id}/activate`, {model: model || ""});
        qc.invalidateQueries({ queryKey: ["settings","apikeys"] });
        qc.invalidateQueries({ queryKey: ["settings","llm"] });
        qc.invalidateQueries({ queryKey: ["llm-status"] });
        toast.success("Key 已添加并激活");
      } catch { toast.success("Key 已添加"); }
      setNewKeyName(""); setApiKey(""); setModel(""); setValid(null); setModels([]);
    },
    onError: (e: Error) => toast.error(e.message || "添加失败"),
  });

  const activateMut = useMutation({
    mutationFn: ({id, model}: {id:number;model:string}) => apiPut(`/api/settings/apikeys/${id}/activate`, {model}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["settings","apikeys"] }); qc.invalidateQueries({ queryKey: ["settings","llm"] }); qc.invalidateQueries({ queryKey: ["llm-status"] }); toast.success("已切换"); setActivatingId(null); setValid(null); setModels([]); },
    onError: (e: Error) => toast.error(e.message || "切换失败"),
  });

  const deleteKeyMut = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/settings/apikeys/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["settings","apikeys"] }); qc.invalidateQueries({ queryKey: ["llm-status"] }); toast.success("Key 已删除"); },
    onError: (e: Error) => toast.error(e.message || "删除失败"),
  });

  useEffect(() => {
    if (saved) {
      setProvider(saved.provider || "deepseek");
      setApiKey(saved.api_key || "");
      setModel(saved.model || "");
      if (saved.api_key && saved.model) {
        setValid(true);
        // Ensure saved model appears in the dropdown even without re-validating
        setModels(prev => prev.includes(saved.model) ? prev : [...prev, saved.model]);
      }
    }
  }, [saved]);

  const validateKey = async () => {
    setValidating(true); setValid(null); setModels([]);
    try {
      const res = await apiPost<{ valid: boolean; models: string[] }>("/api/settings/llm/validate", { provider, api_key: apiKey });
      setValid(res.valid);
      setModels(res.models);
      if (res.models.length > 0) setModel(res.models[0]);
      toast.success("API Key 有效");
    } catch (e: any) {
      setValid(false);
      toast.error(e?.message || "验证失败");
    }
    setValidating(false);
  };

  const saveMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => apiPut("/api/settings/llm", data),
    onSuccess: () => { toast.success("已保存"); qc.invalidateQueries({ queryKey: ["settings", "llm"] }); qc.invalidateQueries({ queryKey: ["llm-status"] }); },
    onError: (e: Error) => toast.error(e.message || "保存失败"),
  });

  const handleSave = () => {
    if (!apiKey.trim()) { toast.error("请输入 API Key"); return; }
    saveMut.mutate({ provider, api_key: apiKey.trim(), model });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">⚙️ 设置</h2>
      <p className="text-sm text-zinc-500 mb-6">配置 LLM API Key、选择模型、查看数据路径。</p>

      {/* === API Key (account-style) === */}
      <section className={`bg-white border rounded-xl p-5 mb-5 transition-all duration-700 ${
        flashSection === "llm" ? "border-amber-400 shadow-[0_0_20px_rgba(251,191,36,0.4)] bg-amber-50/30" : "border-zinc-200"
      }`}>
        <h3 className="font-semibold mb-3">🔑 API Key</h3>

        {/* Current active key */}
        {apiKeys.filter(k => k.is_active).map(k => (
          <div key={k.id} className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 mb-3">
            <p className="text-xs text-indigo-500 font-medium mb-1">当前使用</p>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-indigo-800">{k.name}</p>
                <p className="text-xs text-indigo-500">{k.provider} · {k.api_key} · {k.model || "默认模型"}</p>
              </div>
              <span className="w-2 h-2 rounded-full bg-green-500" title="活跃" />
            </div>
          </div>
        ))}
        {!apiKeys.some(k => k.is_active) && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-3 text-sm text-amber-700">
            ⚠️ 尚未配置 API Key，对话功能不可用。
          </div>
        )}

        {/* Switch key dropdown (only if multiple keys) */}
        {apiKeys.length > 1 && (
          <div className="mb-3">
            <label className="text-xs font-medium text-zinc-500">切换 Key</label>
            <select
              value=""
              onChange={e => { const id = Number(e.target.value); if(id) validateStoredKey(apiKeys.find(k=>k.id===id)!); }}
              className="w-full text-sm border rounded-lg px-3 py-2 bg-white mt-1">
              <option value="">切换其他 Key...</option>
              {apiKeys.filter(k => !k.is_active).map(k => (
                <option key={k.id} value={k.id}>{k.name} ({k.provider} · {k.api_key})</option>
              ))}
            </select>
          </div>
        )}

        {/* Activate confirmation (when validating stored key) */}
        {activatingId && (
          <div className="border border-indigo-200 rounded-lg p-3 mb-3 bg-white">
            {validating ? (
              <p className="text-sm text-zinc-500"><Loader2 size={14} className="animate-spin inline mr-1" />验证中...</p>
            ) : valid === true ? (
              <div>
                <p className="text-sm text-green-600 mb-2"><CheckCircle size={14} className="inline mr-1" />Key 有效</p>
                <label className="text-xs font-medium">选择模型</label>
                <div className="flex gap-2 mt-1">
                  <select value={actModel} onChange={e => setActModel(e.target.value)}
                    className="flex-1 text-sm border rounded-lg px-3 py-2 bg-white">
                    {models.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                  <button onClick={confirmActivate} className="text-sm bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700">确认切换</button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-red-500"><AlertCircle size={14} className="inline mr-1" />Key 已失效</p>
            )}
            <button onClick={() => { setActivatingId(null); setValid(null); }} className="text-xs text-zinc-400 mt-1">取消</button>
          </div>
        )}

        {/* Add new key (collapsible) */}
        <details className="mt-2">
          <summary className="text-sm text-indigo-600 cursor-pointer hover:underline font-medium">
            ＋ 添加新的 API Key
          </summary>
          <div className="mt-3 space-y-2">
            <div className="flex gap-2">
              <input value={newKeyName} onChange={e => setNewKeyName(e.target.value)}
                placeholder="标签（如：个人DeepSeek）" className="flex-1 text-xs border rounded-lg px-2 py-1.5" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              {PROVIDERS.map((p) => (
                <button key={p.key}
                  onClick={() => { setProvider(p.key); setValid(null); setModels([]); setModel(""); }}
                  className={`text-xs rounded-lg border px-2 py-1.5 text-left ${
                    provider === p.key ? "border-indigo-300 bg-indigo-50 text-indigo-700" : "border-zinc-200 hover:bg-zinc-50"
                  }`}>{p.name}</button>
              ))}
            </div>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <input type={showKey ? "text" : "password"} value={apiKey}
                  onChange={(e) => { setApiKey(e.target.value); setValid(null); }}
                  placeholder="粘贴 API Key" className="w-full text-sm border rounded-lg px-3 py-2 pr-9 font-mono" />
                <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400">
                  {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              <button onClick={validateKey} disabled={validating || !apiKey.trim()}
                className="text-xs border rounded-lg px-3 py-2 hover:bg-zinc-50 disabled:opacity-40">验证</button>
            </div>
            {valid === true && <p className="text-xs text-green-600"><CheckCircle size={12} className="inline" /> 有效</p>}
            {valid === false && <p className="text-xs text-red-500"><AlertCircle size={12} className="inline" /> 无效</p>}
            {models.length > 0 && (
              <div>
                <label className="text-xs font-medium">模型</label>
                <select value={model} onChange={e => setModel(e.target.value)}
                  className="w-full text-sm border rounded-lg px-3 py-2 bg-white mt-1">
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            )}
            <button onClick={() => {
              if (!apiKey.trim()) { toast.error("请输入 API Key"); return; }
              addKeyMut.mutate({ provider, name: newKeyName || `${provider}-key`, api_key: apiKey.trim(), model } as any);
            }}
              className="text-sm bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700">保存并使用</button>
          </div>
        </details>

        {/* Saved keys list (for management) */}
        {apiKeys.length > 0 && (
          <details className="mt-3">
            <summary className="text-xs text-zinc-400 cursor-pointer hover:text-zinc-600">管理已保存的 Key ({apiKeys.length})</summary>
            <div className="mt-2 space-y-1">
              {apiKeys.map(k => (
                <div key={k.id} className="flex items-center justify-between text-xs border rounded px-2 py-1.5">
                  <span>{k.name} · {k.provider} · {k.api_key}</span>
                  <span className="flex gap-1">
                    {k.is_active ? <span className="text-green-500">●</span> : <span className="text-zinc-300">○</span>}
                    <button onClick={() => {
                      const warn = k.is_active
                        ? "该 Key 当前正在使用中，删除后将无法使用 LLM 功能，确定删除？"
                        : "确定删除此 Key？";
                      if (confirm(warn)) deleteKeyMut.mutate(k.id);
                    }} className="text-zinc-400 hover:text-red-500">删除</button>
                  </span>
                </div>
              ))}
            </div>
          </details>
        )}
      </section>

      {/* LLM Provider (hidden — kept for compat) */}
      <section className="hidden">
        <h3 className="font-semibold mb-3">LLM 厂商</h3>
        <div className="grid grid-cols-3 gap-2 mb-4">
          {PROVIDERS.map((p) => (
            <button key={p.key}
              onClick={() => { setProvider(p.key); setValid(null); setModels([]); setModel(""); }}
              className={`text-sm rounded-lg border px-3 py-2.5 text-left transition-colors ${
                provider === p.key ? "border-indigo-300 bg-indigo-50 text-indigo-700" : "border-zinc-200 hover:bg-zinc-50"
              }`}>
              <p className="font-medium text-xs">{p.name}</p>
              <p className="text-xs text-zinc-400 mt-0.5">{p.url}</p>
            </button>
          ))}
        </div>

        {/* API Key */}
        <div className="mb-3">
          <label className="block text-xs font-medium mb-1">API Key</label>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setValid(null); }}
                placeholder="输入你的 API Key"
                className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 pr-9 focus:outline-none focus:ring-2 focus:ring-indigo-300 font-mono"
              />
              <button type="button" onClick={() => setShowKey(!showKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 p-1"
                title={showKey ? "隐藏" : "显示"}>
                {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <button onClick={validateKey} disabled={validating || !apiKey.trim()}
              className="text-xs border border-zinc-200 rounded-lg px-3 py-2 hover:bg-zinc-50 disabled:opacity-40 whitespace-nowrap">
              {validating ? <Loader2 size={14} className="animate-spin inline" /> : "验证 Key"}
            </button>
          </div>
          {valid === true && <p className="text-xs text-green-600 mt-1 flex items-center gap-1"><CheckCircle size={12} /> 验证成功</p>}
          {valid === false && <p className="text-xs text-red-500 mt-1 flex items-center gap-1"><AlertCircle size={12} /> Key 无效</p>}
        </div>

        {/* Model Selection */}
        {models.length > 0 && (
          <div className="mb-4">
            <label className="block text-xs font-medium mb-1">模型选择</label>
            <select value={model} onChange={(e) => setModel(e.target.value)}
              className="w-full text-sm border border-zinc-200 rounded-lg px-3 py-2 bg-white">
              {models.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        )}

        <div className="flex gap-2">
          <button onClick={handleSave} className="text-sm bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700 transition-colors">
            保存设置
          </button>
          {saved?.api_key && (
            <button onClick={async () => {
              try {
                await apiPut("/api/settings/llm", { provider: "deepseek", api_key: "", model: "" });
                setApiKey(""); setModel(""); setValid(null); setModels([]);
                qc.invalidateQueries({ queryKey: ["settings", "llm"] });
                qc.invalidateQueries({ queryKey: ["llm-status"] });
                toast.success("API Key 已删除");
              } catch { toast.error("删除失败"); }
            }}
              className="text-sm border border-red-200 text-red-600 rounded-lg px-4 py-2 hover:bg-red-50 transition-colors">
              删除 Key
            </button>
          )}
        </div>
      </section>

      {/* === Voice Settings === */}
      <VoiceSettings flashSection={flashSection} />

      {/* Data Path */}
      <section className="bg-white border border-zinc-200 rounded-xl p-5">
        <h3 className="font-semibold mb-3 flex items-center gap-2"><Shield size={16} /> 数据存储</h3>

        {/* Summary grid */}
        {dataDir?.summary && (
          <div className="grid grid-cols-3 gap-2 mb-4">
            {Object.entries(dataDir.summary).filter(([k]) => k !== "db_size_kb").map(([key, val]) => (
              <div key={key} className="bg-zinc-50 rounded-lg px-3 py-2 text-center">
                <p className="text-lg font-semibold text-zinc-700">{val}</p>
                <p className="text-xs text-zinc-400">{key === "sessions" ? "会话" : key === "messages" ? "消息" : key === "skills" ? "技能" : key === "projects" ? "项目" : key === "internships" ? "实习" : key === "documents" ? "文档" : key === "templates" ? "模板" : key === "jd_contexts" ? "JD" : key}</p>
              </div>
            ))}
            <div className="bg-zinc-50 rounded-lg px-3 py-2 text-center">
              <p className="text-lg font-semibold text-zinc-700">{dataDir.summary.db_size_kb} KB</p>
              <p className="text-xs text-zinc-400">数据库</p>
            </div>
          </div>
        )}

        <p className="text-xs text-zinc-400 mb-2">
          数据以 <strong>SQLite 数据库</strong> 格式存储（copilot.db），可用 DB Browser 等工具直接查看。
        </p>
        <div className="flex items-center gap-2 mb-2">
          <code className="text-xs bg-zinc-100 rounded px-3 py-2 flex-1 font-mono text-zinc-600 break-all select-all">
            {dataDir?.data_dir || "加载中…"}
          </code>
          <button onClick={() => { navigator.clipboard.writeText(dataDir?.data_dir || ""); toast.success("路径已复制"); }}
            className="text-xs border border-zinc-200 rounded-lg px-3 py-2 hover:bg-zinc-50 whitespace-nowrap">
            复制路径
          </button>
        </div>
        <button onClick={async () => {
          const dir = dataDir?.data_dir;
          if (!dir) return;
          if (window.speakwise?.openFolder) {
            window.speakwise.openFolder(dir);
          } else {
            navigator.clipboard.writeText(dir);
            toast.success("路径已复制（浏览器模式无法直接打开文件夹）");
          }
        }}
          className="text-xs text-indigo-600 hover:underline">
          📂 在文件管理器中打开
        </button>
      </section>
    </div>
  );
}

/* ── Voice Settings (iFlytek) ── */

function VoiceSettings({ flashSection }: { flashSection: string | null }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [appid, setAppid] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");

  const { data: savedVoice } = useQuery({
    queryKey: ["settings","voice"],
    queryFn: () => apiGet<{appid:string;api_key:string;api_secret:string}>("/api/settings/voice"),
  });
  useEffect(() => {
    if (savedVoice) { setAppid(savedVoice.appid||""); setApiKey(savedVoice.api_key||""); setApiSecret(savedVoice.api_secret||""); }
  }, [savedVoice]);

  const saveMut = useMutation({
    mutationFn: (d: Record<string,string>) => apiPut("/api/settings/voice", d),
    onSuccess: () => { toast.success("语音配置已保存"); qc.invalidateQueries({queryKey:["settings","voice"]}); },
    onError: (e: Error) => toast.error(e.message || "保存失败"),
  });

  return (
    <section className={`bg-white border rounded-xl p-5 mb-5 transition-all duration-700 ${
      flashSection === "voice" ? "border-amber-400 shadow-[0_0_20px_rgba(251,191,36,0.4)] bg-amber-50/30" : "border-zinc-200"
    }`}>
      <details open={flashSection === "voice"}>
        <summary className="font-semibold cursor-pointer">🎤 语音输入（讯飞）</summary>
        <p className="text-xs text-zinc-400 mt-2 mb-3">
          配置讯飞语音听写服务，即可使用麦克风语音输入。注册地址：<a href="https://www.xfyun.cn/" target="_blank" className="text-indigo-600 underline">xfyun.cn</a>
        </p>
        <div className="space-y-2">
          <input value={appid} onChange={e => setAppid(e.target.value)} placeholder="APPID" className="w-full text-xs border rounded-lg px-2 py-1.5 font-mono" />
          <input value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="API Key" className="w-full text-xs border rounded-lg px-2 py-1.5 font-mono" />
          <input value={apiSecret} onChange={e => setApiSecret(e.target.value)} placeholder="API Secret" type="password" className="w-full text-xs border rounded-lg px-2 py-1.5 font-mono" />
        </div>
        <button onClick={() => saveMut.mutate({appid, api_key: apiKey, api_secret: apiSecret})}
          className="text-xs bg-indigo-600 text-white rounded-lg px-3 py-1.5 mt-2 hover:bg-indigo-700">保存</button>
      </details>
    </section>
  );
}
