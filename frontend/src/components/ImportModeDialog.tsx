/** 导入模式选择弹窗：追加 vs 替换 */

import { useState } from "react";

interface Props {
  onConfirm: (mode: "append" | "replace") => void;
  onCancel: () => void;
}

export default function ImportModeDialog({ onConfirm, onCancel }: Props) {
  const [mode, setMode] = useState<"append" | "replace">("append");

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full">
        {/* Header */}
        <div className="px-5 py-4 border-b border-zinc-200">
          <h3 className="font-semibold text-base">选择导入方式</h3>
          <p className="text-xs text-zinc-500 mt-1">当前简历已有数据，请选择导入方式：</p>
        </div>

        {/* Options */}
        <div className="p-4 space-y-3">
          <label
            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
              mode === "append" ? "border-indigo-300 bg-indigo-50/50" : "border-zinc-200 hover:bg-zinc-50"
            }`}
          >
            <input
              type="radio"
              name="importMode"
              value="append"
              checked={mode === "append"}
              onChange={() => setMode("append")}
              className="mt-0.5 w-4 h-4 accent-indigo-600"
            />
            <div className="flex-1">
              <span className="text-sm font-medium text-zinc-700">更新追加</span>
              <p className="text-xs text-zinc-400 mt-0.5">保留现有实习/项目/技能数据，追加新解析的内容</p>
            </div>
          </label>

          <label
            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
              mode === "replace" ? "border-amber-300 bg-amber-50/50" : "border-zinc-200 hover:bg-zinc-50"
            }`}
          >
            <input
              type="radio"
              name="importMode"
              value="replace"
              checked={mode === "replace"}
              onChange={() => setMode("replace")}
              className="mt-0.5 w-4 h-4 accent-amber-500"
            />
            <div className="flex-1">
              <span className="text-sm font-medium text-zinc-700">完全替换</span>
              <p className="text-xs text-zinc-400 mt-0.5">清空现有实习/项目/技能，仅保留本次导入解析的内容</p>
            </div>
          </label>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-zinc-200 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 border border-zinc-200 rounded-lg text-sm hover:bg-zinc-50 text-zinc-600"
          >取消</button>
          <button
            onClick={() => onConfirm(mode)}
            className={`px-4 py-2 rounded-lg text-sm text-white ${
              mode === "replace" ? "bg-amber-500 hover:bg-amber-600" : "bg-indigo-600 hover:bg-indigo-700"
            }`}
          >
            {mode === "replace" ? "替换并上传" : "追加并上传"}
          </button>
        </div>
      </div>
    </div>
  );
}
