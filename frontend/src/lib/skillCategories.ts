export interface Skill {
  id: number;
  category: string;
  name: string;
  proficiency: string;
}

export const SKILL_CATEGORIES: readonly { key: string; label: string }[] = [
  { key: "programming_language", label: "编程语言" },
  { key: "frontend_client", label: "前端与客户端" },
  { key: "backend_data", label: "后端与数据" },
  { key: "ai_algorithm", label: "AI 与算法" },
  { key: "agent_llm", label: "Agent 与 LLM 应用" },
  { key: "cloud_devops", label: "云平台与 DevOps" },
  { key: "software_engineering", label: "软件工程能力" },
  { key: "other", label: "其他" },
];

export function skillCategoryLabel(key: string): string {
  return SKILL_CATEGORIES.find((category) => category.key === key)?.label ?? "其他";
}

export function groupSkillsByCategory(skills: Skill[]) {
  return SKILL_CATEGORIES.map((category) => ({
    ...category,
    skills: skills.filter((skill) => skillCategoryLabel(skill.category) === category.label),
  })).filter((category) => category.skills.length > 0);
}
