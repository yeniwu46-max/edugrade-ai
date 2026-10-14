"""
AI 自动评分、模糊澄清机制、教师人工复核与 Excel 成绩导出路由 (`app/routers/grading.py`)：
- POST /api/grading/{submission_id}/evaluate: 执行双模式自动评分（若存在模糊疑问点则暂停评分并返回澄清问题列表）
- POST /api/grading/{submission_id}/clarify: 提交模糊澄清答复并完成正式评分
- POST /api/grading/batch-evaluate: 批量自动评分
- PUT  /api/grading/{submission_id}/review: 教师人工复核与分数/评语修正
- GET  /api/grading/export/excel: 导出包含分维度得分、原文引用与改进建议的 Excel 成绩单 (.xlsx)
"""
from datetime import datetime
import io
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.database import DatabaseRepository, get_db_repository
from app.core.security import get_current_user, require_teacher
from app.schemas.schemas import (
    BatchGradeRequest,
    ClarificationReplyRequest,
    GradingTriggerRequest,
    SubmissionOut,
    TeacherReviewRequest,
)
from app.services.llm_provider import get_llm_provider
from app.services.seed_data import match_authoritative_rubric

router = APIRouter(prefix="/api/grading", tags=["AI双模式评分与复核导出"])


def _run_single_evaluation(
    sub: Dict[str, Any],
    grading_mode: str,
    rubric_id: Optional[int],
    force_grade: bool,
    repo: DatabaseRepository,
) -> Dict[str, Any]:
    """内部辅助函数：为单份作业匹配量规并调用 LLM 策略层执行模糊检测与打分。"""
    rubric = None
    if grading_mode == "custom" and rubric_id:
        rubric = repo.get_rubric_by_id(rubric_id)
        if not rubric:
            raise HTTPException(status_code=404, detail="指定的自定义量规不存在")
        if not rubric.get("is_confirmed", True):
            raise HTTPException(
                status_code=400, detail="该自定义量规尚未确认，请先确认量规维度后再评分"
            )
    elif rubric_id:
        rubric = repo.get_rubric_by_id(rubric_id)

    if not rubric:
        rubric = match_authoritative_rubric(
            question_type=sub.get("question_type", "开放论述题"),
            question_prompt=sub.get("question_prompt", ""),
            repo=repo,
        )

    # 若作业包含图片或 PDF 原始文件，读取二进制供 Gemini 多模态直接参考
    file_bytes: Optional[bytes] = None
    mime_type: Optional[str] = sub.get("mime_type")
    if sub.get("file_path") and sub.get("submission_type") in ["image", "pdf"]:
        fpath = Path(sub["file_path"])
        if fpath.exists():
            file_bytes = fpath.read_bytes()

    llm = get_llm_provider()
    eval_result = llm.evaluate_submission(
        submission=sub,
        rubric=rubric,
        file_bytes=file_bytes,
        mime_type=mime_type,
        force_grade=force_grade,
    )

    if eval_result.get("status") == "needs_clarification":
        return repo.update_submission_grading(
            sub["id"],
            {
                "status": "needs_clarification",
                "grading_mode": grading_mode,
                "rubric_id": rubric["id"],
                "matched_rubric_name": rubric["name"],
                "clarification_questions": eval_result.get(
                    "clarification_questions", []
                ),
            },
        )  # type: ignore

    total_score = float(eval_result.get("total_score", 0.0))
    return repo.update_submission_grading(
        sub["id"],
        {
            "status": "graded",
            "grading_mode": grading_mode,
            "rubric_id": rubric["id"],
            "matched_rubric_name": rubric["name"],
            "total_score": total_score,
            "final_score": total_score,
            "cognitive_level": eval_result.get("cognitive_level", ""),
            "overall_comment": eval_result.get("overall_comment", ""),
            "dimension_scores": eval_result.get("dimension_scores", []),
            "improvement_suggestions": eval_result.get(
                "improvement_suggestions", []
            ),
        },
    )  # type: ignore


@router.post("/{submission_id}/evaluate", response_model=SubmissionOut)
def evaluate_submission_endpoint(
    submission_id: int,
    req: GradingTriggerRequest,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """
    触发单份作业的双模式自动评分：
    - 模式 A (`authoritative`)：根据题型自动匹配 SOLO 五水平或布鲁姆六层级权威量规；
    - 模式 B (`custom`)：依据用户已确认的自定义量规评分；
    - 若检测到作业或量规存在模糊不清之处，状态转为 `needs_clarification` 并返回具体疑问点列表。
    """
    sub = repo.get_submission_by_id(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="作业不存在")

    return _run_single_evaluation(
        sub=sub,
        grading_mode=req.grading_mode,
        rubric_id=req.rubric_id or sub.get("rubric_id"),
        force_grade=req.force_grade_without_clarification,
        repo=repo,
    )


@router.post("/{submission_id}/clarify", response_model=SubmissionOut)
def submit_clarification_and_regrade(
    submission_id: int,
    req: ClarificationReplyRequest,
    _user: Dict[str, Any] = Depends(get_current_user),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """
    模糊澄清答复接口：
    当作业处于 `needs_clarification` 状态时，接收教师或用户的具体澄清答复（及可选补充正文），
    记录澄清上下文后立即完成结构化评分。
    """
    sub = repo.get_submission_by_id(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="作业不存在")

    updated_text = sub.get("extracted_text") or ""
    if req.supplemental_text and req.supplemental_text.strip():
        updated_text = (
            f"{updated_text}\n\n【澄清补充正文】：{req.supplemental_text.strip()}"
        ).strip()

    answers_dump = [a.model_dump() for a in req.answers]
    sub = repo.update_submission_grading(
        submission_id,
        {
            "extracted_text": updated_text,
            "clarification_answers": answers_dump,
        },
    )  # type: ignore

    return _run_single_evaluation(
        sub=sub,
        grading_mode=sub.get("grading_mode", "authoritative"),
        rubric_id=sub.get("rubric_id"),
        force_grade=True,
        repo=repo,
    )


@router.post("/batch-evaluate")
def batch_evaluate_submissions(
    req: BatchGradeRequest,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """批量自动评分接口：支持一次选中多份作业进行自动评分，并汇总成功评分与需澄清数量。"""
    if not req.submission_ids:
        raise HTTPException(status_code=400, detail="请至少选择一份待评分作业")

    graded_count = 0
    clarification_count = 0
    results: List[Dict[str, Any]] = []

    for sid in req.submission_ids:
        sub = repo.get_submission_by_id(sid)
        if not sub:
            continue
        updated = _run_single_evaluation(
            sub=sub,
            grading_mode=req.grading_mode,
            rubric_id=req.rubric_id or sub.get("rubric_id"),
            force_grade=False,
            repo=repo,
        )
        if updated.get("status") == "needs_clarification":
            clarification_count += 1
        else:
            graded_count += 1
        results.append(updated)

    return {
        "message": f"批量处理完成：成功评分 {graded_count} 份，触发模糊澄清待确认 {clarification_count} 份",
        "graded_count": graded_count,
        "clarification_count": clarification_count,
        "submissions": results,
    }


@router.put("/{submission_id}/review", response_model=SubmissionOut)
def teacher_review_submission(
    submission_id: int,
    req: TeacherReviewRequest,
    teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """教师端人工复核与手动修正：支持修改最终总分、分维度得分、评分理由及改进建议。"""
    sub = repo.get_submission_by_id(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="作业不存在")

    return repo.update_submission_grading(
        submission_id,
        {
            "status": "reviewed",
            "final_score": round(float(req.final_score), 1),
            "cognitive_level": req.cognitive_level or sub.get("cognitive_level"),
            "overall_comment": req.overall_comment.strip(),
            "dimension_scores": [d.model_dump() for d in req.dimension_scores],
            "improvement_suggestions": req.improvement_suggestions,
            "teacher_adjustment_note": req.teacher_adjustment_note.strip(),
            "reviewed_by": teacher["full_name"],
            "reviewed_at": datetime.utcnow().isoformat(),
        },
    )  # type: ignore


@router.get("/export/excel")
def export_grades_to_excel(
    status_filter: Optional[str] = Query(default=None),
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> StreamingResponse:
    """
    将作业评分结果导出为专业排版格式的 Excel (.xlsx) 报表：
    包含工作表 1「总评成绩与评语汇总」与工作表 2「各维度分项得分与原文引用明细」。
    """
    submissions = repo.list_submissions(status_filter=status_filter)

    wb = openpyxl.Workbook()
    # ==================== Sheet 1: 成绩总表 ====================
    ws_summary = wb.active
    ws_summary.title = "作业成绩与总评汇总"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Microsoft YaHei", size=11, bold=True, color="FFFFFF")
    body_font = Font(name="Microsoft YaHei", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )

    summary_headers = [
        "作业ID",
        "学号",
        "学生姓名",
        "班级",
        "作业题目",
        "题型",
        "评分模式",
        "匹配量规名称",
        "状态",
        "AI初评总分",
        "最终核定总分",
        "SOLO/布鲁姆认知水平",
        "综合评语",
        "具体改进建议",
        "复核教师",
    ]
    ws_summary.append(summary_headers)
    for col_idx in range(1, len(summary_headers) + 1):
        cell = ws_summary.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_summary.row_dimensions[1].height = 28

    status_map = {
        "submitted": "待评分",
        "needs_clarification": "待模糊澄清",
        "graded": "AI已评分",
        "reviewed": "教师已复核",
    }

    for row_idx, sub in enumerate(submissions, start=2):
        suggestions_str = "\n".join(
            f"{i + 1}. {s}"
            for i, s in enumerate(sub.get("improvement_suggestions") or [])
        )
        row_values = [
            sub["id"],
            sub.get("student_no", ""),
            sub.get("student_name", ""),
            sub.get("class_name", ""),
            sub.get("assignment_title", ""),
            sub.get("question_type", ""),
            "权威默认量规 (模式A)"
            if sub.get("grading_mode") == "authoritative"
            else "自定义量规 (模式B)",
            sub.get("matched_rubric_name", ""),
            status_map.get(sub.get("status", ""), sub.get("status", "")),
            sub.get("total_score") if sub.get("total_score") is not None else "-",
            sub.get("final_score") if sub.get("final_score") is not None else "-",
            sub.get("cognitive_level") or "-",
            sub.get("overall_comment") or "-",
            suggestions_str or "-",
            sub.get("reviewed_by") or "-",
        ]
        ws_summary.append(row_values)
        ws_summary.row_dimensions[row_idx].height = 42
        for col_idx in range(1, len(summary_headers) + 1):
            c = ws_summary.cell(row=row_idx, column=col_idx)
            c.font = body_font
            c.border = thin_border
            c.alignment = Alignment(
                horizontal="center" if col_idx in [1, 2, 3, 6, 7, 9, 10, 11, 15] else "left",
                vertical="center",
                wrap_text=True,
            )

    col_widths_1 = [10, 14, 14, 20, 32, 18, 20, 30, 14, 14, 14, 28, 45, 45, 16]
    for i, w in enumerate(col_widths_1, start=1):
        ws_summary.column_dimensions[get_column_letter(i)].width = w

    # ==================== Sheet 2: 分维度得分与原文引用明细 ====================
    ws_detail = wb.create_sheet(title="分维度得分与原文依据明细")
    detail_headers = [
        "作业ID",
        "学号",
        "学生姓名",
        "作业题目",
        "评分维度名称",
        "维度权重(%)",
        "维度满分",
        "实际得分",
        "达成等级",
        "引用的作业原文片段 (Evidence Quote)",
        "具体评分理由 (Rationale)",
        "分项改进建议",
    ]
    ws_detail.append(detail_headers)
    for col_idx in range(1, len(detail_headers) + 1):
        cell = ws_detail.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_detail.row_dimensions[1].height = 28

    detail_row_idx = 2
    for sub in submissions:
        for dim in sub.get("dimension_scores") or []:
            ws_detail.append(
                [
                    sub["id"],
                    sub.get("student_no", ""),
                    sub.get("student_name", ""),
                    sub.get("assignment_title", ""),
                    dim.get("dimension_name", ""),
                    dim.get("weight", 0),
                    dim.get("max_score", 0),
                    dim.get("score", 0),
                    dim.get("level_reached", ""),
                    dim.get("evidence_quote", ""),
                    dim.get("rationale", ""),
                    dim.get("dimension_suggestion", ""),
                ]
            )
            ws_detail.row_dimensions[detail_row_idx].height = 38
            for col_idx in range(1, len(detail_headers) + 1):
                c = ws_detail.cell(row=detail_row_idx, column=col_idx)
                c.font = body_font
                c.border = thin_border
                c.alignment = Alignment(
                    horizontal="center" if col_idx in [1, 2, 3, 6, 7, 8] else "left",
                    vertical="center",
                    wrap_text=True,
                )
            detail_row_idx += 1

    col_widths_2 = [10, 14, 14, 28, 26, 14, 12, 12, 24, 42, 45, 38]
    for i, w in enumerate(col_widths_2, start=1):
        ws_detail.column_dimensions[get_column_letter(i)].width = w

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"EduGrade_作业评分报表_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    encoded_filename = quote(filename)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )
