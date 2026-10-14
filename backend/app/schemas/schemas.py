"""
Pydantic 数据契约模块 (Schemas)：
定义前后端交互的所有请求体与响应体结构，同时兼容 Pydantic v1 (.dict) 与 Pydantic v2 (.model_dump)。
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CompatBaseModel(BaseModel):
    """兼容 Pydantic v1 与 v2 的基础模型类。"""

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        if hasattr(super(), "model_dump"):
            return super().model_dump(**kwargs)  # type: ignore
        return self.dict(**kwargs)


# ==================== 1. 认证与用户契约 ====================
class LoginRequest(CompatBaseModel):
    username: str = Field(..., description="登录账号（教师工号或学生学号/用户名）")
    password: str = Field(..., description="登录密码")


class UserOut(CompatBaseModel):
    id: int
    username: str
    full_name: str
    role: str
    student_no: Optional[str] = None
    class_name: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    created_at: str


class TokenResponse(CompatBaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ==================== 2. 学生管理契约 ====================
class StudentCreate(CompatBaseModel):
    student_no: str = Field(..., description="学号（同时作为默认登录用户名）")
    full_name: str = Field(..., description="学生姓名")
    class_name: str = Field(default="高一(1)班", description="所属班级")
    email: Optional[str] = Field(default=None, description="邮箱")
    password: str = Field(default="123456", description="初始登录密码，默认 123456")


class StudentUpdate(CompatBaseModel):
    student_no: Optional[str] = None
    full_name: Optional[str] = None
    class_name: Optional[str] = None
    email: Optional[str] = None


# ==================== 3. 双模式评分量规契约 ====================
class RubricLevelItem(CompatBaseModel):
    level_name: str = Field(..., description="等级名称，如 '抽象扩展结构 (Extended Abstract)' 或 '优秀 (A)'")
    score_range: str = Field(..., description="分值范围描述，如 '90-100%' 或 '20-25分'")
    min_ratio: float = Field(default=0.85, description="该等级最低得分率 (0.0-1.0)")
    max_ratio: float = Field(default=1.0, description="该等级最高得分率 (0.0-1.0)")
    description: str = Field(..., description="该等级的具体表现特征描述")


class RubricDimensionItem(CompatBaseModel):
    name: str = Field(..., description="评价维度名称，如 '论点深度与结构关联'")
    weight: float = Field(..., description="维度权重百分比（0-100），所有维度权重之和应为 100")
    max_score: float = Field(..., description="该维度满分分值")
    description: str = Field(default="", description="维度考察重点说明")
    levels: List[RubricLevelItem] = Field(default_factory=list, description="该维度下的等级划分描述")


class RubricConfirmRequest(CompatBaseModel):
    name: str = Field(..., description="量规名称")
    framework_type: str = Field(default="CUSTOM", description="框架类型: SOLO | BLOOM | CUSTOM")
    question_type: str = Field(default="开放论述题", description="适用题型")
    description: str = Field(default="", description="量规整体说明")
    total_points: float = Field(default=100.0, description="量规总分")
    dimensions: List[RubricDimensionItem] = Field(..., description="经用户确认后的评分维度列表")
    source_filename: Optional[str] = None
    raw_source_text: Optional[str] = None


class RubricOut(CompatBaseModel):
    id: int
    name: str
    mode: str
    framework_type: str
    question_type: str
    description: Optional[str] = None
    total_points: float
    dimensions: List[Dict[str, Any]]
    source_filename: Optional[str] = None
    is_confirmed: bool
    created_at: str


# ==================== 4. 评分明细与模糊澄清契约 ====================
class ClarificationQuestionItem(CompatBaseModel):
    id: str = Field(..., description="疑问点编号，如 Q1, Q2")
    category: str = Field(
        ...,
        description="疑问类别：'作业内容不清' | '量规维度不明' | '题目与量规不匹配'",
    )
    question: str = Field(..., description="向用户提出的具体澄清问题")
    context_excerpt: Optional[str] = Field(
        default=None, description="触发该疑问的作业片段或量规片段"
    )


class ClarificationAnswerItem(CompatBaseModel):
    id: str = Field(..., description="对应疑问点编号，如 Q1")
    question: str = Field(..., description="原澄清问题")
    answer: str = Field(..., description="教师/用户的补充澄清答复")


class ClarificationReplyRequest(CompatBaseModel):
    answers: List[ClarificationAnswerItem] = Field(
        ..., description="针对系统所提疑问点的逐条回复"
    )
    supplemental_text: Optional[str] = Field(
        default=None, description="可选：补充或修正后的作业正文文本"
    )


class DimensionScoreItem(CompatBaseModel):
    dimension_name: str = Field(..., description="评分维度名称")
    weight: float = Field(..., description="维度权重 (%)")
    max_score: float = Field(..., description="该维度满分")
    score: float = Field(..., description="该维度实际得分")
    level_reached: str = Field(..., description="达到的等级名称（如 SOLO 关联结构 / 布鲁姆分析层）")
    evidence_quote: str = Field(
        ..., description="【强制要求】直接引用的学生作业原文片段作为评分依据"
    )
    rationale: str = Field(
        ..., description="结合量规标准与原文引用的具体评分理由，禁止空泛评价"
    )
    dimension_suggestion: str = Field(
        default="", description="针对该维度的具体提升建议"
    )


class GradingTriggerRequest(CompatBaseModel):
    grading_mode: str = Field(
        default="authoritative",
        description="评分模式: 'authoritative' (模式A：权威默认量规自动匹配) | 'custom' (模式B：指定自定义量规)",
    )
    rubric_id: Optional[int] = Field(
        default=None,
        description="若为模式B，必传已确认的自定义量规 ID；若为模式A，可留空由系统按题型自动匹配",
    )
    force_grade_without_clarification: bool = Field(
        default=False,
        description="是否跳过模糊澄清检查（默认 False，严格执行模糊澄清机制）",
    )


class BatchGradeRequest(CompatBaseModel):
    submission_ids: List[int] = Field(..., description="待批量评分的作业 ID 列表")
    grading_mode: str = Field(default="authoritative")
    rubric_id: Optional[int] = None


class TeacherReviewRequest(CompatBaseModel):
    final_score: float = Field(..., description="教师复核后的最终总分")
    cognitive_level: Optional[str] = Field(default=None, description="复核后的认知层级")
    overall_comment: str = Field(..., description="复核后的综合评语")
    dimension_scores: List[DimensionScoreItem] = Field(
        ..., description="复核修正后的各维度分项得分与理由"
    )
    improvement_suggestions: List[str] = Field(
        ..., description="复核修正后的具体改进建议列表"
    )
    teacher_adjustment_note: str = Field(
        default="", description="教师手动修正说明（记录修正原因）"
    )


class SubmissionOut(CompatBaseModel):
    id: int
    assignment_title: str
    question_prompt: str
    question_type: str
    student_id: int
    student_no: str
    student_name: str
    class_name: Optional[str] = None
    submission_type: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    extracted_text: Optional[str] = None
    grading_mode: str
    rubric_id: Optional[int] = None
    matched_rubric_name: Optional[str] = None
    status: str
    clarification_questions: List[Dict[str, Any]] = Field(default_factory=list)
    clarification_answers: List[Dict[str, Any]] = Field(default_factory=list)
    total_score: Optional[float] = None
    final_score: Optional[float] = None
    cognitive_level: Optional[str] = None
    overall_comment: Optional[str] = None
    dimension_scores: List[Dict[str, Any]] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    teacher_adjustment_note: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str
    updated_at: str
