"""
系统内置种子数据初始化服务 (`seed_data.py`)：
1. 初始化默认教师账号与 3 个测试学生账号（密码均为 123456）
2. 初始化三大内置权威默认量规（模式 A）：
   - SOLO 分类评价法（前结构、单点结构、多点结构、关联结构、抽象扩展五水平）—— 适用于「开放论述题 / 历史政治思辨题」
   - 布鲁姆 (Bloom) 教育目标分类量规（记忆、理解、应用、分析、评价、创造六层级）—— 适用于「案例分析题 / 科学探究与实验设计」
   - 程序设计与算法工程权威量规（融合布鲁姆应用-分析-创造与代码工程规范）—— 适用于「编程与算法题」
3. 初始化 3 份典型示例作业：
   - 作业 1（林知夏）：已完成 SOLO 权威量规评分，包含完整的分维度得分、原文句子引用与改进建议
   - 作业 2（陈宇轩）：内容存在残缺与模糊表述，处于 `needs_clarification`（待模糊澄清）状态，方便直接演示模糊澄清机制
   - 作业 3（苏沐晴）：新上传待评分状态 (`submitted`)，方便一键点击触发 AI 评分或批量评分
"""
from typing import Any, Dict, List

from app.core.database import DatabaseRepository
from app.core.security import hash_password


AUTHORITATIVE_RUBRICS: List[Dict[str, Any]] = [
    {
        "name": "SOLO 分类评价法标准量规（五水平深度思维评价）",
        "mode": "authoritative",
        "framework_type": "SOLO",
        "question_type": "开放论述题",
        "description": (
            "基于比格斯 (Biggs) SOLO 分类理论（可观察的学习成果结构），从「前结构、单点结构、多点结构、关联结构、抽象扩展结构」"
            "五个思维层级评估学生论述的认知结构复杂度与迁移创新能力。"
        ),
        "total_points": 100.0,
        "is_confirmed": True,
        "dimensions": [
            {
                "name": "核心概念界定与论点结构层级",
                "weight": 35.0,
                "max_score": 35.0,
                "description": "考察学生对核心议题的理解处于孤立单点还是系统性关联结构。",
                "levels": [
                    {
                        "level_name": "抽象扩展结构 (Extended Abstract)",
                        "score_range": "31-35分",
                        "min_ratio": 0.88,
                        "max_ratio": 1.0,
                        "description": "不仅整合多维要素形成严密体系，还能跳出给定材料提炼普适性原理或预判边界条件。",
                    },
                    {
                        "level_name": "关联结构 (Relational)",
                        "score_range": "26-30.5分",
                        "min_ratio": 0.74,
                        "max_ratio": 0.87,
                        "description": "能够围绕核心主线将多个相关概念有机串联，解释各要素之间的内在因果机理。",
                    },
                    {
                        "level_name": "多点结构 (Multistructural)",
                        "score_range": "21-25.5分",
                        "min_ratio": 0.60,
                        "max_ratio": 0.73,
                        "description": "罗列了两个及以上相关要点，但各要点之间彼此孤立、缺乏深层逻辑整合。",
                    },
                    {
                        "level_name": "单点结构 (Unistructural)",
                        "score_range": "14-20.5分",
                        "min_ratio": 0.40,
                        "max_ratio": 0.59,
                        "description": "仅抓住题目中的单一线索简单作答，视野局限于表面现象。",
                    },
                    {
                        "level_name": "前结构 (Prestructural)",
                        "score_range": "0-13.5分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.39,
                        "description": "未能理解问题核心，同义反复或观点完全偏离题意。",
                    },
                ],
            },
            {
                "name": "多维论据整合与因果链条推导",
                "weight": 35.0,
                "max_score": 35.0,
                "description": "考察事实论据、理论依据与核心论点之间的逻辑严密程度。",
                "levels": [
                    {
                        "level_name": "抽象扩展结构 (Extended Abstract)",
                        "score_range": "31-35分",
                        "min_ratio": 0.88,
                        "max_ratio": 1.0,
                        "description": "综合正反多维证据并进行反事实推演或跨学科验证，论证无懈可击。",
                    },
                    {
                        "level_name": "关联结构 (Relational)",
                        "score_range": "26-30.5分",
                        "min_ratio": 0.74,
                        "max_ratio": 0.87,
                        "description": "多个论据彼此呼应，能够清晰说明“为何这些证据共同导出结论”。",
                    },
                    {
                        "level_name": "多点结构 (Multistructural)",
                        "score_range": "21-25.5分",
                        "min_ratio": 0.60,
                        "max_ratio": 0.73,
                        "description": "堆砌了若干案例或事实，但缺乏对材料背后机制的剖析。",
                    },
                    {
                        "level_name": "单点/前结构 (Uni/Prestructural)",
                        "score_range": "0-20.5分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.59,
                        "description": "仅凭主观臆断或单一孤证下结论，缺乏推理过程。",
                    },
                ],
            },
            {
                "name": "批判性反思与跨情境迁移拓展",
                "weight": 30.0,
                "max_score": 30.0,
                "description": "考察对结论适用前提的审视以及将原理迁移至新情境的能力。",
                "levels": [
                    {
                        "level_name": "抽象扩展结构 (Extended Abstract)",
                        "score_range": "26.5-30分",
                        "min_ratio": 0.88,
                        "max_ratio": 1.0,
                        "description": "主动剖析方案潜在风险与伦理/现实边界，提出具有创新价值的迁移方案。",
                    },
                    {
                        "level_name": "关联结构 (Relational)",
                        "score_range": "22-26分",
                        "min_ratio": 0.73,
                        "max_ratio": 0.87,
                        "description": "在给定框架内进行了较为全面的总结与利弊权衡。",
                    },
                    {
                        "level_name": "多点及以下结构",
                        "score_range": "0-21.5分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.72,
                        "description": "缺乏反思意识，结论流于口号式总结。",
                    },
                ],
            },
        ],
    },
    {
        "name": "布鲁姆 (Bloom) 教育目标分类标准量规（六认知维度）",
        "mode": "authoritative",
        "framework_type": "BLOOM",
        "question_type": "案例分析与科学探究题",
        "description": (
            "依据修订版布鲁姆教育目标分类学（记忆、理解、应用、分析、评价、创造），"
            "系统评估学生从基础概念掌握到高阶问题解决与创新方案设计的达成度。"
        ),
        "total_points": 100.0,
        "is_confirmed": True,
        "dimensions": [
            {
                "name": "基础认知：概念记忆与原理理解 (Remember & Understand)",
                "weight": 25.0,
                "max_score": 25.0,
                "description": "准确复述核心概念并用自己的语言解释原理机制。",
                "levels": [
                    {
                        "level_name": "精通 (22-25分)",
                        "score_range": "22-25分",
                        "min_ratio": 0.88,
                        "max_ratio": 1.0,
                        "description": "核心术语定义零误差，能清晰阐明原理的来龙去脉。",
                    },
                    {
                        "level_name": "熟练 (17.5-21.5分)",
                        "score_range": "17.5-21.5分",
                        "min_ratio": 0.70,
                        "max_ratio": 0.87,
                        "description": "基本理解核心概念，但个别细节表述不够精准。",
                    },
                    {
                        "level_name": "待巩固 (0-17分)",
                        "score_range": "0-17分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.69,
                        "description": "存在明显概念混淆或原理记忆错误。",
                    },
                ],
            },
            {
                "name": "中阶认知：情境应用与要素分析 (Apply & Analyze)",
                "weight": 40.0,
                "max_score": 40.0,
                "description": "将理论模型应用于具体案例情境，拆解变量关系并识别关键矛盾。",
                "levels": [
                    {
                        "level_name": "高阶分析 (35-40分)",
                        "score_range": "35-40分",
                        "min_ratio": 0.88,
                        "max_ratio": 1.0,
                        "description": "精准拆解案例中的自变量、因变量与干扰因素，定量与定性分析结合紧密。",
                    },
                    {
                        "level_name": "有效应用 (28-34.5分)",
                        "score_range": "28-34.5分",
                        "min_ratio": 0.70,
                        "max_ratio": 0.87,
                        "description": "能够套用所学方法解决情境问题，但对隐含条件的剖析不够深入。",
                    },
                    {
                        "level_name": "机械套用 (0-27.5分)",
                        "score_range": "0-27.5分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.69,
                        "description": "理论与案例脱节，未能完成有效的要素拆解。",
                    },
                ],
            },
            {
                "name": "高阶认知：方案评价与创新设计 (Evaluate & Create)",
                "weight": 35.0,
                "max_score": 35.0,
                "description": "基于明确准则评判既有方案优劣，并构建可落地的优化或创新方案。",
                "levels": [
                    {
                        "level_name": "卓越创造 (30.5-35分)",
                        "score_range": "30.5-35分",
                        "min_ratio": 0.87,
                        "max_ratio": 1.0,
                        "description": "能指出既有方法局限并提出结构完整、具备可行性的创新改进设计。",
                    },
                    {
                        "level_name": "合理评价 (24.5-30分)",
                        "score_range": "24.5-30分",
                        "min_ratio": 0.70,
                        "max_ratio": 0.86,
                        "description": "能对方案做出合理评价，提出的改进建议具有一定参考价值。",
                    },
                    {
                        "level_name": "缺乏创见 (0-24分)",
                        "score_range": "0-24分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.69,
                        "description": "仅有简单结论，未给出可验证的改进方案。",
                    },
                ],
            },
        ],
    },
    {
        "name": "程序设计与算法实验权威评价量规（SOLO + 布鲁姆融合）",
        "mode": "authoritative",
        "framework_type": "BLOOM",
        "question_type": "编程与算法题",
        "description": "适用于计算机科学、Python/数据结构实验报告与代码作业，从算法正确性、时空复杂度分析、代码工程规范三个维度评分。",
        "total_points": 100.0,
        "is_confirmed": True,
        "dimensions": [
            {
                "name": "算法逻辑正确性与边界条件处理",
                "weight": 45.0,
                "max_score": 45.0,
                "description": "考察核心算法思路是否正确，是否覆盖空输入、极值等边界用例。",
                "levels": [
                    {
                        "level_name": "优秀 (39-45分)",
                        "score_range": "39-45分",
                        "min_ratio": 0.87,
                        "max_ratio": 1.0,
                        "description": "算法逻辑严密，全面处理各类边界条件与异常分支。",
                    },
                    {
                        "level_name": "良好 (31.5-38.5分)",
                        "score_range": "31.5-38.5分",
                        "min_ratio": 0.70,
                        "max_ratio": 0.86,
                        "description": "主流程正确，但个别极端边界条件未做防御处理。",
                    },
                    {
                        "level_name": "待改进 (0-31分)",
                        "score_range": "0-31分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.69,
                        "description": "核心逻辑存在缺陷或无法通过基础测试用例。",
                    },
                ],
            },
            {
                "name": "时间与空间复杂度分析及优化",
                "weight": 30.0,
                "max_score": 30.0,
                "description": "考察对 Big-O 复杂度的推导准确性以及数据结构选型合理性。",
                "levels": [
                    {
                        "level_name": "优秀 (26-30分)",
                        "score_range": "26-30分",
                        "min_ratio": 0.87,
                        "max_ratio": 1.0,
                        "description": "准确推导时间与空间复杂度，并给出了从暴力解到最优解的演进分析。",
                    },
                    {
                        "level_name": "良好 (21-25.5分)",
                        "score_range": "21-25.5分",
                        "min_ratio": 0.70,
                        "max_ratio": 0.86,
                        "description": "给出了复杂度结论，但推导过程略简略。",
                    },
                    {
                        "level_name": "待改进 (0-20.5分)",
                        "score_range": "0-20.5分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.69,
                        "description": "未包含复杂度分析或采用低效冗余实现。",
                    },
                ],
            },
            {
                "name": "代码可读性、模块化与测试验证",
                "weight": 25.0,
                "max_score": 25.0,
                "description": "考察函数拆分、命名规范、注释说明及自测结果分析。",
                "levels": [
                    {
                        "level_name": "优秀 (21.5-25分)",
                        "score_range": "21.5-25分",
                        "min_ratio": 0.86,
                        "max_ratio": 1.0,
                        "description": "模块化清晰、注释到位，附有完整的测试用例与运行结果对比。",
                    },
                    {
                        "level_name": "良好/及格 (0-21分)",
                        "score_range": "0-21分",
                        "min_ratio": 0.0,
                        "max_ratio": 0.85,
                        "description": "代码结构一般或缺少测试验证环节。",
                    },
                ],
            },
        ],
    },
]


def match_authoritative_rubric(
    question_type: str, question_prompt: str, repo: DatabaseRepository
) -> Dict[str, Any]:
    """根据作业题型与题目描述，自动匹配最合适的内置权威量规（模式 A）。"""
    auth_rubrics = repo.list_rubrics(mode="authoritative", confirmed_only=True)
    if not auth_rubrics:
        seed_initial_data(repo)
        auth_rubrics = repo.list_rubrics(mode="authoritative", confirmed_only=True)

    combined = f"{question_type} {question_prompt}".lower()
    if any(k in combined for k in ["编程", "算法", "代码", "python", "复杂度", "数据结构"]):
        for r in auth_rubrics:
            if "程序" in r["name"] or "算法" in r["name"]:
                return r
    if any(k in combined for k in ["案例", "实验", "科学", "探究", "bloom", "布鲁姆", "方案设计"]):
        for r in auth_rubrics:
            if r["framework_type"] == "BLOOM":
                return r
    # 默认匹配 SOLO 分类评价法五水平量规
    return auth_rubrics[0]


def seed_initial_data(repo: DatabaseRepository) -> None:
    """初始化表结构与演示种子数据（幂等操作，已有数据时不重复插入）。"""
    repo.init_tables()

    # 1. 初始化默认教师与学生账号
    teacher = repo.get_user_by_username("teacher")
    if not teacher:
        teacher = repo.create_user(
            {
                "username": "teacher",
                "password_hash": hash_password("123456"),
                "full_name": "张明远（教研组长）",
                "role": "teacher",
                "email": "zhangmingyuan@edugrade.edu.cn",
            }
        )

    students_seed = [
        {
            "username": "2026001",
            "student_no": "2026001",
            "full_name": "林知夏",
            "class_name": "高二(1)班 创新实验班",
            "email": "linzhixia@student.edu.cn",
        },
        {
            "username": "2026002",
            "student_no": "2026002",
            "full_name": "陈宇轩",
            "class_name": "高二(1)班 创新实验班",
            "email": "chenyuxuan@student.edu.cn",
        },
        {
            "username": "2026003",
            "student_no": "2026003",
            "full_name": "苏沐晴",
            "class_name": "高二(2)班 人文强化班",
            "email": "sumuqing@student.edu.cn",
        },
    ]
    student_map: Dict[str, Dict[str, Any]] = {}
    for s in students_seed:
        existing_s = repo.get_user_by_username(s["username"])
        if not existing_s:
            existing_s = repo.create_user(
                {
                    **s,
                    "password_hash": hash_password("123456"),
                    "role": "student",
                }
            )
        student_map[s["student_no"]] = existing_s

    # 2. 初始化内置权威默认量规
    existing_rubrics = repo.list_rubrics()
    if not existing_rubrics:
        for r_data in AUTHORITATIVE_RUBRICS:
            repo.create_rubric({**r_data, "created_by": teacher["id"]})
        existing_rubrics = repo.list_rubrics()

    solo_rubric = existing_rubrics[0]
    bloom_rubric = existing_rubrics[1] if len(existing_rubrics) > 1 else solo_rubric

    # 3. 初始化 3 份覆盖完整生命周期的示例学生作业
    existing_subs = repo.list_submissions()
    if not existing_subs:
        # 示例 1：已完成 SOLO 五水平评分的高质量论述作业（林知夏）
        sub1 = repo.create_submission(
            {
                "assignment_title": "人工智能生成内容 (AIGC) 对基础教育评价范式的冲击与重构",
                "question_prompt": (
                    "请结合教育学原理与实际教学情境，论述生成式人工智能对传统作业评价带来的挑战，"
                    "并提出具有可行性的过程性评价改革方案（要求观点明确、论据充分、体现辩证思考）。"
                ),
                "question_type": "开放论述题",
                "student_id": student_map["2026001"]["id"],
                "student_no": "2026001",
                "student_name": "林知夏",
                "class_name": "高二(1)班 创新实验班",
                "submission_type": "text",
                "file_name": "林知夏_AIGC与教育评价重构论述.docx",
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "extracted_text": (
                    "生成式人工智能的普及正在动摇以“标准答案和终结性纸笔测试”为核心的传统评价范式。"
                    "首先，在知识获取层面，当大模型能够在数秒内生成结构工整的议论文或代码时，传统的单纯考察事实记忆与机械模仿的课后作业已失去甄别效度。"
                    "其次，这并不意味着书面作业失去了教育价值，关键在于评价重心必须从“静态结果查验”转向“高阶思维过程追踪”。"
                    "例如，在高中历史探究课中，教师可以要求学生提交完整的Prompt提问迭代日志与对AI输出谬误的批判性核查报告，从而考察其信息甄别与元认知监控能力。"
                    "然而，我们也必须警惕技术赋能背后的数字鸿沟与算法偏见风险：若过度依赖自动化评分模型而缺乏教师的人文裁量，容易导致创造性异质思维被均值化标准抹杀。"
                    "因此，未来的教育评价应构建“AI诊断性量规反馈 + 教师苏格拉底式追问 + 学生多轮修正”的人机协同闭环。"
                ),
                "grading_mode": "authoritative",
                "rubric_id": solo_rubric["id"],
                "matched_rubric_name": solo_rubric["name"],
                "status": "graded",
            }
        )
        repo.update_submission_grading(
            sub1["id"],
            {
                "status": "graded",
                "total_score": 91.5,
                "final_score": 91.5,
                "cognitive_level": "SOLO 抽象扩展结构 (Extended Abstract) / 布鲁姆：评价与创造层",
                "overall_comment": (
                    "这是一篇达到 SOLO「抽象扩展结构 (Extended Abstract)」水准的优秀论述作业。"
                    "林知夏同学不仅清晰剖析了 AIGC 冲击传统作业效度的内在机理（关联结构），"
                    "更进一步审视了算法偏见与创造性异质思维被均值化的技术伦理边界，提出了“人机协同评价闭环”的系统构想。"
                ),
                "dimension_scores": [
                    {
                        "dimension_name": "核心概念界定与论点结构层级",
                        "weight": 35.0,
                        "max_score": 35.0,
                        "score": 32.5,
                        "level_reached": "抽象扩展结构 (Extended Abstract)",
                        "evidence_quote": "传统的单纯考察事实记忆与机械模仿的课后作业已失去甄别效度……关键在于评价重心必须从“静态结果查验”转向“高阶思维过程追踪”。",
                        "rationale": "直接命中传统终结性评价失效的本质原因，并建立起“静态结果”向“高阶思维过程”跃迁的核心论点主线，各概念关联紧密。",
                        "dimension_suggestion": "可进一步界定“高阶思维过程”在不同学段或学科中的具体可观测指标。",
                    },
                    {
                        "dimension_name": "多维论据整合与因果链条推导",
                        "weight": 35.0,
                        "max_score": 35.0,
                        "score": 31.5,
                        "level_reached": "关联结构至抽象扩展结构",
                        "evidence_quote": "在高中历史探究课中，教师可以要求学生提交完整的Prompt提问迭代日志与对AI输出谬误的批判性核查报告，从而考察其信息甄别与元认知监控能力。",
                        "rationale": "以高中历史探究课为具体情境案例，将抽象的“过程性评价”落地为“Prompt日志+谬误核查报告”，论据与论点之间形成了严密的因果支撑。",
                        "dimension_suggestion": "若能补充一个理科实验或实证数据对比案例，跨学科说服力将更强。",
                    },
                    {
                        "dimension_name": "批判性反思与跨情境迁移拓展",
                        "weight": 30.0,
                        "max_score": 30.0,
                        "score": 27.5,
                        "level_reached": "抽象扩展结构 (Extended Abstract)",
                        "evidence_quote": "我们也必须警惕技术赋能背后的数字鸿沟与算法偏见风险：若过度依赖自动化评分模型而缺乏教师的人文裁量，容易导致创造性异质思维被均值化标准抹杀。",
                        "rationale": "跳出了单纯赞美技术效率的视角，深刻反思了自动化评分可能抹杀“创造性异质思维”的边界条件，体现了极高的批判性思辨水平。",
                        "dimension_suggestion": "可针对如何防范“均值化抹杀”补充一条具体的量规设计原则（如增设模糊澄清与人工复核机制）。",
                    },
                ],
                "improvement_suggestions": [
                    "【拓展跨学科实证】在“高中历史探究课”案例之外，建议补充一个理工科（如物理实验设计或算法编程）的过程性评价对比案例，使改革方案更具普适性。",
                    "【细化操作指标】针对文末提出的“人机协同闭环”，可以尝试设计一份包含权重分配的 3 维微量规示例，增强方案的可操作性。",
                ],
            },
        )

        # 示例 2：触发「模糊澄清机制」的残缺/存疑作业（陈宇轩）
        sub2 = repo.create_submission(
            {
                "assignment_title": "城市热岛效应成因分析与海绵城市缓解方案设计",
                "question_prompt": (
                    "结合地理与环境科学知识，分析高密度城市热岛效应的三大核心热力学成因，"
                    "并针对你所在城市设计一套可量化的海绵城市降温与雨水调蓄综合方案。"
                ),
                "question_type": "案例分析与科学探究题",
                "student_id": student_map["2026002"]["id"],
                "student_no": "2026002",
                "student_name": "陈宇轩",
                "class_name": "高二(1)班 创新实验班",
                "submission_type": "pdf",
                "file_name": "陈宇轩_海绵城市方案扫描件.pdf",
                "mime_type": "application/pdf",
                "extracted_text": (
                    "一、热岛效应成因：主要是城市水泥地面太多，吸收太阳辐射多，而且空调和汽车尾气排放大量人为热。"
                    "二、海绵城市设计方案：（此处手写草图字迹模糊，参数表格第2页缺失，此处略，不确定题目是否要求计算年径流总量控制率）。"
                ),
                "grading_mode": "authoritative",
                "rubric_id": bloom_rubric["id"],
                "matched_rubric_name": bloom_rubric["name"],
                "status": "needs_clarification",
            }
        )
        repo.update_submission_grading(
            sub2["id"],
            {
                "status": "needs_clarification",
                "clarification_questions": [
                    {
                        "id": "Q1",
                        "category": "作业内容不清",
                        "question": (
                            "学生在第二部分方案设计中写道「（此处手写草图字迹模糊，参数表格第2页缺失，此处略）」，"
                            "导致无法评估布鲁姆「方案评价与创新设计 (35%)」维度。请确认：是否由教师补充学生草图中的核心设计参数，或按方案缺失直接在该维度扣分？"
                        ),
                        "context_excerpt": "二、海绵城市设计方案：（此处手写草图字迹模糊，参数表格第2页缺失，此处略，不确定题目是否要求计算年径流总量控制率）。",
                    },
                    {
                        "id": "Q2",
                        "category": "题目与量规不匹配",
                        "question": (
                            "学生提到「不确定题目是否要求计算年径流总量控制率」。请澄清本次作业评分标准中，"
                            "定量水文计算（如年径流总量控制率）是否为必考得分点？"
                        ),
                        "context_excerpt": "不确定题目是否要求计算年径流总量控制率",
                    },
                ],
            },
        )

        # 示例 3：已上传待评分的完整作业（苏沐晴）
        repo.create_submission(
            {
                "assignment_title": "人工智能生成内容 (AIGC) 对基础教育评价范式的冲击与重构",
                "question_prompt": (
                    "请结合教育学原理与实际教学情境，论述生成式人工智能对传统作业评价带来的挑战，"
                    "并提出具有可行性的过程性评价改革方案（要求观点明确、论据充分、体现辩证思考）。"
                ),
                "question_type": "开放论述题",
                "student_id": student_map["2026003"]["id"],
                "student_no": "2026003",
                "student_name": "苏沐晴",
                "class_name": "高二(2)班 人文强化班",
                "submission_type": "text",
                "file_name": "苏沐晴_教育评价思考作业.txt",
                "mime_type": "text/plain",
                "extracted_text": (
                    "随着大模型技术走进校园，传统课后作业面临着严峻的真实性危机。首先，学生可以轻易借助工具完成概要总结与基础写作，"
                    "如果教师依然仅凭最终交上来的文本字数和表面流畅度打分，将无法区分哪些是学生真实的认知建构，哪些是算法生成的套话。"
                    "其次，我认为应对这一挑战的核心在于引入基于SOLO分类法的结构化量规与口头答辩抽查机制。"
                    "具体而言，教师在布置开放性课题时，不仅要求学生提交文本，还应要求学生标注自己引用的核心一手文献，并在课堂上进行3分钟的追问式互评。"
                    "此外，我们还应当引导学生把AI当作“反方辩友”，让学生在作业中专门增加一个“AI观点批判与修正”小节，记录自己如何发现并纠正大模型的事实幻觉。"
                    "综上所述，只有将评价维度锚定在批判性审视与真实情境迁移上，才能让技术真正服务于学生的思维成长。"
                ),
                "grading_mode": "authoritative",
                "rubric_id": solo_rubric["id"],
                "matched_rubric_name": solo_rubric["name"],
                "status": "submitted",
            }
        )
