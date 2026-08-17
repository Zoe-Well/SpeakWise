import { SKILL_CATEGORIES, skillCategoryLabel } from "../lib/skillCategories";

export interface SkillClassificationPreview {
  id: number;
  name: string;
  current_category: string;
  suggested_category: string;
}

interface Props {
  preview: SkillClassificationPreview[];
  onCancel: () => void;
  onConfirm: (assignments: { id: number; category: string }[]) => void;
  saving?: boolean;
}

export default function SkillClassificationDialog({ preview, onCancel, onConfirm, saving = false }: Props) {
  const groups = SKILL_CATEGORIES.map((category) => ({
    ...category,
    skills: preview.filter((skill) => skillCategoryLabel(skill.suggested_category) === category.label),
  })).filter((category) => category.skills.length > 0);

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="skill-classification-title" className="bg-white rounded-xl shadow-2xl max-w-lg w-full">
        <div className="px-5 py-4">
          <h3 id="skill-classification-title" className="font-semibold text-base">AI 智能整理预览</h3>
          <p className="text-sm text-zinc-500 mt-2">请确认建议分类，保存后将批量更新技能分类。</p>
          <div className="mt-4 space-y-3 max-h-80 overflow-y-auto">
            {groups.map((group) => (
              <div key={group.key}>
                <h4 className="text-sm font-medium text-zinc-700 mb-1">{group.label}</h4>
                <div className="flex flex-wrap gap-2">
                  {group.skills.map((skill) => (
                    <span key={skill.id} className="text-xs bg-zinc-100 border border-zinc-200 rounded-lg px-2.5 py-1.5">{skill.name}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="px-5 py-3 border-t border-zinc-200 flex justify-end gap-2">
          <button disabled={saving} onClick={onCancel} className="px-4 py-2 border border-zinc-200 rounded-lg text-sm hover:bg-zinc-50 text-zinc-600 disabled:opacity-50">取消</button>
          <button
            disabled={saving}
            onClick={() => onConfirm(preview.map(({ id, suggested_category }) => ({
              id,
              category: SKILL_CATEGORIES.some(({ key }) => key === suggested_category) ? suggested_category : "other",
            })))}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 disabled:opacity-50"
          >确认保存</button>
        </div>
      </div>
    </div>
  );
}
