"""Job Description 分析服务"""

import json
import logging
from backend.src.llm.client import llm_client

JD_SYSTEM_PROMPT = """你是一个岗位描述（JD）解析器。从输入的 JD 文本中提取以下结构化信息，以严格 JSON 格式返回：

{
  "core_skills": ["技能1", "技能2", ...],       // 核心硬技能要求
  "duties": ["职责1", "职责2", ...],            // 主要岗位职责/业务场景
  "culture_values": ["价值观1", "价值观2", ...] // 公司价值观/业务方向
}

如果文本无法解析或为空，返回：
{"core_skills": [], "duties": [], "culture_values": [], "parse_error": "原因"}
"""


async def analyze_jd(jd_text: str) -> dict:
    """解析 JD 文本，返回结构化字段。失败时返回空字段 + parse_error。"""
    if not jd_text or not jd_text.strip():
        return {"core_skills": [], "duties": [], "culture_values": [], "parse_error": "empty input"}

    try:
        resp = await llm_client.chat(
            messages=[
                {"role": "system", "content": JD_SYSTEM_PROMPT},
                {"role": "user", "content": jd_text[:8000]},
            ],
            temperature=0.1,
        )
        return json.loads(resp)
    except Exception as e:
        logging.getLogger("speakwise").error("JD 解析失败: %s", e, exc_info=True)
        return {
            "core_skills": [],
            "duties": [],
            "culture_values": [],
            "parse_error": "JD 解析失败，请重试",
            "parse_status": "failed",
        }
