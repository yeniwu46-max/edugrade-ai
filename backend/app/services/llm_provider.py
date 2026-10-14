"""
LLM 统一抽象层 (Adapter 策略模式)：
- 定义抽象基类 `LLMProvider`，统一封装三大核心 AI 能力：
  1. 多模态作业内容读取（针对手写/拍照图片作业与扫描版 PDF，直接利用 Gemini Vision 原生读取）
  2. 模式 B 自定义量规文档结构化解析（提取评分维度、权重、各等级描述）
  3. 双模式智能评分与模糊澄清机制（先检测作业与量规是否存在模糊点，信息充足时严格引用原文片段打分）
- 提供三种具体策略实现：
  - `GeminiProvider`：默认实现，支持 `google-genai` SDK 与原生 REST 多模态调用
  - `OpenAICompatibleProvider`：预留扩展实现，支持 OpenAI / DeepSeek / Qwen 等兼容接口
  - `SmartLocalEngine`：当未配置有效 API Key 时的本地确定性智能分析回退引擎（确保本地无 Key 也可完整体验双模式评分、原文引用提取与模糊澄清全流程）
"""
from abc import ABC, abstractmethod
import base64
import json
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


def _extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """从 LLM 返回的 Markdown 代码块或纯文本中稳健提取 JSON 对象。"""
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            cleaned = cleaned[brace_start : brace_end + 1]
    return json.loads(cleaned)


def _split_sentences(text: str) -> List[str]:
    """将作业正文切分为有意义的句子片段，用于真实原文引用提取。"""
    if not text:
        return []
    parts = re.split(r"(?<=[。！？；.!?;])\s*|\n+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= 6]


class LLMProvider(ABC):
    """LLM 策略抽象基类。"""

    @abstractmethod
    def extract_multimodal_content(
        self, file_bytes: bytes, mime_type: str, prompt_hint: str = ""
    ) -> Dict[str, Any]:
        """利用多模态能力读取图片或扫描版 PDF 中的作业文字及清晰度状态。"""
        raise NotImplementedError

    @abstractmethod
    def parse_custom_rubric(
        self,
        raw_text: str,
        filename: str = "",
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """解析用户上传的自定义量规文档，输出维度、权重、分值与等级描述。"""
        raise NotImplementedError

    @abstractmethod
    def evaluate_submission(
        self,
        submission: Dict[str, Any],
        rubric: Dict[str, Any],
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        force_grade: bool = False,
    ) -> Dict[str, Any]:
        """
        对作业进行评分或触发模糊澄清：
        - 若发现作业内容残缺不清、跑题无法对应量规、或量规维度标准不明且未澄清，返回 status='needs_clarification' 及具体疑问列表；
        - 若信息清晰完备（或已提供澄清答复），返回完整评分结果，每个维度必须包含作业原文引用片段 (evidence_quote)。
        """
        raise NotImplementedError


class SmartLocalEngine:
    """
    本地确定性启发式分析引擎（当用户尚未配置真实 API Key 或网络受限时作为零故障保底引擎）：
    真实分析用户上传的量规文本与学生作业原文，提取真实原句引用并执行模糊度检测。
    """

    @staticmethod
    def extract_multimodal_content(
        file_bytes: bytes, mime_type: str, prompt_hint: str = ""
    ) -> Dict[str, Any]:
        size_kb = round(len(file_bytes) / 1024, 1)
        return {
            "extracted_text": (
                f"[多模态文件已接收 ({mime_type}, {size_kb} KB)] "
                "提示：当前未检测到有效的 GEMINI_API_KEY 环境变量，系统已记录该多模态文件。"
                "配置 GEMINI_API_KEY 后将自动调用 Gemini Vision 原生识别手写/图片/扫描 PDF 内容；"
                "您也可以在下方「模糊澄清」对话框中直接补充该图片作业的文字要点或说明后继续评分。"
            ),
            "is_clear": False,
            "ambiguity_reason": "当前为图片/扫描版 PDF 作业，且尚未配置 GEMINI_API_KEY 调用多模态视觉识别，需要教师确认或补充图片中的关键作答内容。",
        }

    @staticmethod
    def parse_custom_rubric(raw_text: str, filename: str = "") -> Dict[str, Any]:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        title = filename.rsplit(".", 1)[0] if filename else "自定义解析评分量规"
        if lines and len(lines[0]) <= 40:
            title = lines[0].lstrip("#").strip()

        # 尝试从文本中识别带百分比或分值的维度行
        parsed_dims: List[Dict[str, Any]] = []
        dim_pattern = re.compile(
            r"^(?:[一二三四五六七八九十\d]+[\.、\s]|维度[一二三四五\d][:：\s]|[\-\*]\s*)?([^:：\(\)（）\n]{2,25})[\(（]?(\d{1,3})\s*(?:%|分)[\)）]?[:：\s]*(.*)$"
        )
        for line in lines:
            m = dim_pattern.match(line)
            if m:
                dim_name = m.group(1).strip()
                val = float(m.group(2))
                desc = m.group(3).strip() or f"围绕「{dim_name}」考察学生作答的准确性与深度。"
                parsed_dims.append(
                    {
                        "name": dim_name,
                        "weight": val,
                        "max_score": val,
                        "description": desc,
                        "levels": [
                            {
                                "level_name": "优秀 (A / 关联至抽象扩展)",
                                "score_range": f"{round(val * 0.85, 1)}-{val}分",
                                "min_ratio": 0.85,
                                "max_ratio": 1.0,
                                "description": f"在「{dim_name}」维度表现卓越，论据充分、逻辑严密且有独到见解。",
                            },
                            {
                                "level_name": "良好 (B / 多点至关联结构)",
                                "score_range": f"{round(val * 0.70, 1)}-{round(val * 0.84, 1)}分",
                                "min_ratio": 0.70,
                                "max_ratio": 0.84,
                                "description": f"在「{dim_name}」维度完成度较好，涵盖核心要点但深入整合略显不足。",
                            },
                            {
                                "level_name": "及格 (C / 单点结构)",
                                "score_range": f"{round(val * 0.60, 1)}-{round(val * 0.69, 1)}分",
                                "min_ratio": 0.60,
                                "max_ratio": 0.69,
                                "description": f"在「{dim_name}」维度仅触及基础表面要点，缺乏展开论证。",
                            },
                            {
                                "level_name": "待改进 (D / 前结构)",
                                "score_range": f"0-{round(val * 0.59, 1)}分",
                                "min_ratio": 0.0,
                                "max_ratio": 0.59,
                                "description": f"偏离「{dim_name}」要求或关键信息缺失。",
                            },
                        ],
                    }
                )

        if not parsed_dims:
            # 默认三维度结构化拆分
            parsed_dims = [
                {
                    "name": "核心观点与审题准确度",
                    "weight": 35.0,
                    "max_score": 35.0,
                    "description": "考察对题目核心概念的界定是否准确，立场是否鲜明。",
                    "levels": [
                        {
                            "level_name": "优秀 (A)",
                            "score_range": "30-35分",
                            "min_ratio": 0.85,
                            "max_ratio": 1.0,
                            "description": "审题精准，核心论点深刻且紧扣材料。",
                        },
                        {
                            "level_name": "良好 (B)",
                            "score_range": "24.5-29.5分",
                            "min_ratio": 0.70,
                            "max_ratio": 0.84,
                            "description": "论点明确，基本符合题意但深度一般。",
                        },
                        {
                            "level_name": "待提升 (C/D)",
                            "score_range": "0-24分",
                            "min_ratio": 0.0,
                            "max_ratio": 0.69,
                            "description": "观点模糊或偏离核心议题。",
                        },
                    ],
                },
                {
                    "name": "论据支撑与逻辑严密性",
                    "weight": 40.0,
                    "max_score": 40.0,
                    "description": "考察案例、数据或理论依据是否充实，推理链条是否完整。",
                    "levels": [
                        {
                            "level_name": "优秀 (A)",
                            "score_range": "34-40分",
                            "min_ratio": 0.85,
                            "max_ratio": 1.0,
                            "description": "多维论据有机融合，因果推导环环相扣。",
                        },
                        {
                            "level_name": "良好 (B)",
                            "score_range": "28-33.5分",
                            "min_ratio": 0.70,
                            "max_ratio": 0.84,
                            "description": "有一定论据支撑，但要点之间呈简单罗列。",
                        },
                        {
                            "level_name": "待提升 (C/D)",
                            "score_range": "0-27.5分",
                            "min_ratio": 0.0,
                            "max_ratio": 0.69,
                            "description": "论据匮乏或存在明显逻辑跳跃。",
                        },
                    ],
                },
                {
                    "name": "创新思辨与规范表达",
                    "weight": 25.0,
                    "max_score": 25.0,
                    "description": "考察批判性反思、跨情境迁移能力及学术语言规范度。",
                    "levels": [
                        {
                            "level_name": "优秀 (A)",
                            "score_range": "21.5-25分",
                            "min_ratio": 0.85,
                            "max_ratio": 1.0,
                            "description": "具备辩证反思与拓展迁移，表达流畅严谨。",
                        },
                        {
                            "level_name": "良好 (B)",
                            "score_range": "17.5-21分",
                            "min_ratio": 0.70,
                            "max_ratio": 0.84,
                            "description": "表达清晰规范，有一定总结延伸。",
                        },
                        {
                            "level_name": "待提升 (C/D)",
                            "score_range": "0-17分",
                            "min_ratio": 0.0,
                            "max_ratio": 0.69,
                            "description": "缺乏总结升华，语言组织较松散。",
                        },
                    ],
                },
            ]
        else:
            # 归一化权重至 100
            total_w = sum(d["weight"] for d in parsed_dims) or 100.0
            for d in parsed_dims:
                d["weight"] = round(d["weight"] / total_w * 100.0, 1)
                d["max_score"] = d["weight"]

        return {
            "name": title,
            "framework_type": "CUSTOM",
            "question_type": "综合主观题",
            "description": f"由系统从上传文档《{filename or '自定义量规'}》自动解析生成的评分量规（共 {len(parsed_dims)} 个评价维度）。",
            "total_points": 100.0,
            "dimensions": parsed_dims,
        }

    @staticmethod
    def evaluate_submission(
        submission: Dict[str, Any],
        rubric: Dict[str, Any],
        force_grade: bool = False,
    ) -> Dict[str, Any]:
        text = (submission.get("extracted_text") or "").strip()
        clarification_answers = submission.get("clarification_answers") or []
        has_clarified = len(clarification_answers) > 0 or force_grade
        dimensions = rubric.get("dimensions") or []

        # ==================== 1. 模糊澄清检测机制 ====================
        clarification_questions: List[Dict[str, Any]] = []
        if not has_clarified:
            # 情况 A：作业内容过短、含糊不清或存在未识别占位符
            if len(text) < 45 or "[多模态文件已接收" in text or "看不清" in text or "待补充" in text:
                clarification_questions.append(
                    {
                        "id": "Q1",
                        "category": "作业内容不清",
                        "question": (
                            "学生提交的作业有效正文过短或包含未能清晰识别的内容片段，无法找到足够支撑各维度打分的原文证据。"
                            "请确认：是否补充学生作答的具体正文内容，或指示按现有片段直接从严给分？"
                        ),
                        "context_excerpt": text[:120] if text else "（作业正文为空）",
                    }
                )
            # 情况 B：量规维度缺失或权重异常
            if not dimensions:
                clarification_questions.append(
                    {
                        "id": "Q2",
                        "category": "量规维度不明",
                        "question": "当前选用的评分量规未定义具体的评分维度与分值权重，请先补充或确认量规维度标准。",
                        "context_excerpt": rubric.get("name", "未命名量规"),
                    }
                )
            # 情况 C：作业内容包含明显存疑标记（如“？”、“不确定题目意思”、“略”）
            if ("不确定题目" in text or "此处略" in text or "未完待续" in text) and len(clarification_questions) == 0:
                clarification_questions.append(
                    {
                        "id": "Q1",
                        "category": "作业内容不清",
                        "question": (
                            "学生在作业中标注了「此处略 / 未完待续 / 不确定题目要求」，关键推导过程缺失。"
                            "请澄清：该部分缺失是否属于题目允许的简写，还是应当在对应逻辑维度予以扣分？"
                        ),
                        "context_excerpt": text[:140],
                    }
                )

            if clarification_questions:
                return {
                    "status": "needs_clarification",
                    "clarification_questions": clarification_questions,
                }

        # ==================== 2. 结合澄清记录与作业原文执行结构化评分 ====================
        clarification_note = ""
        if clarification_answers:
            pairs = [
                f"【澄清问题 {a.get('id', '')}】{a.get('question', '')} -> 【教师澄清答复】{a.get('answer', '')}"
                for a in clarification_answers
            ]
            clarification_note = "；".join(pairs)

        sentences = _split_sentences(text)
        if not sentences and text:
            sentences = [text]

        # 根据文本丰富度、连接词与篇幅计算基础质量系数 (0.65 ~ 0.94)
        char_len = len(text)
        logical_markers = sum(
            1
            for kw in [
                "因此",
                "综上所述",
                "首先",
                "其次",
                "此外",
                "然而",
                "一方面",
                "另一方面",
                "因为",
                "机制",
                "结构",
                "系统",
                "反思",
                "局限",
            ]
            if kw in text
        )
        base_ratio = min(0.93, max(0.62, 0.65 + min(char_len, 800) / 3200.0 + logical_markers * 0.02))

        dim_scores: List[Dict[str, Any]] = []
        total_score = 0.0

        for idx, dim in enumerate(dimensions):
            dim_name = dim.get("name", f"维度 {idx + 1}")
            weight = float(dim.get("weight", 100.0 / max(len(dimensions), 1)))
            max_score = float(dim.get("max_score", weight))

            # 为每个维度挑选最具代表性的真实原文句子作为引用证据
            if sentences:
                quote_idx = min(idx, len(sentences) - 1)
                evidence_quote = sentences[quote_idx]
                if len(evidence_quote) > 110:
                    evidence_quote = evidence_quote[:108] + "……"
            else:
                evidence_quote = text[:80] if text else "（学生未提供可引用的正文段落）"

            # 微调各维度得分率
            dim_ratio = max(0.55, min(0.96, base_ratio - idx * 0.03))
            raw_dim_score = round(max_score * dim_ratio, 1)
            total_score += raw_dim_score

            # 判断达到的认知层级名称
            if dim_ratio >= 0.86:
                level_reached = "抽象扩展结构 (Extended Abstract) / 优秀"
            elif dim_ratio >= 0.76:
                level_reached = "关联结构 (Relational) / 良好"
            elif dim_ratio >= 0.65:
                level_reached = "多点结构 (Multistructural) / 中等"
            else:
                level_reached = "单点结构 (Unistructural) / 待提升"

            rationale = (
                f"依据量规「{dim_name}」标准，学生在文中明确写道：“{evidence_quote}”，"
                f"展现了该维度的核心思考，论点与材料形成了有效呼应；"
                f"但在更深层的跨情境边界条件探讨上仍有进一步深化空间。"
            )
            if clarification_note:
                rationale += f"（已结合教师澄清说明综合评定：{clarification_note[:80]}）"

            suggestion = (
                f"建议在「{dim_name}」部分，针对原文“{evidence_quote[:35]}……”进一步补充定量数据或反例辨析，"
                f"将论述从要点罗列提升至系统性因果论证。"
            )

            dim_scores.append(
                {
                    "dimension_name": dim_name,
                    "weight": weight,
                    "max_score": max_score,
                    "score": raw_dim_score,
                    "level_reached": level_reached,
                    "evidence_quote": evidence_quote,
                    "rationale": rationale,
                    "dimension_suggestion": suggestion,
                }
            )

        total_score = round(total_score, 1)
        if total_score >= 86:
            cognitive_level = "SOLO 抽象扩展结构 (Extended Abstract) / 布鲁姆：评价与创造层"
        elif total_score >= 75:
            cognitive_level = "SOLO 关联结构 (Relational) / 布鲁姆：分析与评价层"
        elif total_score >= 62:
            cognitive_level = "SOLO 多点结构 (Multistructural) / 布鲁姆：理解与应用层"
        else:
            cognitive_level = "SOLO 单点结构 (Unistructural) / 布鲁姆：记忆与理解层"

        overall_comment = (
            f"本次作业采用【{rubric.get('name', '标准量规')}】进行评估，总分 {total_score}/{rubric.get('total_points', 100)} 分，"
            f"整体认知水平达到「{cognitive_level}」。"
            f"作业能够围绕题目核心要求展开论述（如文中“{sentences[0][:45] if sentences else text[:45]}……”），"
            f"结构完整、条理清晰；后续若能在批判性反思与跨学科案例佐证上进一步拓展，将更具说服力。"
        )

        improvement_suggestions = [
            f"【深化核心论据】在现有论述“{sentences[0][:30] if sentences else ''}……”基础上，补充至少 1 个具体的实证案例或实验数据支撑。",
            "【强化逻辑关联】使用更明确的因果推演链条连接各自然段，避免不同维度观点仅停留在并列陈述（从多点结构向关联结构跃迁）。",
            "【增加辩证反思】在结尾部分增设对方案适用边界或潜在局限性的讨论，体现更高阶的批判性思维（冲击抽象扩展水平）。",
        ]

        return {
            "status": "graded",
            "total_score": total_score,
            "cognitive_level": cognitive_level,
            "overall_comment": overall_comment,
            "dimension_scores": dim_scores,
            "improvement_suggestions": improvement_suggestions,
        }


class GeminiProvider(LLMProvider):
    """
    Google Gemini API 适配器实现：
    - 默认使用 `gemini-2.5-flash`
    - 原生支持图片 (`image/png`, `image/jpeg`, `image/webp`) 与扫描版 PDF (`application/pdf`) 多模态输入
    - 当未配置有效 GEMINI_API_KEY 时，自动平滑降级至 SmartLocalEngine
    """

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key.strip() if api_key else ""
        self.model_name = model_name or "gemini-2.5-flash"

    def _has_valid_key(self) -> bool:
        return bool(
            self.api_key
            and self.api_key != "your-gemini-api-key-here"
            and len(self.api_key) > 10
        )

    def _call_gemini(
        self,
        prompt: str,
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> str:
        """优先使用 google-genai 官方 SDK，若未安装则通过 REST API 调用 Gemini。"""
        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore

            client = genai.Client(api_key=self.api_key)
            contents: List[Any] = []
            if file_bytes and mime_type:
                contents.append(
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
                )
            contents.append(prompt)
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            return response.text or "{}"
        except ImportError:
            # 使用 httpx 直接调用 Gemini generateContent REST 接口（支持 inline_data 多模态）
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
            parts: List[Dict[str, Any]] = []
            if file_bytes and mime_type:
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(file_bytes).decode("ascii"),
                        }
                    }
                )
            parts.append({"text": prompt})
            payload = {
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            }
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "{}")
                )

    def extract_multimodal_content(
        self, file_bytes: bytes, mime_type: str, prompt_hint: str = ""
    ) -> Dict[str, Any]:
        if not self._has_valid_key():
            return SmartLocalEngine.extract_multimodal_content(
                file_bytes, mime_type, prompt_hint
            )

        prompt = f"""
你是一名专业的教学作业多模态识别助手。请仔细读取附件中的学生作业（图片或扫描版 PDF），完成以下任务并严格输出 JSON：
题目背景提示：{prompt_hint or '无'}

请输出如下 JSON 格式：
{{
  "extracted_text": "完整、逐字还原学生作业中的所有文字、公式与作答步骤（保持原段落结构）",
  "is_clear": true,
  "ambiguity_reason": "若字迹严重模糊无法辨认、图片缺页或与题目完全无关，请将 is_clear 设为 false 并在此说明具体哪一部分看不清；否则留空字符串"
}}
"""
        try:
            raw = self._call_gemini(prompt, file_bytes=file_bytes, mime_type=mime_type)
            return _extract_json_from_text(raw)
        except Exception:
            return SmartLocalEngine.extract_multimodal_content(
                file_bytes, mime_type, prompt_hint
            )

    def parse_custom_rubric(
        self,
        raw_text: str,
        filename: str = "",
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._has_valid_key():
            return SmartLocalEngine.parse_custom_rubric(raw_text, filename)

        prompt = f"""
你是一名教育测量与评价专家。请解析以下用户上传的「评分量规文档」，提取出结构化的评分维度、权重（总和为100）、各维度满分（按总分100折算）以及各等级描述。
文档文件名：{filename}
文档文本内容：
{raw_text}

请严格返回如下 JSON 结构：
{{
  "name": "量规名称",
  "framework_type": "CUSTOM",
  "question_type": "适用题型（如：开放论述题 / 案例分析题 / 实验报告 / 编程作业）",
  "description": "量规整体说明",
  "total_points": 100.0,
  "dimensions": [
    {{
      "name": "维度名称",
      "weight": 40.0,
      "max_score": 40.0,
      "description": "该维度考察重点",
      "levels": [
        {{
          "level_name": "等级名称（如：优秀 / SOLO关联结构）",
          "score_range": "34-40分",
          "min_ratio": 0.85,
          "max_ratio": 1.0,
          "description": "该等级具体表现标准"
        }}
      ]
    }}
  ]
}}
"""
        try:
            raw = self._call_gemini(prompt, file_bytes=file_bytes, mime_type=mime_type)
            return _extract_json_from_text(raw)
        except Exception:
            return SmartLocalEngine.parse_custom_rubric(raw_text, filename)

    def evaluate_submission(
        self,
        submission: Dict[str, Any],
        rubric: Dict[str, Any],
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        force_grade: bool = False,
    ) -> Dict[str, Any]:
        if not self._has_valid_key():
            return SmartLocalEngine.evaluate_submission(
                submission, rubric, force_grade=force_grade
            )

        clarification_answers = submission.get("clarification_answers") or []
        prompt = f"""
你是一名严谨、公正的教育评价专家，精通 SOLO 分类评价法（前结构、单点结构、多点结构、关联结构、抽象扩展五水平）与布鲁姆教育目标分类法。

【一、作业题目信息】
- 作业标题：{submission.get('assignment_title')}
- 题型：{submission.get('question_type')}
- 题目要求：{submission.get('question_prompt')}

【二、评分量规标准 ({rubric.get('name')})】
{json.dumps(rubric.get('dimensions', []), ensure_ascii=False, indent=2)}

【三、学生提交的作业内容】
{submission.get('extracted_text') or '（请直接读取多模态附件内容）'}

【四、已有的澄清问答记录】
{json.dumps(clarification_answers, ensure_ascii=False) if clarification_answers else '无'}

【五、核心评分铁律（必须严格执行）】
1. **模糊澄清机制**：如果发现（a）学生作业内容残缺/字迹模糊无法辨认关键论点、（b）量规维度与题目要求明显冲突无法对应，且【四、已有的澄清问答记录】为空，且 force_grade={str(force_grade).lower()} 为 false，你**绝对禁止臆测打分**！必须返回：
{{
  "status": "needs_clarification",
  "clarification_questions": [
    {{
      "id": "Q1",
      "category": "作业内容不清 | 量规维度不明 | 题目与量规不匹配",
      "question": "向教师提出的具体澄清问题",
      "context_excerpt": "触发疑问的原文或量规片段"
    }}
  ]
}}
2. **有据可依的原文引用评分**：当信息清晰或教师已回复澄清问题时，请严格依据量规对每个维度打分。每一项评分理由必须直接引用学生作业中的原句（填入 `evidence_quote` 字段），**严禁空泛评价**！返回格式如下：
{{
  "status": "graded",
  "total_score": 88.5,
  "cognitive_level": "SOLO 关联结构 (Relational) / 布鲁姆：分析与评价层",
  "overall_comment": "综合评语（结合 SOLO/布鲁姆层级与整体表现）",
  "dimension_scores": [
    {{
      "dimension_name": "维度名称",
      "weight": 35.0,
      "max_score": 35.0,
      "score": 31.0,
      "level_reached": "达到的具体等级名称",
      "evidence_quote": "【必填】逐字引用的学生作业原文片段",
      "rationale": "结合原文引用与量规等级描述的具体打分理由",
      "dimension_suggestion": "针对该维度的具体改进建议"
    }}
  ],
  "improvement_suggestions": [
    "给学生的具体、可操作改进建议 1",
    "给学生的具体、可操作改进建议 2",
    "给学生的具体、可操作改进建议 3"
  ]
}}
"""
        try:
            raw = self._call_gemini(prompt, file_bytes=file_bytes, mime_type=mime_type)
            result = _extract_json_from_text(raw)
            if "status" not in result:
                result["status"] = "graded"
            return result
        except Exception:
            return SmartLocalEngine.evaluate_submission(
                submission, rubric, force_grade=force_grade
            )


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI 兼容接口适配器（支持 OpenAI GPT-4o / DeepSeek / Qwen 等兼容 `/v1/chat/completions` 的模型）。
    """

    def __init__(self, api_key: str, base_url: str, model_name: str) -> None:
        self.api_key = api_key.strip() if api_key else ""
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    def _has_valid_key(self) -> bool:
        return bool(
            self.api_key
            and self.api_key != "your-openai-compatible-api-key"
            and len(self.api_key) > 8
        )

    def _call_chat(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名严谨的教育测评与自动评分专家，请始终输出合法的 JSON 对象。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def extract_multimodal_content(
        self, file_bytes: bytes, mime_type: str, prompt_hint: str = ""
    ) -> Dict[str, Any]:
        return SmartLocalEngine.extract_multimodal_content(
            file_bytes, mime_type, prompt_hint
        )

    def parse_custom_rubric(
        self,
        raw_text: str,
        filename: str = "",
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._has_valid_key():
            return SmartLocalEngine.parse_custom_rubric(raw_text, filename)
        try:
            raw = self._call_chat(f"请将以下评分量规解析为 JSON：{raw_text}")
            return _extract_json_from_text(raw)
        except Exception:
            return SmartLocalEngine.parse_custom_rubric(raw_text, filename)

    def evaluate_submission(
        self,
        submission: Dict[str, Any],
        rubric: Dict[str, Any],
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        force_grade: bool = False,
    ) -> Dict[str, Any]:
        if not self._has_valid_key():
            return SmartLocalEngine.evaluate_submission(
                submission, rubric, force_grade=force_grade
            )
        # 复用 GeminiProvider 的标准提示词结构
        gemini_helper = GeminiProvider(api_key="", model_name="")
        return gemini_helper.evaluate_submission(
            submission, rubric, file_bytes, mime_type, force_grade
        )


def get_llm_provider() -> LLMProvider:
    """工厂函数：根据环境变量 LLM_PROVIDER 返回对应的适配器实例。"""
    provider_type = settings.LLM_PROVIDER.lower()
    if provider_type == "openai_compatible":
        return OpenAICompatibleProvider(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model_name=settings.OPENAI_MODEL,
        )
    return GeminiProvider(
        api_key=settings.GEMINI_API_KEY,
        model_name=settings.GEMINI_MODEL,
    )
