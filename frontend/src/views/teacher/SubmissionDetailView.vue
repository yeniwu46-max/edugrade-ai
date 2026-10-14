<template>
  <div v-if="submission" v-loading="loading">
    <!-- 顶部返回与模式切换操作栏 -->
    <el-card shadow="never" style="margin-bottom: 18px">
      <div class="detail-header">
        <div class="left-info">
          <el-button icon="ArrowLeft" @click="router.push('/teacher/submissions')">
            返回作业列表
          </el-button>
          <span class="sub-title">
            {{ submission.student_name }}（{{ submission.student_no }}）— {{ submission.assignment_title }}
          </span>
          <el-tag :type="statusTagType(submission.status)" effect="dark">
            {{ statusText(submission.status) }}
          </el-tag>
        </div>

        <div class="right-controls">
          <el-select
            v-model="evalConfig.grading_mode"
            style="width: 195px"
            @change="onModeChange"
          >
            <el-option label="模式A：权威默认量规" value="authoritative" />
            <el-option label="模式B：自定义量规" value="custom" />
          </el-select>

          <el-select
            v-model="evalConfig.rubric_id"
            placeholder="选择适用量规"
            style="width: 260px"
          >
            <el-option
              v-for="r in filteredRubrics"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </el-select>

          <el-button
            type="primary"
            icon="MagicStick"
            :loading="evaluating"
            @click="handleEvaluate(false)"
          >
            执行 AI 评分
          </el-button>
          <el-button
            v-if="submission.dimension_scores && submission.dimension_scores.length"
            type="warning"
            icon="EditPen"
            @click="openReviewDrawer"
          >
            教师人工复核与修正
          </el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20">
      <!-- 左侧：题目要求与学生作业原文 -->
      <el-col :span="10">
        <el-card shadow="never" style="margin-bottom: 18px">
          <template #header>
            <div class="card-header-title">
              <span>一、题目要求与评价量规信息</span>
              <el-tag size="small" type="info">{{ submission.question_type }}</el-tag>
            </div>
          </template>
          <div class="prompt-box">{{ submission.question_prompt }}</div>
          <div style="margin-top: 12px; font-size: 13px; color: #475569">
            <strong>当前绑定量规：</strong>{{ submission.matched_rubric_name || '待匹配' }}
          </div>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="card-header-title">
              <span>二、学生作业内容原文</span>
              <el-tag size="small" effect="plain">
                来源: {{ submission.file_name || '直接文本提交' }} ({{ submission.submission_type.toUpperCase() }})
              </el-tag>
            </div>
          </template>
          <div class="homework-text-box">
            {{ submission.extracted_text || '（无文本内容）' }}
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：模糊澄清交互区 或 结构化评分结果展示区 -->
      <el-col :span="14">
        <!-- 1. 模糊澄清机制面板 (当 status === 'needs_clarification' 时高亮展示) -->
        <el-card
          v-if="submission.status === 'needs_clarification'"
          shadow="always"
          class="clarification-card"
        >
          <template #header>
            <div class="clarification-header">
              <span>⚠️ 模糊澄清机制已触发：检测到关键信息不足或存疑（禁止盲目臆测打分）</span>
            </div>
          </template>

          <el-alert
            title="系统在审阅作业与量规对应关系时发现以下具体疑问点。请逐条澄清或补充说明，确认后系统将结合您的回复立即完成精准评分："
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 16px"
          />

          <div
            v-for="(q, idx) in submission.clarification_questions"
            :key="q.id || idx"
            class="question-item"
          >
            <div class="q-title">
              <el-tag size="small" type="danger" style="margin-right: 8px">
                {{ q.id || `Q${idx + 1}` }} · {{ q.category }}
              </el-tag>
              <span>{{ q.question }}</span>
            </div>
            <div v-if="q.context_excerpt" class="q-excerpt">
              触发疑问片段：“{{ q.context_excerpt }}”
            </div>
            <el-input
              v-model="clarifyAnswers[idx]"
              type="textarea"
              :rows="2"
              placeholder="请在此输入针对该疑问点的澄清说明或评分指示..."
              style="margin-top: 8px"
            />
          </div>

          <div style="margin-top: 16px">
            <div style="font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #334155">
              可选：补充或修正学生作业中的缺失文字（如手写草图参数、缺页内容）
            </div>
            <el-input
              v-model="supplementalText"
              type="textarea"
              :rows="3"
              placeholder="若原件为手写草图或存在扫描残缺，可在此直接补充文字内容..."
            />
          </div>

          <div style="margin-top: 18px; display: flex; gap: 12px; justify-content: flex-end">
            <el-button
              type="info"
              plain
              :loading="evaluating"
              @click="handleEvaluate(true)"
            >
              跳过澄清，按现有内容直接从严评分
            </el-button>
            <el-button
              type="primary"
              :loading="clarifying"
              @click="handleSubmitClarification"
            >
              提交澄清答复并立即完成评分
            </el-button>
          </div>
        </el-card>

        <!-- 2. 结构化评分报告面板 -->
        <el-card
          v-if="submission.dimension_scores && submission.dimension_scores.length"
          shadow="never"
        >
          <template #header>
            <div class="card-header-title">
              <span>三、双模式智能评分与诊断报告</span>
              <span v-if="submission.reviewed_by" style="font-size: 12px; color: #2563eb">
                已由 {{ submission.reviewed_by }} 人工复核确认
              </span>
            </div>
          </template>

          <!-- 总分与认知层级横幅 -->
          <div class="score-banner">
            <div class="score-circle">
              <div class="num">{{ submission.final_score ?? submission.total_score }}</div>
              <div class="total">/ 100 分</div>
            </div>
            <div class="banner-right">
              <div class="cog-badge">
                认知发展水平：{{ submission.cognitive_level || 'SOLO 关联结构' }}
              </div>
              <div class="overall-comment">{{ submission.overall_comment }}</div>
              <div
                v-if="submission.teacher_adjustment_note"
                class="teacher-note"
              >
                <strong>教师复核修正说明：</strong>{{ submission.teacher_adjustment_note }}
              </div>
            </div>
          </div>

          <!-- 各维度分项得分、原文引用与评分理由 -->
          <h4 class="section-subtitle">各维度分项得分与原文依据（禁止空泛评价）</h4>
          <div
            v-for="(dim, idx) in submission.dimension_scores"
            :key="idx"
            class="dim-card"
          >
            <div class="dim-top">
              <div>
                <span class="dim-name">{{ idx + 1 }}. {{ dim.dimension_name }}</span>
                <el-tag size="small" type="info" style="margin-left: 8px">
                  权重 {{ dim.weight }}%
                </el-tag>
                <el-tag size="small" type="success" style="margin-left: 6px">
                  {{ dim.level_reached }}
                </el-tag>
              </div>
              <div class="dim-score">
                <strong>{{ dim.score }}</strong> / {{ dim.max_score }} 分
              </div>
            </div>

            <el-progress
              :percentage="Math.min(100, Math.round((dim.score / (dim.max_score || 1)) * 100))"
              :stroke-width="8"
              style="margin: 10px 0"
            />

            <!-- 强制要求：原文片段引用 -->
            <div class="quote-box">
              <span class="quote-label">📌 作业原文引用依据：</span>
              “{{ dim.evidence_quote }}”
            </div>

            <div class="rationale-text">
              <strong>评分理由：</strong>{{ dim.rationale }}
            </div>

            <div v-if="dim.dimension_suggestion" class="dim-suggestion">
              <strong>分项改进建议：</strong>{{ dim.dimension_suggestion }}
            </div>
          </div>

          <!-- 给学生的整体具体改进建议 -->
          <h4 class="section-subtitle" style="margin-top: 22px">
            给学生的具体可操作改进建议
          </h4>
          <ul class="suggestion-list">
            <li
              v-for="(sug, sIdx) in submission.improvement_suggestions"
              :key="sIdx"
            >
              {{ sug }}
            </li>
          </ul>
        </el-card>

        <!-- 尚未评分时的空状态 -->
        <el-card
          v-else-if="submission.status === 'submitted'"
          shadow="never"
          style="text-align: center; padding: 48px 20px"
        >
          <el-empty description="该作业已上传就绪，请点击右上角「执行 AI 评分」开始批改" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 抽屉：教师人工复核与手动修正 -->
    <el-drawer
      v-model="reviewDrawerVisible"
      title="教师端评分复核与手动修正"
      size="620px"
    >
      <el-form v-if="reviewForm" :model="reviewForm" label-position="top">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="最终核定总分 (0-100)">
              <el-input-number
                v-model="reviewForm.final_score"
                :min="0"
                :max="100"
                :step="0.5"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="14">
            <el-form-item label="核定认知层级 (SOLO / 布鲁姆)">
              <el-input v-model="reviewForm.cognitive_level" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="综合评语修正">
          <el-input
            v-model="reviewForm.overall_comment"
            type="textarea"
            :rows="3"
          />
        </el-form-item>

        <div
          v-for="(dim, idx) in reviewForm.dimension_scores"
          :key="idx"
          class="review-dim-item"
        >
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
            <strong>维度 {{ idx + 1 }}：{{ dim.dimension_name }}（满分 {{ dim.max_score }}）</strong>
            <el-input-number
              v-model="dim.score"
              :min="0"
              :max="dim.max_score"
              :step="0.5"
              size="small"
              @change="recalculateTotalScore"
            />
          </div>
          <el-input
            v-model="dim.evidence_quote"
            size="small"
            placeholder="引用的作业原文片段"
            style="margin-bottom: 6px"
          >
            <template #prepend>原文引用</template>
          </el-input>
          <el-input
            v-model="dim.rationale"
            type="textarea"
            :rows="2"
            placeholder="评分理由"
          />
        </div>

        <el-form-item label="教师手动修正原因备注" style="margin-top: 14px">
          <el-input
            v-model="reviewForm.teacher_adjustment_note"
            placeholder="例如：学生补充了实验原始记录表，在论据维度酌情加 3 分"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="reviewDrawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingReview" @click="submitTeacherReview">
          保存复核结果
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../../api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const evaluating = ref(false)
const clarifying = ref(false)
const savingReview = ref(false)

const submission = ref(null)
const rubrics = ref([])
const clarifyAnswers = ref([])
const supplementalText = ref('')

const reviewDrawerVisible = ref(false)
const reviewForm = ref(null)

const evalConfig = reactive({
  grading_mode: 'authoritative',
  rubric_id: null
})

const filteredRubrics = computed(() =>
  rubrics.value.filter((r) => r.mode === evalConfig.grading_mode)
)

onMounted(async () => {
  rubrics.value = await api.listRubrics()
  await loadDetail()
})

async function loadDetail() {
  loading.value = true
  try {
    const data = await api.getSubmissionDetail(route.params.id)
    submission.value = data
    evalConfig.grading_mode = data.grading_mode || 'authoritative'
    evalConfig.rubric_id = data.rubric_id
    clarifyAnswers.value = (data.clarification_questions || []).map(
      (_, idx) => data.clarification_answers?.[idx]?.answer || ''
    )
  } finally {
    loading.value = false
  }
}

function onModeChange() {
  const list = filteredRubrics.value
  evalConfig.rubric_id = list.length ? list[0].id : null
}

function statusText(status) {
  const map = {
    submitted: '待评分',
    needs_clarification: '待模糊澄清',
    graded: 'AI已评分',
    reviewed: '教师已复核'
  }
  return map[status] || status
}

function statusTagType(status) {
  const map = {
    submitted: 'info',
    needs_clarification: 'warning',
    graded: 'success',
    reviewed: 'primary'
  }
  return map[status] || 'info'
}

async function handleEvaluate(forceWithoutClarification = false) {
  evaluating.value = true
  try {
    const res = await api.evaluateSubmission(submission.value.id, {
      grading_mode: evalConfig.grading_mode,
      rubric_id: evalConfig.rubric_id,
      force_grade_without_clarification: forceWithoutClarification
    })
    submission.value = res
    if (res.status === 'needs_clarification') {
      clarifyAnswers.value = (res.clarification_questions || []).map(() => '')
      ElMessage.warning('检测到模糊疑问点，请先澄清后再打分')
    } else {
      ElMessage.success(`AI 评分完成，总分：${res.total_score} 分`)
    }
  } finally {
    evaluating.value = false
  }
}

async function handleSubmitClarification() {
  const questions = submission.value.clarification_questions || []
  const answersPayload = questions.map((q, idx) => ({
    id: q.id || `Q${idx + 1}`,
    question: q.question,
    answer: (clarifyAnswers.value[idx] || '').trim() || '按现有内容及标准正常评定'
  }))

  clarifying.value = true
  try {
    const res = await api.submitClarification(submission.value.id, {
      answers: answersPayload,
      supplemental_text: supplementalText.value
    })
    submission.value = res
    ElMessage.success(`澄清完毕并已完成评分！总分：${res.total_score} 分`)
  } finally {
    clarifying.value = false
  }
}

function openReviewDrawer() {
  reviewForm.value = JSON.parse(
    JSON.stringify({
      final_score: submission.value.final_score ?? submission.value.total_score ?? 85,
      cognitive_level: submission.value.cognitive_level || '',
      overall_comment: submission.value.overall_comment || '',
      dimension_scores: submission.value.dimension_scores || [],
      improvement_suggestions: submission.value.improvement_suggestions || [],
      teacher_adjustment_note: submission.value.teacher_adjustment_note || ''
    })
  )
  reviewDrawerVisible.value = true
}

function recalculateTotalScore() {
  if (!reviewForm.value) return
  const sum = reviewForm.value.dimension_scores.reduce(
    (acc, d) => acc + Number(d.score || 0),
    0
  )
  reviewForm.value.final_score = Number(sum.toFixed(1))
}

async function submitTeacherReview() {
  savingReview.value = true
  try {
    const res = await api.reviewSubmission(submission.value.id, reviewForm.value)
    submission.value = res
    reviewDrawerVisible.value = false
    ElMessage.success('教师人工复核结果已保存')
  } finally {
    savingReview.value = false
  }
}
</script>

<style scoped>
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.left-info,
.right-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.sub-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}
.card-header-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}
.prompt-box {
  background: #f8fafc;
  padding: 12px 14px;
  border-radius: 8px;
  border-left: 4px solid #3b82f6;
  color: #334155;
  line-height: 1.6;
  font-size: 14px;
}
.homework-text-box {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  padding: 16px;
  border-radius: 8px;
  white-space: pre-wrap;
  line-height: 1.8;
  color: #1e293b;
  font-size: 14px;
  max-height: 560px;
  overflow-y: auto;
}
.clarification-card {
  border: 2px solid #f59e0b;
  margin-bottom: 18px;
}
.clarification-header {
  color: #b45309;
  font-weight: 700;
  font-size: 15px;
}
.question-item {
  background: #fffbeb;
  border: 1px solid #fde68a;
  padding: 14px;
  border-radius: 8px;
  margin-bottom: 12px;
}
.q-title {
  font-weight: 600;
  color: #92400e;
  line-height: 1.5;
}
.q-excerpt {
  font-size: 12px;
  color: #b45309;
  margin-top: 6px;
  font-style: italic;
}
.score-banner {
  display: flex;
  gap: 20px;
  align-items: center;
  background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%);
  padding: 18px;
  border-radius: 10px;
  border: 1px solid #bfdbfe;
  margin-bottom: 20px;
}
.score-circle {
  min-width: 105px;
  height: 105px;
  border-radius: 50%;
  background: #1e3a8a;
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.score-circle .num {
  font-size: 30px;
  font-weight: 700;
}
.score-circle .total {
  font-size: 12px;
  opacity: 0.85;
}
.cog-badge {
  display: inline-block;
  background: #dbeafe;
  color: #1e40af;
  font-weight: 600;
  font-size: 13px;
  padding: 4px 10px;
  border-radius: 6px;
  margin-bottom: 8px;
}
.overall-comment {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.6;
}
.teacher-note {
  margin-top: 8px;
  font-size: 13px;
  color: #b45309;
  background: #fef3c7;
  padding: 6px 10px;
  border-radius: 6px;
}
.section-subtitle {
  margin: 0 0 12px 0;
  color: #0f172a;
  font-size: 15px;
  border-left: 4px solid #1e3a8a;
  padding-left: 10px;
}
.dim-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 14px;
  background: #fafafa;
}
.dim-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.dim-name {
  font-weight: 600;
  color: #0f172a;
}
.dim-score {
  font-size: 15px;
  color: #16a34a;
}
.quote-box {
  background: #eff6ff;
  border-left: 3px solid #2563eb;
  padding: 8px 12px;
  font-size: 13px;
  color: #1e3a8a;
  border-radius: 4px;
  margin: 8px 0;
  line-height: 1.5;
}
.quote-label {
  font-weight: 600;
}
.rationale-text {
  font-size: 13.5px;
  color: #334155;
  line-height: 1.6;
  margin-top: 6px;
}
.dim-suggestion {
  font-size: 13px;
  color: #0f766e;
  margin-top: 6px;
}
.suggestion-list {
  margin: 0;
  padding-left: 20px;
  color: #1e293b;
  line-height: 1.8;
  font-size: 14px;
}
.review-dim-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 12px;
}
</style>
