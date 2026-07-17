/** LLM API Key 未配置时弹出的引导弹窗 */

interface Props {
  open: boolean;
  onClose: () => void;
  featureName?: string;
  /** 服务描述，默认 "LLM 服务"，语音场景传 "讯飞语音服务" */
  serviceName?: string;
  /** 跳转到设置页后高亮的区域：llm | voice */
  highlight?: string;
}

export default function ApiKeyRequiredDialog({ open, onClose, featureName, serviceName = "LLM 服务", highlight }: Props) {
  if (!open) return null;

  const handleGoSettings = () => {
    onClose();
    window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "settings", highlight } }));
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-sm w-full">
        <div className="px-5 py-4">
          <h3 className="font-semibold text-base">需要配置 API Key</h3>
          <p className="text-sm text-zinc-500 mt-2">
            {featureName ? `「${featureName}」功能依赖${serviceName}，` : `此功能依赖${serviceName}，`}
            请先配置 API Key 后重试。
          </p>
        </div>
        <div className="px-5 py-3 border-t border-zinc-200 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-zinc-200 rounded-lg text-sm hover:bg-zinc-50 text-zinc-600"
          >取消</button>
          <button
            onClick={handleGoSettings}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700"
          >前往设置</button>
        </div>
      </div>
    </div>
  );
}
