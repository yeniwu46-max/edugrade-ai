"""
作业上传与列表管理路由 (`app/routers/assignments.py`)：
- 支持单份上传（纯文本直接提交，或上传 TXT / 图片 PNG,JPG,WEBP / PDF / Word .docx）
- 支持教师端批量上传多份作业文件（自动按文件名中的学号/姓名匹配学生，或归入默认学生名下）
- 支持按状态、关键词、学生 ID 查询作业列表与详情
"""
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.core.config import settings
from app.core.database import DatabaseRepository, get_db_repository
from app.core.security import get_current_user, require_teacher
from app.schemas.schemas import SubmissionOut
from app.services.file_parser import parse_uploaded_file
from app.services.seed_data import match_authoritative_rubric

router = APIRouter(prefix="/api/submissions", tags=["作业上传与管理"])


@router.get("", response_model=List[SubmissionOut])
def list_submissions(
    status_filter: Optional[str] = Query(
        default=None,
        description="按状态筛选: submitted | needs_clarification | graded | reviewed",
    ),
    keyword: Optional[str] = Query(
        default=None, description="按学生姓名、学号或作业标题搜索"
    ),
    student_id: Optional[int] = Query(default=None, description="按学生 ID 筛选"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> List[Dict[str, Any]]:
    """
    获取作业列表：
    - 若当前用户为学生 (`role == 'student'`)，仅返回该学生自己的作业记录；
    - 若当前用户为教师 (`role == 'teacher'`)，返回全班作业记录并支持多条件过滤。
    """
    effective_student_id = (
        current_user["id"] if current_user.get("role") == "student" else student_id
    )
    return repo.list_submissions(
        student_id=effective_student_id,
        status_filter=status_filter,
        keyword=keyword,
    )


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission_detail(
    submission_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """获取单份作业的完整详情（含原文、模糊澄清问题、各维度分项得分与原文引用、改进建议）。"""
    sub = repo.get_submission_by_id(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="未找到该作业记录")
    if (
        current_user.get("role") == "student"
        and sub["student_id"] != current_user["id"]
    ):
        raise HTTPException(status_code=403, detail="无权查看其他同学的作业详情")
    return sub


@router.post("/upload", response_model=SubmissionOut)
async def upload_submission(
    assignment_title: str = Form(..., description="作业题目名称"),
    question_prompt: str = Form(..., description="题目具体要求与背景材料"),
    question_type: str = Form(default="开放论述题", description="题型：开放论述题 / 案例分析与科学探究题 / 编程与算法题"),
    student_id: Optional[int] = Form(default=None, description="提交学生 ID（学生端登录可自动获取）"),
    grading_mode: str = Form(default="authoritative", description="authoritative (模式A) | custom (模式B)"),
    rubric_id: Optional[int] = Form(default=None, description="指定量规 ID（模式B必传，模式A可自动匹配）"),
    text_content: Optional[str] = Form(default=None, description="直接输入的文本作业内容"),
    file: Optional[UploadFile] = File(default=None, description="上传的作业文件（支持 TXT / 图片 / PDF / Word）"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """上传单份作业（支持教师代传或学生自主提交，支持文本与多模态文件）。"""
    # 确定学生身份
    if current_user.get("role") == "student":
        student = current_user
    else:
        if student_id:
            student = repo.get_user_by_id(student_id)
        else:
            students = repo.list_students()
            student = students[0] if students else current_user
        if not student:
            raise HTTPException(status_code=400, detail="指定的学生不存在")

    submission_type = "text"
    saved_file_name = None
    saved_file_path = None
    mime_type = "text/plain"
    extracted_text = (text_content or "").strip()

    if file and file.filename:
        file_bytes = await file.read()
        safe_name = f"{int(time.time())}_{Path(file.filename).name}"
        dest_path = settings.UPLOAD_DIR / safe_name
        dest_path.write_bytes(file_bytes)

        parsed = parse_uploaded_file(
            file_bytes=file_bytes,
            filename=file.filename,
            prompt_hint=f"作业题目：{assignment_title}。题目要求：{question_prompt}",
        )
        submission_type = parsed["submission_type"]
        saved_file_name = file.filename
        saved_file_path = str(dest_path)
        mime_type = parsed["mime_type"]
        file_text = parsed.get("extracted_text", "")
        extracted_text = (
            f"{extracted_text}\n\n{file_text}".strip() if extracted_text else file_text
        )

    if not extracted_text and not saved_file_path:
        raise HTTPException(
            status_code=400,
            detail="请填写作业文本内容，或上传作业文件（支持 TXT / 图片 / PDF / Word）",
        )

    # 匹配量规
    matched_rubric = None
    if rubric_id:
        matched_rubric = repo.get_rubric_by_id(rubric_id)
    if not matched_rubric:
        matched_rubric = match_authoritative_rubric(
            question_type=question_type,
            question_prompt=question_prompt,
            repo=repo,
        )

    return repo.create_submission(
        {
            "assignment_title": assignment_title.strip(),
            "question_prompt": question_prompt.strip(),
            "question_type": question_type.strip(),
            "student_id": student["id"],
            "student_no": student.get("student_no") or student["username"],
            "student_name": student["full_name"],
            "class_name": student.get("class_name") or "高二(1)班",
            "submission_type": submission_type,
            "file_name": saved_file_name,
            "file_path": saved_file_path,
            "mime_type": mime_type,
            "extracted_text": extracted_text,
            "grading_mode": grading_mode,
            "rubric_id": matched_rubric["id"] if matched_rubric else None,
            "matched_rubric_name": matched_rubric["name"] if matched_rubric else None,
            "status": "submitted",
        }
    )


@router.post("/batch-upload", response_model=List[SubmissionOut])
async def batch_upload_submissions(
    assignment_title: str = Form(..., description="批量作业统一题目名称"),
    question_prompt: str = Form(..., description="题目具体要求"),
    question_type: str = Form(default="开放论述题", description="题型"),
    grading_mode: str = Form(default="authoritative"),
    rubric_id: Optional[int] = Form(default=None),
    files: List[UploadFile] = File(..., description="多份学生作业文件（推荐命名格式：学号_姓名_作业名.docx/.pdf/.png/.txt）"),
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> List[Dict[str, Any]]:
    """
    教师端批量上传作业文件：
    自动根据文件名识别学生（如 `2026001_林知夏_作业.docx` 或包含学生姓名/学号），
    若未匹配到特定学生则轮询分配给班级学生名册。
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少选择一个作业文件进行批量上传")

    students = repo.list_students()
    if not students:
        raise HTTPException(status_code=400, detail="系统中暂无学生名册，请先添加学生")

    matched_rubric = (
        repo.get_rubric_by_id(rubric_id)
        if rubric_id
        else match_authoritative_rubric(question_type, question_prompt, repo)
    )

    created_list: List[Dict[str, Any]] = []
    for idx, upload_file in enumerate(files):
        fname = upload_file.filename or f"batch_file_{idx + 1}.txt"
        file_bytes = await upload_file.read()
        safe_name = f"{int(time.time())}_{idx}_{Path(fname).name}"
        dest_path = settings.UPLOAD_DIR / safe_name
        dest_path.write_bytes(file_bytes)

        # 根据文件名自动匹配学生（匹配学号或姓名）
        target_student = None
        for stu in students:
            stu_no = stu.get("student_no") or ""
            stu_name = stu.get("full_name") or ""
            if (stu_no and stu_no in fname) or (stu_name and stu_name in fname):
                target_student = stu
                break
        if not target_student:
            target_student = students[idx % len(students)]

        parsed = parse_uploaded_file(
            file_bytes=file_bytes,
            filename=fname,
            prompt_hint=f"作业题目：{assignment_title}。题目要求：{question_prompt}",
        )

        sub = repo.create_submission(
            {
                "assignment_title": assignment_title.strip(),
                "question_prompt": question_prompt.strip(),
                "question_type": question_type.strip(),
                "student_id": target_student["id"],
                "student_no": target_student.get("student_no") or target_student["username"],
                "student_name": target_student["full_name"],
                "class_name": target_student.get("class_name") or "高二(1)班",
                "submission_type": parsed["submission_type"],
                "file_name": fname,
                "file_path": str(dest_path),
                "mime_type": parsed["mime_type"],
                "extracted_text": parsed.get("extracted_text", ""),
                "grading_mode": grading_mode,
                "rubric_id": matched_rubric["id"] if matched_rubric else None,
                "matched_rubric_name": matched_rubric["name"] if matched_rubric else None,
                "status": "submitted",
            }
        )
        created_list.append(sub)

    return created_list


@router.delete("/{submission_id}")
def delete_submission(
    submission_id: int,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """删除单份作业记录。"""
    ok = repo.delete_submission(submission_id)
    if not ok:
        raise HTTPException(status_code=404, detail="作业记录不存在")
    return {"message": "作业已删除", "id": submission_id}
