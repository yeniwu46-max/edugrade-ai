# EduGrade AI — 教学作业上传与双模式自动评分系统

一套前后端完整、开箱即用的教学作业智能批改与过程性诊断反馈系统。后端采用 **Python + FastAPI**，前端采用 **Vue 3 + Vite + Element Plus**，支持 **SQLite / PostgreSQL** 无缝切换与 **LLM Adapter 策略模式（默认 Gemini 多模态 API）**。

## 一、完整工程目录结构

```text
edugrade-ai/
├── README.md                          # 项目架构、接口契约与一键启动说明
├── start.sh                           # macOS / Linux 一键启动脚本
├── start.bat                          # Windows 一键启动脚本
├── backend/                           # Python + FastAPI 后端工程
│   ├── requirements.txt               # Python 依赖包清单
│   ├── .env.example                   # 环境变量配置模板（含数据库与 LLM API Key）
│   ├── uploads/                       # 作业与量规文件本地存储目录
│   └── app/
│       ├── main.py                    # FastAPI 应用主入口与启动种子数据初始化
│       ├── core/
│       │   ├── config.py              # 环境变量配置加载器
│       │   ├── database.py            # SQLite / PostgreSQL 统一数据访问仓储层
│       │   └── security.py            # JWT (HS256) 签发校验与教师/学生角色权限守卫
│       ├── models/
│       │   └── models.py              # SQLAlchemy 2.0 ORM 模型与跨库兼容建表 DDL
│       ├── schemas/
│       │   └── schemas.py             # Pydantic 前后端接口请求与响应契约
│       ├── services/
│       │   ├── llm_provider.py        # LLM 统一抽象层 (LLMProvider 基类 + Gemini/OpenAI/本地回退适配器)
│       │   ├── file_parser.py         # 多格式解析服务 (TXT/Word 本地提取 + 图片/扫描PDF Gemini 多模态读取)
│       │   └── seed_data.py           # 内置 SOLO 五水平量规、布鲁姆六层级量规及演示数据种子
│       └── routers/
│           ├── auth.py                # 登录鉴权与学生档案 CRUD 路由
│           ├── rubrics.py             # 模式A权威量规查询 & 模式B自定义量规 LLM 解析与人工确认路由
│           ├── assignments.py         # 单份/批量作业上传与作业列表管理路由
│           └── grading.py             # AI双模式评分、模糊澄清机制、教师人工复核与 Excel 导出路由
└── frontend/                          # Vue 3 + Vite + Element Plus 前端工程
    ├── package.json                   # 前端依赖与启动脚本
    ├── vite.config.js                 # Vite 配置与 /api 反向代理
    ├── index.html                     # 页面入口
    └── src/
        ├── main.js                    # Vue 3 + Element Plus + Pinia + Router 挂载入口
        ├── App.vue                    # 顶栏导航、LLM 状态指示与快捷角色切换器
        ├── api/
        │   └── index.js               # Axios 封装、JWT 拦截器与全部接口调用函数
        ├── stores/
        │   └── auth.js                # Pinia 登录态与角色管理
        ├── router/
        │   └── index.js               # 教师端与学生端路由权限守卫
        └── views/
            ├── LoginView.vue          # 登录页（支持一键填充教师/学生演示账号）
            ├── teacher/
            │   ├── TeacherDashboard.vue     # 教师端工作台（统计卡片、单份/批量上传、批量评分、导出 Excel）
            │   ├── SubmissionDetailView.vue # 作业详情页（原文对照、模糊澄清对话、分维度原文引用得分、人工复核抽屉）
            │   ├── RubricManageView.vue     # 双模式量规库（SOLO/布鲁姆展示 + 自定义量规上传解析与编辑确认）
            │   └── StudentManageView.vue    # 学生名册管理页
            └── student/
                └── StudentDashboard.vue     # 学生端工作台（提交新作业、查看分维度得分、原文引用依据与改进建议）
```

## 二、核心功能设计亮点

| 核心模块 | 实现机制说明 |
| :--- | :--- |
| **多格式与多模态作业读取** | `.txt` 与 `.docx` 使用本地解析库直接提取段落与表格文本；**图片作业 (`.png`/`.jpg`/`.webp`) 与扫描版 PDF (`.pdf`)** 直接调用 Gemini 多模态 (Vision) 原生读取。 |
| **模式 A「权威默认量规」** | 系统内置 **SOLO 分类评价法（前结构、单点结构、多点结构、关联结构、抽象扩展五水平）**、**布鲁姆教育目标分类（记忆、理解、应用、分析、评价、创造六层级）** 及程序设计量规，根据题型自动匹配。 |
| **模式 B「自定义量规学习」** | 教师上传 PDF / Word / 纯文本量规文档后，先由 `/api/rubrics/parse` 调用 LLM 提取评价维度、权重与等级描述并在前端表单展示，经教师核对/微调并点击确认后才通过 `/api/rubrics/confirm` 正式入库启用。 |
| **有据可依的评分输出** | 输出包含总分、认知层级、各维度分项得分、每一项的评分理由 (`rationale`) 与具体改进建议 (`improvement_suggestions`)。每个维度强制绑定 `evidence_quote`（直接引用的学生作业原句），杜绝空泛评语。 |
| **模糊澄清机制** | 当作业内容残缺/模糊、包含未完成标记、或与量规维度无法对应时，系统自动将状态置为 `needs_clarification` 并列出具体疑问点 (`Q1`, `Q2`...)，待教师或学生补充澄清答复后再执行评分，禁止在信息不足时臆测打分。 |
| **完整 JWT 双端角色鉴权** | 区分 `teacher`（教师教研端）与 `student`（学生学习端），前后端均实现严格的 JWT 校验与数据隔离，并在顶部导航提供演示账号一键切换。 |
| **LLM Adapter 策略模式** | `app/services/llm_provider.py` 封装 `LLMProvider` 抽象基类，内置 `GeminiProvider`、`OpenAICompatibleProvider` 及 `SmartLocalEngine`（无 Key 时亦可完整跑通所有业务闭环）。 |

## 三、本地一键启动步骤

### 方式一：使用一键启动脚本

- **macOS / Linux**：
  ```bash
  chmod +x start.sh
  ./start.sh
  ```
- **Windows**：
  双击运行 `start.bat` 或在命令行执行：
  ```bat
  start.bat
  ```

### 方式二：分步手动启动（推荐开发调试）

1. **启动后端 (FastAPI)**：
   ```bash
   cd backend
   cp .env.example .env
   # 编辑 .env 填入你的 GEMINI_API_KEY（不填也可使用内置启发式引擎直接体验全部功能）
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   - 后端接口地址：`http://127.0.0.1:8000`
   - Swagger 交互式接口文档：`http://127.0.0.1:8000/docs`

2. **启动前端 (Vue 3 + Vite)**：
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   - 前端访问地址：`http://127.0.0.1:5173`

## 四、内置演示账号与预置数据

系统首次启动时会自动创建 SQLite 数据库并写入以下测试账号与 3 份典型状态的作业：

| 角色 | 登录账号 | 默认密码 | 姓名 / 班级 | 预置作业状态说明 |
| :--- | :--- | :--- | :--- | :--- |
| **教师端** | `teacher` | `123456` | 张明远（教研组长） | 可管理全部作业、量规、复核与导出 Excel |
| **学生端 1** | `2026001` | `123456` | 林知夏（高二1班） | 预置 1 份已完成 SOLO 五水平评分的高分论述作业（含原文引用） |
| **学生端 2** | `2026002` | `123456` | 陈宇轩（高二1班） | 预置 1 份触发 **模糊澄清机制 (`needs_clarification`)** 的扫描版 PDF 作业 |
| **学生端 3** | `2026003` | `123456` | 苏沐晴（高二2班） | 预置 1 份已上传待评分 (`submitted`) 的作业，可一键点击测试 AI 评分 |

## 五、前后端核心 API 接口契约

| 模块 | 方法与路径 | 权限 | 功能描述 |
| :--- | :--- | :--- | :--- |
| **认证** | `POST /api/auth/login` | 公开 | 账号/学号登录，返回 JWT `access_token` 与用户信息 |
| **认证** | `GET /api/auth/me` | 登录用户 | 获取当前登录用户详情 |
| **学生** | `GET /api/students` | 登录用户 | 查询学生列表（支持 `keyword` 模糊搜索） |
| **学生** | `POST /api/students` | 仅教师 | 新增学生信息并自动创建学生端登录账号 |
| **量规** | `GET /api/rubrics` | 登录用户 | 获取量规列表（支持 `mode=authoritative\|custom`） |
| **量规** | `POST /api/rubrics/parse` | 仅教师 | **模式B第一步**：上传 PDF/Word/TXT 量规文档，LLM 解析维度与权重供前端确认 |
| **量规** | `POST /api/rubrics/confirm` | 仅教师 | **模式B第二步**：用户确认解析结果无误后正式保存启用自定义量规 |
| **作业** | `GET /api/submissions` | 登录用户 | 查询作业列表（学生端自动隔离仅返回本人作业） |
| **作业** | `POST /api/submissions/upload` | 登录用户 | 上传单份作业（支持文本、图片、PDF、Word `.docx`） |
| **作业** | `POST /api/submissions/batch-upload` | 仅教师 | 批量上传多份作业文件并自动匹配学生名册 |
| **评分** | `POST /api/grading/{id}/evaluate` | 仅教师 | 执行双模式自动评分（若信息模糊则返回 `needs_clarification` 及具体问题列表） |
| **评分** | `POST /api/grading/{id}/clarify` | 登录用户 | 提交模糊澄清答复及补充说明，系统结合澄清上下文立即完成评分 |
| **评分** | `POST /api/grading/batch-evaluate` | 仅教师 | 批量自动评分并汇总已评分与需澄清数量 |
| **评分** | `PUT /api/grading/{id}/review` | 仅教师 | 教师端人工复核与分数/评语/分项得分手动修正 |
| **导出** | `GET /api/grading/export/excel` | 仅教师 | 导出双 Sheet 专业排版 Excel 成绩单（含分维度得分与原文引用明细） |

## 六、切换至 PostgreSQL 数据库说明

项目在 `backend/app/core/database.py` 与 `backend/app/models/models.py` 中已完成双数据库兼容封装。当需要从默认 SQLite 切换至生产环境 PostgreSQL 时，只需修改 `backend/.env` 中的 `DATABASE_URL`：

```env
DATABASE_URL="postgresql+psycopg2://postgres:your_password@localhost:5432/edugrade_db"
```
重启后端服务即可自动在 PostgreSQL 中建表并初始化种子数据，无需改动业务代码。
