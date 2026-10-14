"""
双模式评分量规路由 (`app/routers/rubrics.py`)：
- 模式 A「权威默认量规」：查询系统内置 SOLO 分类法五水平量规、布鲁姆教育目标六层级量规等
- 模式 B「自定义量规学习」：
  1. POST /api/rubrics/parse：上传 PDF / Word / 纯文本量规文档（或直接粘贴量规文本），调用 LLM 解析出评分维度、权重、各等级描述，返回给前端供用户核对与调整（先解析展示、后确认入库）
  2. POST /api/rubrics/confirm：用户确认解析结果无误后，正式保存为可用自定义量规
  3. PUT / DELETE：支持后续对自定义量规进行微调或删除
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.core.database import DatabaseRepository, get_db_repository
from app.core.security import get_current_user, require_teacher
from app.schemas.schemas import RubricConfirmRequest, RubricOut
from app.services.file_parser import parse_uploaded_file
from app.services.llm_provider import get_llm_provider

router = APIRouter(prefix="/api/rubrics", tags=["双模式量规管理"])


@router.get("", response_model=List[RubricOut])
def list_rubrics(
    mode: Optional[str] = Query(
        default=None, description="过滤模式: authoritative (权威默认) | custom (自定义学习)"
    ),
    _user: Dict[str, Any] = Depends(get_current_user),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> List[Dict[str, Any]]:
    """获取量规列表（支持按模式筛选）。"""
    return repo.list_rubrics(mode=mode)


@router.get("/{rubric_id}", response_model=RubricOut)
def get_rubric(
    rubric_id: int,
    _user: Dict[str, Any] = Depends(get_current_user),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """获取单个量规详情（含全部维度、权重与等级描述）。"""
    rubric = repo.get_rubric_by_id(rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="量规不存在")
    return rubric


@router.post("/parse")
async def parse_custom_rubric_document(
    file: Optional[UploadFile] = File(default=None, description="上传的量规文档 (PDF / Word / TXT)"),
    raw_text: Optional[str] = Form(default=None, description="或者直接粘贴的量规纯文本"),
    _teacher: Dict[str, Any] = Depends(require_teacher),
) -> Dict[str, Any]:
    """
    模式 B 第一步：上传量规文档或文本，由 LLM 解析出评分维度、权重与等级描述，
    返回解析预览结果供教师在前端弹窗/表单中确认与修订（尚未直接用于打分）。
    """
    extracted_text = (raw_text or "").strip()
    filename = "手动粘贴量规.txt"
    file_bytes: Optional[bytes] = None
    mime_type: Optional[str] = None

    if file and file.filename:
        filename = file.filename
        file_bytes = await file.read()
        parsed_file = parse_uploaded_file(
            file_bytes=file_bytes,
            filename=filename,
            prompt_hint="这是一份教学评分量规（Rubric）文档，请完整提取其中的评价维度、权重分值与等级描述。",
        )
        extracted_text = (
            f"{extracted_text}\n{parsed_file.get('extracted_text', '')}".strip()
        )
        mime_type = parsed_file.get("mime_type")

    if not extracted_text and not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="请上传量规文件（PDF / Word / TXT）或输入量规文本内容",
        )

    llm = get_llm_provider()
    parsed_rubric = llm.parse_custom_rubric(
        raw_text=extracted_text,
        filename=filename,
        file_bytes=file_bytes if mime_type in ["application/pdf", "image/png", "image/jpeg"] else None,
        mime_type=mime_type,
    )

    return {
        "message": "量规解析完成，请核对以下评分维度、权重与等级描述，确认无误后点击保存启用",
        "source_filename": filename,
        "raw_source_text": extracted_text,
        "parsed_rubric": parsed_rubric,
    }


@router.post("/confirm", response_model=RubricOut)
def confirm_and_save_custom_rubric(
    req: RubricConfirmRequest,
    teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """
    模式 B 第二步：用户确认（并可微调）LLM 解析出的维度、权重和等级描述后，
    正式保存为已确认的自定义量规 (`mode='custom'`, `is_confirmed=True`)。
    """
    if not req.dimensions:
        raise HTTPException(status_code=400, detail="量规至少需要包含一个评分维度")

    return repo.create_rubric(
        {
            "name": req.name.strip(),
            "mode": "custom",
            "framework_type": req.framework_type or "CUSTOM",
            "question_type": req.question_type or "综合主观题",
            "description": req.description,
            "total_points": req.total_points,
            "dimensions": [d.model_dump() for d in req.dimensions],
            "source_filename": req.source_filename,
            "raw_source_text": req.raw_source_text,
            "is_confirmed": True,
            "created_by": teacher["id"],
        }
    )


@router.put("/{rubric_id}", response_model=RubricOut)
def update_rubric(
    rubric_id: int,
    req: RubricConfirmRequest,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """更新量规的维度、权重或等级描述。"""
    updated = repo.update_rubric(
        rubric_id,
        {
            "name": req.name.strip(),
            "question_type": req.question_type,
            "description": req.description,
            "total_points": req.total_points,
            "dimensions": [d.model_dump() for d in req.dimensions],
            "is_confirmed": True,
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="未找到该量规")
    return updated


@router.delete("/{rubric_id}")
def delete_rubric(
    rubric_id: int,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """删除自定义量规（内置权威量规不可删除）。"""
    existing = repo.get_rubric_by_id(rubric_id)
    if not existing:
        raise HTTPException(status_code=404, detail="量规不存在")
    if existing.get("mode") == "authoritative":
        raise HTTPException(status_code=400, detail="系统内置权威量规不支持删除")
    repo.delete_rubric(rubric_id)
    return {"message": "自定义量规已删除", "id": rubric_id}
