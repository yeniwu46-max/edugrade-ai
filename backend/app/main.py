"""
FastAPI 应用主入口 (`app/main.py`)：
- 启动时自动初始化数据库表结构、默认教师/学生账号、SOLO 与布鲁姆权威量规库及示例作业
- 配置跨域中间件 (CORS) 支持 Vue 3 + Vite 前端访问
- 挂载认证、学生管理、双模式量规、作业上传与智能评分全部路由
"""
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import db_repo
from app.routers import assignments, auth, grading, rubrics
from app.services.seed_data import seed_initial_data

# 模块加载与启动时确保表结构和初始演示数据已就绪
seed_initial_data(db_repo)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "支持多模态作业上传（TXT/图片/PDF/Word）、SOLO 与布鲁姆权威量规自动匹配、"
        "自定义量规 LLM 解析确认、模糊澄清机制、原文引用打分、人工复核与 Excel 导出的完整教学系统。"
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(rubrics.router)
app.include_router(assignments.router)
app.include_router(grading.router)


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """系统健康检查与当前 LLM 适配器状态查询接口。"""
    has_gemini_key = bool(
        settings.GEMINI_API_KEY
        and settings.GEMINI_API_KEY != "your-gemini-api-key-here"
        and len(settings.GEMINI_API_KEY) > 10
    )
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "database_type": "PostgreSQL"
        if settings.DATABASE_URL.startswith("postgresql")
        else "SQLite",
        "llm_provider": settings.LLM_PROVIDER,
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_api_key_configured": has_gemini_key,
    }
