<template>
  <div>
    <!-- 学生个人信息与提交新作业入口 -->
    <el-card shadow="never" style="margin-bottom: 20px">
      <div class="stu-header">
        <div>
          <h3 style="margin: 0 0 6px 0; color: #0f172a">
            欢迎你，{{ authStore.user?.full_name }}（学号：{{ authStore.user?.student_no || authStore.user?.username }}）
          </h3>
          <div style="font-size: 13px; color: #64748b">
            班级：{{ authStore.user?.class_name || '高二(1)班' }} · 在此提交课后作业并查看基于 SOLO / 布鲁姆量规的分维度诊断报告与改进建议
          </div>
        </div>
        <el-button
          type="primary"
          size="large"
          icon="UploadFilled"
          @click="uploadVisible = true"
        >
          提交新作业
        </el-button>
      </div>
    </el-card>

    <el-row :gutter="20">
      <!-- 左侧：我的作业提交记录列表 -->
      <el-col :span="9">
        <el-card shadow="never">
          <template #header>
            <div style="font-weight: 600">我的作业列表 ({{ mySubmissions.length }})</div>
          </template>

          <el-empty v-if="mySubmissions.length === 0" description="暂无作业提交记录" />

          <div
            v-for="item in mySubmissions"
            :key="item.id"
            class="sub-list-item"
            :class="{ active: activeSubmission?.id === item.id }"
            @click="selectSubmission(item)"
          >
            <div class="item-top">
              <span class="item-title">{{ item.assignment_title }}</span>
              <el-tag size="small" :type="statusTagType(item.status)">
                {{ statusText(item.status) }}
              </el-tag>
            </div>
            <div class="item-meta">
              <span>题型：{{ item.question_type }}</span>
              <span v-if="item.final_score !== null && item.final_score !== undefined" class="item-score">
                得分：<strong>{{ item.final_score }}</strong> / 100
              </span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：选中作业的评分结果、原文引用与改进建议详情 -->
      <el-col :span="15">
        <el-card v-if="activeSubmission" shadow="never">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 700; font-size: 16px">
                {{ activeSubmission.assignment_title }} — 诊断反馈详情
              </span>
              <el-tag size="small" effect="plain">
                匹配量规：{{ activeSubmission.matched_rubric_name }}
              </el-tag>
            </div>
          </template>

          <!-- 若处于待模糊澄清状态，允许学生直接补充说明 -->
          <div
            v-if="activeSubmission.status === 'needs_clarification'"
            class="stu-clarify-box"
          >
            <el-alert
              title="提示：系统检测到你提交的作业存在以下需要补充澄清的地方（澄清后将立即生成评分报告）："
              type="warning"
              :closable="false"
              show-icon
              style="margin-bottom: 12px"
            />
            <div
              v-for="(q, idx) in activeSubmission.clarification_questions"
              :key="idx"
              style="margin-bottom: 12px"
            >
              <div style="font-weight: 600; color: #92400e; margin-bottom: 6px">
                {{ q.id }} ({{ q.category }})：{{ q.question }}
              </div>
              <el-input
                v-model="stuClarifyAnswers[idx]"
                type="textarea"
                :rows="2"
                placeholder="请在此输入补充说明..."
              />
            </div>
            <el-button
              type="primary"
              :loading="submittingClarify"
              @click="handleStudentClarify"
            >
              提交补充说明并获取评分
            </el-button>
          </div>

          <!-- 已出分：展示总分、认知层级、分维度原文引用与改进建议 -->
          <div v-if="activeSubmission.dimension_scores && activeSubmission.dimension_scores.length">
            <div class="stu-score-header">
              <div class="big-score">
                {{ activeSubmission.final_score ?? activeSubmission.total_score }}
                <span>分</span>
              </div>
              <div style="flex: 1">
                <el-tag type="primary" effect="dark" style="margin-bottom: 8px">
                  {{ activeSubmission.cognitive_level }}
                </el-tag>
                <div style="font-size: 14px; color: #1e293b; line-height: 1.6">
                  {{ activeSubmission.overall_comment }}
                </div>
              </div>
            </div>

            <h4 class="sec-title">一、各维度分项得分与作业原文引用依据</h4>
            <div
              v-for="(dim, idx) in activeSubmission.dimension_scores"
              :key="idx"
              class="stu-dim-card"
            >
              <div style="display: flex; justify-content: space-between; align-items: center">
                <div>
                  <strong>{{ idx + 1 }}. {{ dim.dimension_name }}</strong>
                  <el-tag size="small" type="success" style="margin-left: 8px">
                    {{ dim.level_reached }}
                  </el-tag>
                </div>
                <span style="font-weight: 700; color: #16a34a">
                  {{ dim.score }} / {{ dim.max_score }} 分
                </span>
              </div>
              <div class="stu-quote">
                <strong>引用的你的作业原文：</strong>“{{ dim.evidence_quote }}”
              </div>
              <div style="font-size: 13.5px; color: #334155; line-height: 1.6">
                <strong>评价解析：</strong>{{ dim.rationale }}
              </div>
              <div
                v-if="dim.dimension_suggestion"
                style="font-size: 13px; color: #0f766e; margin-top: 4px"
              >
                <strong>提升贴士：</strong>{{ dim.dimension_suggestion }}
              </div>
            </div>

            <h4 class="sec-title" style="margin-top: 20px">
              二、针对性改进建议（下一步行动指南）
            </h4>
            <ul class="stu-suggestions">
              <li
                v-for="(s, sIdx) in activeSubmission.improvement_suggestions"
                :key="sIdx"
              >
                {{ s }}
              </li>
            </ul>
          </div>

          <!-- 待评分提示 -->
          <el-empty
            v-else-if="activeSubmission.status === 'submitted'"
            description="你的作业已成功上传，等待教师端触发批改或复核"
          />

          <el-divider />
          <h4 class="sec-title">我提交的作业正文</h4>
          <div class="my-raw-text">{{ activeSubmission.extracted_text }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 学生提交新作业弹窗 -->
    <el-dialog v-model="uploadVisible" title="提交新作业" width="600px">
      <el-form :model="form" label-width="105px">
        <el-form-item label="作业题目" required>
          <el-input v-model="form.assignment_title" />
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="form.question_type" style="width: 100%">
            <el-option label="开放论述题" value="开放论述题" />
            <el-option label="案例分析与科学探究题" value="案例分析与科学探究题" />
            <el-option label="编程与算法题" value="编程与算法题" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目要求" required>
          <el-input v-model="form.question_prompt" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="上传作业文件">
          <input
            type="file"
            accept=".txt,.md,.pdf,.docx,.png,.jpg,.jpeg,.webp"
            @change="onFileChange"
          />
        </el-form-item>
        <el-form-item label="或输入正文">
          <el-input
            v-model="form.text_content"
            type="textarea"
            :rows="5"
            placeholder="在此输入你的作业作答内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          确认提交
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/auth'
import { api } from '../../api'

const authStore = useAuthStore()
const mySubmissions = ref([])
const activeSubmission = ref(null)
const stuClarifyAnswers = ref([])
const submittingClarify = ref(false)

const uploadVisible = ref(false)
const uploading = ref(false)
const selectedFile = ref(null)

const form = reactive({
  assignment_title: '人工智能生成内容 (AIGC) 对基础教育评价范式的冲击与重构',
  question_type: '开放论述题',
  question_prompt:
    '请结合教育学原理与实际教学情境，论述生成式人工智能对传统作业评价带来的挑战，并提出具有可行性的过程性评价改革方案。',
  text_content: ''
})

onMounted(() => {
  loadMySubmissions()
})

async function loadMySubmissions() {
  const list = await api.listSubmissions()
  mySubmissions.value = list
  if (list.length) {
    selectSubmission(list[0])
  }
}

function selectSubmission(item) {
  activeSubmission.value = item
  stuClarifyAnswers.value = (item.clarification_questions || []).map(() => '')
}

function statusText(status) {
  const map = {
    submitted: '已提交待批改',
    needs_clarification: '待补充澄清',
    graded: '已出分',
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

function onFileChange(e) {
  const files = e.target.files
  selectedFile.value = files && files.length ? files[0] : null
}

async function handleUpload() {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('assignment_title', form.assignment_title)
    fd.append('question_prompt', form.question_prompt)
    fd.append('question_type', form.question_type)
    if (form.text_content) fd.append('text_content', form.text_content)
    if (selectedFile.value) fd.append('file', selectedFile.value)

    await api.uploadSubmission(fd)
    ElMessage.success('作业提交成功！')
    uploadVisible.value = false
    await loadMySubmissions()
  } finally {
    uploading.value = false
  }
}

async function handleStudentClarify() {
  if (!activeSubmission.value) return
  const questions = activeSubmission.value.clarification_questions || []
  const answers = questions.map((q, idx) => ({
    id: q.id || `Q${idx + 1}`,
    question: q.question,
    answer: (stuClarifyAnswers.value[idx] || '').trim() || '已确认并补充说明'
  }))
  submittingClarify.value = true
  try {
    const updated = await api.submitClarification(activeSubmission.value.id, {
      answers,
      supplemental_text: answers.map((a) => a.answer).join('；')
    })
    activeSubmission.value = updated
    await loadMySubmissions()
    ElMessage.success('补充澄清已提交，系统已完成评分！')
  } finally {
    submittingClarify.value = false
  }
}
</script>

<style scoped>
.stu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sub-list-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.sub-list-item:hover,
.sub-list-item.active {
  border-color: #2563eb;
  background: #eff6ff;
}
.item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.item-title {
  font-weight: 600;
  color: #0f172a;
  font-size: 14px;
}
.item-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
}
.item-score {
  color: #16a34a;
}
.stu-clarify-box {
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 18px;
}
.stu-score-header {
  display: flex;
  gap: 18px;
  align-items: center;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  padding: 16px;
  border-radius: 10px;
  margin-bottom: 18px;
}
.big-score {
  font-size: 36px;
  font-weight: 800;
  color: #15803d;
  min-width: 100px;
  text-align: center;
}
.big-score span {
  font-size: 14px;
  font-weight: 400;
}
.sec-title {
  margin: 0 0 12px 0;
  font-size: 15px;
  color: #0f172a;
  border-left: 4px solid #2563eb;
  padding-left: 10px;
}
.stu-dim-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #fafafa;
}
.stu-quote {
  background: #eff6ff;
  color: #1e3a8a;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
  margin: 8px 0;
}
.stu-suggestions {
  padding-left: 20px;
  line-height: 1.8;
  color: #1e293b;
  font-size: 14px;
}
.my-raw-text {
  background: #f8fafc;
  padding: 14px;
  border-radius: 8px;
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 13.5px;
  color: #334155;
}
</style>
