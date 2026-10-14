"""
认证与学生信息管理路由 (`app/routers/auth.py`)：
- POST /api/auth/login: 账号密码登录，签发 JWT Access Token（区分 teacher / student 角色）
- GET  /api/auth/me: 获取当前登录用户信息
- GET  /api/students: 获取学生列表（支持按姓名/学号/班级搜索）
- POST /api/students: 新增学生信息并自动创建学生端登录账号
- PUT  /api/students/{student_id}: 修改学生信息
- DELETE /api/students/{student_id}: 删除学生账号
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import DatabaseRepository, get_db_repository
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_teacher,
    verify_password,
)
from app.schemas.schemas import (
    LoginRequest,
    StudentCreate,
    StudentUpdate,
    TokenResponse,
    UserOut,
)

router = APIRouter(tags=["认证与学生管理"])


@router.post("/api/auth/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """统一登录接口：支持教师账号或学生学号登录，返回 JWT Token 与角色信息。"""
    user = repo.get_user_by_username(req.username.strip())
    if not user and req.username.strip():
        # 允许学生直接用学号登录
        user = repo.get_user_by_student_no(req.username.strip())

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误（演示默认密码均为 123456）",
        )

    token = create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"],
            "user_id": user["id"],
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/api/auth/me", response_model=UserOut)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """获取当前登录用户的个人信息。"""
    return current_user


@router.get("/api/students", response_model=List[UserOut])
def list_students(
    keyword: Optional[str] = Query(default=None, description="按姓名、学号或班级模糊搜索"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> List[Dict[str, Any]]:
    """查询学生列表（教师与学生均可查看基础名册，方便上传作业选择学生）。"""
    return repo.list_students(keyword=keyword)


@router.post("/api/students", response_model=UserOut)
def create_student(
    req: StudentCreate,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """新增学生档案（自动以学号作为登录账号，初始密码默认 123456）。"""
    student_no = req.student_no.strip()
    if repo.get_user_by_username(student_no) or repo.get_user_by_student_no(student_no):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"学号 {student_no} 已存在，请勿重复添加",
        )
    return repo.create_user(
        {
            "username": student_no,
            "student_no": student_no,
            "password_hash": hash_password(req.password or "123456"),
            "full_name": req.full_name.strip(),
            "role": "student",
            "class_name": req.class_name.strip(),
            "email": req.email,
        }
    )


@router.put("/api/students/{student_id}", response_model=UserOut)
def update_student(
    student_id: int,
    req: StudentUpdate,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """修改学生基本信息。"""
    updated = repo.update_student(student_id, req.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="未找到该学生记录")
    return updated


@router.delete("/api/students/{student_id}")
def delete_student(
    student_id: int,
    _teacher: Dict[str, Any] = Depends(require_teacher),
    repo: DatabaseRepository = Depends(get_db_repository),
) -> Dict[str, Any]:
    """删除学生记录。"""
    ok = repo.delete_student(student_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该学生或无权删除")
    return {"message": "学生信息已删除", "id": student_id}
