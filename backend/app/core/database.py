"""
数据库访问与连接池管理模块：
- 支持通过 DATABASE_URL 环境变量在 SQLite（默认开发环境）与 PostgreSQL（生产环境）之间无缝切换。
- 当环境安装了 SQLAlchemy 时，自动配置 SQLAlchemy Engine 与 SessionLocal；
- 同时提供统一的 DatabaseRepository 仓储层，兼容 SQLite3 原生驱动与 SQLAlchemy，保证本地零配置即可运行。
"""
import json
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.models import SCHEMA_SQL_STATEMENTS, SQLALCHEMY_AVAILABLE, Base

# 若安装了 SQLAlchemy 且使用 PostgreSQL，则初始化 SQLAlchemy Engine
sqlalchemy_engine = None
SessionLocal = None

if SQLALCHEMY_AVAILABLE:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    connect_args = (
        {"check_same_thread": False}
        if settings.DATABASE_URL.startswith("sqlite")
        else {}
    )
    sqlalchemy_engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=sqlalchemy_engine
    )


def _resolve_sqlite_path(db_url: str) -> str:
    """从 sqlite:/// URL 中提取本地文件路径；若当前挂载目录不支持文件锁则自动回退至系统临时目录。"""
    target_path = (
        db_url.replace("sqlite:///", "", 1)
        if db_url.startswith("sqlite:///")
        else settings.SQLITE_FILE_PATH
    )
    try:
        conn = sqlite3.connect(target_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=MEMORY;")
        conn.execute("CREATE TABLE IF NOT EXISTS _lock_probe (id INTEGER);")
        conn.close()
        return target_path
    except sqlite3.OperationalError:
        fallback_path = str(Path(tempfile.gettempdir()) / "edugrade.db")
        return fallback_path


class DatabaseRepository:
    """
    统一数据访问仓储层：
    封装用户、学生、评分量规、作业提交与评分结果的 CRUD 操作。
    通过参数化 SQL 查询同时支持 SQLite 与 PostgreSQL。
    """

    def __init__(self, db_url: Optional[str] = None) -> None:
        self.db_url = db_url or settings.DATABASE_URL
        self.is_postgres = self.db_url.startswith("postgresql")
        self._resolved_sqlite_path: Optional[str] = None

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        if not self._resolved_sqlite_path:
            self._resolved_sqlite_path = _resolve_sqlite_path(self.db_url)
        conn = sqlite3.connect(self._resolved_sqlite_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self) -> None:
        """初始化数据库表结构（支持 SQLite 与 PostgreSQL）。"""
        if self.is_postgres and SQLALCHEMY_AVAILABLE and Base is not None:
            Base.metadata.create_all(bind=sqlalchemy_engine)
            return

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            for stmt in SCHEMA_SQL_STATEMENTS:
                cursor.execute(stmt)
            conn.commit()
        finally:
            conn.close()

    def _execute_query(
        self,
        sql: str,
        params: tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = False,
        commit: bool = False,
    ) -> Any:
        """统一执行参数化 SQL，自动适配 SQLite (?) 与 PostgreSQL (:p0)。"""
        if self.is_postgres and SQLALCHEMY_AVAILABLE and sqlalchemy_engine is not None:
            from sqlalchemy import text

            parts = sql.split("?")
            bound_sql = parts[0]
            bind_params = {}
            for idx, part in enumerate(parts[1:]):
                key = f"p{idx}"
                bound_sql += f":{key}{part}"
                bind_params[key] = params[idx]

            with sqlalchemy_engine.begin() as conn:
                if commit and not fetch_one and not fetch_all and "INSERT INTO" in sql.upper():
                    bound_sql_ret = bound_sql.rstrip().rstrip(";") + " RETURNING id"
                    res = conn.execute(text(bound_sql_ret), bind_params)
                    row = res.fetchone()
                    return row[0] if row else None
                res = conn.execute(text(bound_sql), bind_params)
                if fetch_one:
                    row = res.mappings().fetchone()
                    return dict(row) if row else None
                if fetch_all:
                    return [dict(r) for r in res.mappings().fetchall()]
                return None

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            if commit:
                conn.commit()
                if sql.strip().upper().startswith("INSERT"):
                    return cursor.lastrowid
            if fetch_one:
                row = cursor.fetchone()
                return dict(row) if row else None
            if fetch_all:
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            return None
        finally:
            conn.close()

    # ==================== 用户与学生管理 ====================
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        row = self._execute_query(
            "SELECT * FROM users WHERE username = ?", (username,), fetch_one=True
        )
        if row:
            row["is_active"] = bool(row.get("is_active", 1))
        return row

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self._execute_query(
            "SELECT * FROM users WHERE id = ?", (user_id,), fetch_one=True
        )
        if row:
            row["is_active"] = bool(row.get("is_active", 1))
        return row

    def get_user_by_student_no(self, student_no: str) -> Optional[Dict[str, Any]]:
        row = self._execute_query(
            "SELECT * FROM users WHERE student_no = ?", (student_no,), fetch_one=True
        )
        if row:
            row["is_active"] = bool(row.get("is_active", 1))
        return row

    def list_students(self, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        if keyword:
            kw = f"%{keyword}%"
            rows = self._execute_query(
                """
                SELECT * FROM users
                WHERE role = 'student'
                  AND (full_name LIKE ? OR student_no LIKE ? OR class_name LIKE ?)
                ORDER BY student_no ASC
                """,
                (kw, kw, kw),
                fetch_all=True,
            )
        else:
            rows = self._execute_query(
                "SELECT * FROM users WHERE role = 'student' ORDER BY student_no ASC",
                fetch_all=True,
            )
        for r in rows:
            r["is_active"] = bool(r.get("is_active", 1))
        return rows

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        user_id = self._execute_query(
            """
            INSERT INTO users (username, password_hash, full_name, role, student_no, class_name, email, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["username"],
                data["password_hash"],
                data["full_name"],
                data.get("role", "student"),
                data.get("student_no"),
                data.get("class_name"),
                data.get("email"),
                1 if data.get("is_active", True) else 0,
                now,
            ),
            commit=True,
        )
        return self.get_user_by_id(user_id)  # type: ignore

    def update_student(self, user_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_user_by_id(user_id)
        if not existing:
            return None
        full_name = data.get("full_name", existing["full_name"])
        student_no = data.get("student_no", existing["student_no"])
        class_name = data.get("class_name", existing["class_name"])
        email = data.get("email", existing["email"])
        self._execute_query(
            """
            UPDATE users
            SET full_name = ?, student_no = ?, class_name = ?, email = ?
            WHERE id = ?
            """,
            (full_name, student_no, class_name, email, user_id),
            commit=True,
        )
        return self.get_user_by_id(user_id)

    def delete_student(self, user_id: int) -> bool:
        existing = self.get_user_by_id(user_id)
        if not existing or existing.get("role") != "student":
            return False
        self._execute_query(
            "DELETE FROM users WHERE id = ?", (user_id,), commit=True
        )
        return True

    # ==================== 量规 (Rubric) 管理 ====================
    def _deserialize_rubric(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        row["is_confirmed"] = bool(row.get("is_confirmed", 1))
        try:
            row["dimensions"] = json.loads(row.get("dimensions_json") or "[]")
        except Exception:
            row["dimensions"] = []
        return row

    def list_rubrics(
        self, mode: Optional[str] = None, confirmed_only: bool = False
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if mode:
            clauses.append("mode = ?")
            params.append(mode)
        if confirmed_only:
            clauses.append("is_confirmed = 1")
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._execute_query(
            f"SELECT * FROM rubrics {where_sql} ORDER BY id ASC",
            tuple(params),
            fetch_all=True,
        )
        return [self._deserialize_rubric(r) for r in rows if r]  # type: ignore

    def get_rubric_by_id(self, rubric_id: int) -> Optional[Dict[str, Any]]:
        row = self._execute_query(
            "SELECT * FROM rubrics WHERE id = ?", (rubric_id,), fetch_one=True
        )
        return self._deserialize_rubric(row)

    def create_rubric(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        dimensions_json = (
            json.dumps(data["dimensions"], ensure_ascii=False)
            if isinstance(data.get("dimensions"), list)
            else data.get("dimensions_json", "[]")
        )
        rubric_id = self._execute_query(
            """
            INSERT INTO rubrics (
                name, mode, framework_type, question_type, description,
                total_points, dimensions_json, source_filename, raw_source_text,
                is_confirmed, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data.get("mode", "authoritative"),
                data.get("framework_type", "SOLO"),
                data.get("question_type", "开放论述题"),
                data.get("description", ""),
                float(data.get("total_points", 100.0)),
                dimensions_json,
                data.get("source_filename"),
                data.get("raw_source_text"),
                1 if data.get("is_confirmed", True) else 0,
                data.get("created_by"),
                now,
            ),
            commit=True,
        )
        return self.get_rubric_by_id(rubric_id)  # type: ignore

    def update_rubric(
        self, rubric_id: int, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        existing = self.get_rubric_by_id(rubric_id)
        if not existing:
            return None
        name = data.get("name", existing["name"])
        question_type = data.get("question_type", existing["question_type"])
        description = data.get("description", existing["description"])
        total_points = float(data.get("total_points", existing["total_points"]))
        dimensions = data.get("dimensions", existing["dimensions"])
        dimensions_json = json.dumps(dimensions, ensure_ascii=False)
        is_confirmed = 1 if data.get("is_confirmed", True) else 0

        self._execute_query(
            """
            UPDATE rubrics
            SET name = ?, question_type = ?, description = ?, total_points = ?,
                dimensions_json = ?, is_confirmed = ?
            WHERE id = ?
            """,
            (
                name,
                question_type,
                description,
                total_points,
                dimensions_json,
                is_confirmed,
                rubric_id,
            ),
            commit=True,
        )
        return self.get_rubric_by_id(rubric_id)

    def delete_rubric(self, rubric_id: int) -> bool:
        existing = self.get_rubric_by_id(rubric_id)
        if not existing:
            return False
        self._execute_query(
            "DELETE FROM rubrics WHERE id = ?", (rubric_id,), commit=True
        )
        return True

    # ==================== 作业提交与评分管理 ====================
    def _deserialize_submission(
        self, row: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        for json_col, target_col in [
            ("clarification_questions_json", "clarification_questions"),
            ("clarification_answers_json", "clarification_answers"),
            ("dimension_scores_json", "dimension_scores"),
            ("improvement_suggestions_json", "improvement_suggestions"),
        ]:
            raw = row.get(json_col)
            try:
                row[target_col] = json.loads(raw) if raw else []
            except Exception:
                row[target_col] = []
        return row

    def create_submission(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        sub_id = self._execute_query(
            """
            INSERT INTO submissions (
                assignment_title, question_prompt, question_type,
                student_id, student_no, student_name, class_name,
                submission_type, file_name, file_path, mime_type, extracted_text,
                grading_mode, rubric_id, matched_rubric_name, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["assignment_title"],
                data["question_prompt"],
                data.get("question_type", "开放论述题"),
                int(data["student_id"]),
                data["student_no"],
                data["student_name"],
                data.get("class_name", ""),
                data.get("submission_type", "text"),
                data.get("file_name"),
                data.get("file_path"),
                data.get("mime_type"),
                data.get("extracted_text", ""),
                data.get("grading_mode", "authoritative"),
                data.get("rubric_id"),
                data.get("matched_rubric_name"),
                data.get("status", "submitted"),
                now,
                now,
            ),
            commit=True,
        )
        return self.get_submission_by_id(sub_id)  # type: ignore

    def get_submission_by_id(self, submission_id: int) -> Optional[Dict[str, Any]]:
        row = self._execute_query(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
            fetch_one=True,
        )
        return self._deserialize_submission(row)

    def list_submissions(
        self,
        student_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        assignment_title: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if student_id is not None:
            clauses.append("student_id = ?")
            params.append(student_id)
        if status_filter:
            clauses.append("status = ?")
            params.append(status_filter)
        if assignment_title:
            clauses.append("assignment_title LIKE ?")
            params.append(f"%{assignment_title}%")
        if keyword:
            clauses.append(
                "(student_name LIKE ? OR student_no LIKE ? OR assignment_title LIKE ?)"
            )
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._execute_query(
            f"SELECT * FROM submissions {where_sql} ORDER BY id DESC",
            tuple(params),
            fetch_all=True,
        )
        return [self._deserialize_submission(r) for r in rows if r]  # type: ignore

    def update_submission_grading(
        self, submission_id: int, update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        existing = self.get_submission_by_id(submission_id)
        if not existing:
            return None

        now = datetime.utcnow().isoformat()
        fields = []
        params: List[Any] = []

        mapping = {
            "status": "status",
            "grading_mode": "grading_mode",
            "rubric_id": "rubric_id",
            "matched_rubric_name": "matched_rubric_name",
            "extracted_text": "extracted_text",
            "total_score": "total_score",
            "final_score": "final_score",
            "cognitive_level": "cognitive_level",
            "overall_comment": "overall_comment",
            "teacher_adjustment_note": "teacher_adjustment_note",
            "reviewed_by": "reviewed_by",
            "reviewed_at": "reviewed_at",
        }
        for key, col in mapping.items():
            if key in update_data:
                fields.append(f"{col} = ?")
                params.append(update_data[key])

        json_mapping = {
            "clarification_questions": "clarification_questions_json",
            "clarification_answers": "clarification_answers_json",
            "dimension_scores": "dimension_scores_json",
            "improvement_suggestions": "improvement_suggestions_json",
        }
        for key, col in json_mapping.items():
            if key in update_data:
                fields.append(f"{col} = ?")
                params.append(
                    json.dumps(update_data[key], ensure_ascii=False)
                    if update_data[key] is not None
                    else None
                )

        fields.append("updated_at = ?")
        params.append(now)
        params.append(submission_id)

        self._execute_query(
            f"UPDATE submissions SET {', '.join(fields)} WHERE id = ?",
            tuple(params),
            commit=True,
        )
        return self.get_submission_by_id(submission_id)

    def delete_submission(self, submission_id: int) -> bool:
        existing = self.get_submission_by_id(submission_id)
        if not existing:
            return False
        self._execute_query(
            "DELETE FROM submissions WHERE id = ?", (submission_id,), commit=True
        )
        return True


# 全局单例仓储与依赖注入函数
db_repo = DatabaseRepository()


def get_db_repository() -> DatabaseRepository:
    return db_repo
