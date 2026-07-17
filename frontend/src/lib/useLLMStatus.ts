import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./api";

/** 检查 LLM 是否已配置的共享 hook */
export function useLLMStatus() {
  const { data } = useQuery({
    queryKey: ["llm-status"],
    queryFn: () => apiGet<{ configured: boolean; provider: string }>("/api/settings/llm/status"),
    staleTime: 0,  // 每次挂载都重新检查（端点轻量，只查数据库）
  });
  return {
    isConfigured: data?.configured ?? false,
    provider: data?.provider ?? "",
  };
}
