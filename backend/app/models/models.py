"""
数据库模型与 DDL 定义模块：
1. 提供标准 SQLAlchemy 2.0 ORM 模型定义（当环境中安装了 SQLAlchemy 时启用，支持 SQLite 与 PostgreSQL）。
2. 同时导出跨数据库兼容的标准 SQL 建表定义，确保在轻量环境或迁移脚本中均可直接初始化表结构。
"""
from datetime import datetime
from typing import Optional

try:
    from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
    from sqlalchemy.orm import declarative_base, relationship

    Base = declarative_base()

    class UserORM(Base):
        """系统用户表（区分 teacher 与 student 角色）"""
        __tablename__ = "users"

        id = Column(Integer, primary_key=True, index=True, autoincrement=True)
        username = Column(String(64), unique=True, index=True, nullable=False)
        password_hash = Column(String(256), nullable=False)
        full_name = Column(String(128), nullable=False)
        role = Column(String(32), nullable=False, default="student")  # teacher | student
        student_no = Column(String(64), unique=True, nullable=True, index=True)
        class_name = Column(String(128), nullable=True)
        email = Column(String(128), nullable=True)
        is_active = Column(Boolean, default=True)
        created_at = Column(String(64), default=lambda: datetime.utcnow().isoformat())

    class RubricORM(Base):
        """
        评分量规表：
        - mode: 'authoritative'（内置权威量规：SOLO 分类法 / 布鲁姆分类法 / 议论文写作 / 编程实验）
                或 'custom'（用户上传文档经 LLM 解析并确认的自定义量规）
        - dimensions_json: JSON 数组，存储维度名称、权重、各等级描述与分值区间
        """
        __tablename__ = "rubrics"

        id = Column(Integer, primary_key=True, index=True, autoincrement=True)
        name = Column(String(256), nullable=False)
        mode = Column(String(32), nullable=False, default="authoritative")  # authoritative | custom
        framework_type = Column(String(64), nullable=False, default="SOLO")  # SOLO | BLOOM | CUSTOM
        question_type = Column(String(128), nullable=False, default="开放论述题")
        description = Column(Text, nullable=True)
        total_points = Column(Float, nullable=False, default=100.0)
        dimensions_json = Column(Text, nullable=False)
        source_filename = Column(String(256), nullable=True)
        raw_source_text = Column(Text, nullable=True)
        is_confirmed = Column(Boolean, default=True)
        created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
        created_at = Column(String(64), default=lambda: datetime.utcnow().isoformat())

    class SubmissionORM(Base):
        """
        学生作业提交与评分主表：
        - 支持文本、图片(.png/.jpg/.webp)、PDF(.pdf)、Word(.docx)
        - status:
          - 'submitted': 已上传待评分
          - 'needs_clarification': 存在模糊点，等待教师/用户澄清后再评分
          - 'graded': AI 已完成评分
          - 'reviewed': 教师已完成人工复核与修正
        """
        __tablename__ = "submissions"

        id = Column(Integer, primary_key=True, index=True, autoincrement=True)
        assignment_title = Column(String(256), nullable=False)
        question_prompt = Column(Text, nullable=False)
        question_type = Column(String(128), nullable=False, default="开放论述题")
        student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        student_no = Column(String(64), nullable=False)
        student_name = Column(String(128), nullable=False)
        class_name = Column(String(128), nullable=True)

        # 作业内容与文件信息
        submission_type = Column(String(32), nullable=False, default="text")  # text | image | pdf | docx
        file_name = Column(String(256), nullable=True)
        file_path = Column(String(512), nullable=True)
        mime_type = Column(String(128), nullable=True)
        extracted_text = Column(Text, nullable=True)

        # 评分配置与状态
        grading_mode = Column(String(32), nullable=False, default="authoritative")  # authoritative | custom
        rubric_id = Column(Integer, ForeignKey("rubrics.id"), nullable=True)
        matched_rubric_name = Column(String(256), nullable=True)
        status = Column(String(32), nullable=False, default="submitted")

        # 模糊澄清记录 (JSON: 疑问点列表 + 用户补充回答)
        clarification_questions_json = Column(Text, nullable=True)
        clarification_answers_json = Column(Text, nullable=True)

        # 评分输出 (总分、SOLO/Bloom 等级、各维度得分+原文引用依据、具体改进建议)
        total_score = Column(Float, nullable=True)
        final_score = Column(Float, nullable=True)
        cognitive_level = Column(String(128), nullable=True)
        overall_comment = Column(Text, nullable=True)
        dimension_scores_json = Column(Text, nullable=True)
        improvement_suggestions_json = Column(Text, nullable=True)

        # 教师人工复核信息
        teacher_Adjustment_note = Column(Text, nullable=True)
        reviewed_by = Column(String(128), nullable=True)
        reviewed_at = Column(String(64), nullable=True)

        created_at = Column(String(64), default=lambda: datetime.utcnow().isoformat())
        updated_at = Column(String(64), default=lambda: datetime.utcnow().isoformat())

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    Base = None
    SQLALCHEMY_AVAILABLE = False


# 跨 SQLite / PostgreSQL 兼容的初始化表结构 SQL
SCHEMA_SQL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(64) UNIQUE NOT NULL,
        password_hash VARCHAR(256) NOT NULL,
        full_name VARCHAR(128) NOT NULL,
        role VARCHAR(32) NOT NULL DEFAULT 'student',
        student_no VARCHAR(64) UNIQUE,
        class_name VARCHAR(128),
        email VARCHAR(128),
        is_active INTEGER DEFAULT 1,
        created_at VARCHAR(64) NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS rubrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(256) NOT NULL,
        mode VARCHAR(32) NOT NULL DEFAULT 'authoritative',
        framework_type VARCHAR(64) NOT NULL DEFAULT 'SOLO',
        question_type VARCHAR(128) NOT NULL DEFAULT '开放论述题',
        description TEXT,
        total_points REAL NOT NULL DEFAULT 100.0,
        dimensions_json TEXT NOT NULL,
        source_filename VARCHAR(256),
        raw_source_text TEXT,
        is_confirmed INTEGER DEFAULT 1,
        created_by INTEGER,
        created_at VARCHAR(64) NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_title VARCHAR(256) NOT NULL,
        question_prompt TEXT NOT NULL,
        question_type VARCHAR(128) NOT NULL DEFAULT '开放论述题',
        student_id INTEGER NOT NULL,
        student_no VARCHAR(64) NOT NULL,
        student_name VARCHAR(128) NOT NULL,
        class_name VARCHAR(128),
        submission_type VARCHAR(32) NOT NULL DEFAULT 'text',
        file_name VARCHAR(256),
        file_path VARCHAR(512),
        mime_type VARCHAR(128),
        extracted_text TEXT,
        grading_mode VARCHAR(32) NOT NULL DEFAULT 'authoritative',
        rubric_id INTEGER,
        matched_rubric_name VARCHAR(256),
        status VARCHAR(32) NOT NULL DEFAULT 'submitted',
        clarification_questions_json TEXT,
        clarification_answers_json TEXT,
        total_score REAL,
        final_score REAL,
        cognitive_level VARCHAR(128),
        overall_comment TEXT,
        dimension_scores_json TEXT,
        improvement_suggestions_json TEXT,
        teacher_adjustment_note TEXT,
        reviewed_by VARCHAR(128),
        reviewed_at VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    );
    """,
]
