"""
AI 内容生成服务
通过 HTTP 调用 AI API 生成各类内容
"""
import os
import json
import httpx


class AIService:
    """AI 服务封装，支持 OpenAI 兼容 API"""

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("AI_MODEL", "gpt-4o")
        self.timeout = 120.0

    def set_config(self, api_key: str = "", base_url: str = "", model: str = ""):
        """按请求覆盖 API 配置"""
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url
        if model:
            self.model = model

    async def _call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000, temperature: float = 0.7) -> str:
        """调用 AI API"""
        if not self.api_key:
            raise ValueError("请设置环境变量 OPENAI_API_KEY")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> dict:
        """调用 AI API 并解析 JSON 返回"""
        raw = await self._call(system_prompt, user_prompt, max_tokens, temperature=0.3)
        # 清理 markdown 代码块
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
        return json.loads(clean)

    async def generate_updated_resume(self, resume_text: str, jd_text: str) -> str:
        """根据 JD 优化简历内容"""
        system_prompt = """你是一位资深的简历优化专家和招聘顾问。你的任务是根据岗位描述(JD)优化候选人的简历。

请仔细分析JD中的岗位职责和任职要求，然后对简历进行针对性优化，使简历内容更好地匹配目标岗位。

优化原则：
1. 保留简历中真实的工作经历和项目经验，不编造虚假内容
2. 突出与JD要求匹配的技能和经验
3. 使用JD中的关键词和术语，使简历更贴合岗位要求
4. 优化工作经历和项目描述的表述方式，使其更加专业和有说服力
5. 在简历开头增加"求职意向"部分，明确目标岗位
6. 保持简历结构清晰、格式规范

请直接输出优化后的完整简历文本，不要输出任何其他说明。"""

        user_prompt = f"""【岗位描述】
{jd_text}

【原始简历】
{resume_text}

请根据以上岗位描述，优化并输出完整的简历文本。"""

        return await self._call(system_prompt, user_prompt, max_tokens=4000, temperature=0.5)

    async def generate_ppt_content(self, resume_text: str, jd_text: str) -> dict:
        """生成面试PPT内容结构"""
        system_prompt = """你是一位专业的面试辅导专家。请根据候选人的简历和目标岗位的JD，生成一份面试演示PPT的内容大纲。

返回严格的JSON格式，结构如下：
{
  "title": "PPT标题",
  "subtitle": "副标题",
  "slides": [
    {
      "title": "幻灯片标题",
      "content": ["要点1", "要点2", "要点3"],
      "notes": "演讲备注"
    }
  ]
}

PPT内容应包含以下部分（共8-12页）：
1. 封面页：候选人姓名 + 目标岗位
2. 个人简介：教育背景、核心优势
3. 岗位理解：对目标岗位的理解和认知
4. 专业技能：与岗位匹配的技术能力
5. 工作经历亮点：与岗位最相关的工作经历
6. 项目经验展示：重点项目成果
7. 个人优势：与岗位匹配的软实力
8. 职业规划：未来发展方向
9. 结束页：感谢语和联系方式

请确保内容专业、有说服力，能帮助候选人在面试中脱颖而出。"""

        user_prompt = f"""【岗位描述】
{jd_text}

【候选人简历】
{resume_text}

请生成面试PPT内容大纲。"""

        return await self._call_json(system_prompt, user_prompt, max_tokens=4000)

    async def generate_script(self, resume_text: str, jd_text: str, ppt_content: dict) -> str:
        """生成面试PPT逐页讲稿"""
        slides_json = json.dumps(ppt_content.get("slides", []), ensure_ascii=False, indent=2)

        system_prompt = """你是一位资深的面试演讲教练。请根据面试PPT的内容，为每一页幻灯片生成详细的演讲讲稿。

讲稿要求：
1. 每页讲稿以"第X页：[标题]"开头
2. 用自然的口语化语言撰写，像是真实面试中的表达
3. 每页讲稿控制在150-300字，适合1-2分钟演讲
4. 包含开场白、过渡语和结束语
5. 标注每页建议演讲时长
6. 对于关键页面，提供"强调要点"提示
7. 整体风格自信、专业但不生硬

请直接输出完整的讲稿文本。"""

        user_prompt = f"""【岗位描述】
{jd_text}

【候选人简历】
{resume_text}

【PPT内容】
{slides_json}

请为以上PPT生成完整的逐页面试讲稿。"""

        return await self._call(system_prompt, user_prompt, max_tokens=4000, temperature=0.7)

    async def generate_interview_questions(self, resume_text: str, jd_text: str) -> dict:
        """生成面试提问"""
        system_prompt = """你是一位专业的面试官和技术面试专家。请根据岗位JD和候选人简历，生成一份全面的面试提问清单。

返回严格的JSON格式：
{
  "self_intro_questions": ["自我介绍相关问题"],
  "technical_questions": [
    {"question": "技术问题", "purpose": "考察目的", "expected_answer_hint": "期望回答要点"}
  ],
  "project_questions": [
    {"question": "项目相关问题", "purpose": "考察目的", "expected_answer_hint": "期望回答要点"}
  ],
  "behavioral_questions": [
    {"question": "行为面试问题", "purpose": "考察目的", "expected_answer_hint": "期望回答要点"}
  ],
  "jd_match_questions": [
    {"question": "岗位匹配问题", "purpose": "考察目的", "expected_answer_hint": "期望回答要点"}
  ],
  "reverse_questions": ["建议反问面试官的问题"]
}

要求：
1. 技术问题要针对JD中的技术栈和简历中的项目经验
2. 项目问题要深挖简历中的项目细节
3. 行为问题要考察团队协作、问题解决等软技能
4. 岗位匹配问题要考察候选人对岗位的理解
5. 每个类别3-5个问题
6. 问题要有深度，能考察候选人的真实水平"""

        user_prompt = f"""【岗位描述】
{jd_text}

【候选人简历】
{resume_text}

请生成面试提问清单。"""

        return await self._call_json(system_prompt, user_prompt, max_tokens=4000)


import re  # noqa: E402

# 全局单例
ai_service = AIService()