<template>
  <div>
    <!-- 顶部核心指标统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">全部提交作业</div>
          <div class="stat-value">{{ submissions.length }} <span class="unit">份</span></div>
          <div class="stat-sub">支持 TXT / 图片 / PDF / Word</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">已完成评分 / 复核</div>
          <div class="stat-value" style="color: #16a34a">
            {{ gradedCount }} <span class="unit">份</span>
          </div>
          <div class="stat-sub">含原文片段引用与改进建议</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">待模糊澄清确认</div>
          <div class="stat-value" style="color: #d97706">
            {{ clarificationCount }} <span class="unit">份</span>
          </div>
          <div class="stat-sub">内容或量规存疑，禁止臆测打分</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">班级已评平均分</div>
          <div class="stat-value" style="color: #2563eb">
            {{ averageScore }} <span class="unit">分</span>
          </div>
          <div class="stat-sub">满分 100 分制</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选与批量操作工具栏 -->
    <el-card shadow="never" style="margin-bottom: 20px">
      <div class="toolbar">
        <div class="filters">
          <el-input
            v-model="filters.keyword"
            placeholder="搜索学生姓名、学号或作业题目..."
            clearable
            prefix-icon="Search"
            style="width: 260px"
            @clear="loadData"
            @keyup.enter="loadData"
          />
          <el-select
            v-model="filters.status_filter"
            placeholder="全部评分状态"
            clearable
            style="width: 170px"
            @change="loadData"
          >
            <el-option label="待评分 (submitted)" value="submitted" />
            <el-option label="待模糊澄清 (needs_clarification)" value="needs_clarification" />
            <el-option label="AI已评分 (graded)" value="graded" />
            <el-option label="教师已复核 (reviewed)" value="reviewed" />
          </el-select>
          <el-button type="primary" plain icon="Refresh" @click="loadData">
            查询刷新
          </el-button>
        </div>

        <div class="actions">
          <el-button
            type="primary"
            icon="UploadFilled"
            @click="openSingleUpload"
          >
            上传单份作业
          </el-button>
          <el-button
            type="primary"
            plain
            icon="FolderAdd"
            @click="batchUploadVisible = true"
          >
            批量上传作业
          </el-button>
          <el-button
            type="warning"
            icon="MagicStick"
            :disabled="selectedRows.length === 0"
            :loading="batchGrading"
            @click="handleBatchEvaluate"
          >
            批量 AI 评分 ({{ selectedRows.length }})
          </el-button>
          <el-button
            type="success"
            icon="Download"
            @click="handleExportExcel"
          >
            导出 Excel 成绩单
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 作业列表表格 -->
    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="submissions"
        stripe
        border
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" align="center" />
        <el-table-column prop="id" label="ID" width="65" align="center" />
        <el-table-column label="学生信息" width="160">
          <template #default="{ row }">
            <div style="font-weight: 600">{{ row.student_name }}</div>
            <div style="font-size: 12px; color: #64748b">
              {{ row.student_no }} · {{ row.class_name || '默认班级' }}
            </div>
          </template>
        </el-table-column>

        <el-table-column label="作业题目与题型" min-width="240">
          <template #default="{ row }">
            <div style="font-weight: 600; color: #1e293b">
              {{ row.assignment_title }}
            </div>
            <div style="margin-top: 4px; display: flex; gap: 6px; align-items: center">
              <el-tag size="small" type="info">{{ row.question_type }}</el-tag>
              <el-tag size="small" effect="plain">
                格式: {{ row.submission_type.toUpperCase() }}
              </el-tag>
              <span v-if="row.file_name" style="font-size: 12px; color: #64748b">
                ({{ row.file_name }})
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="评分模式与匹配量规" width="220">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.grading_mode === 'authoritative' ? 'primary' : 'warning'"
            >
              {{ row.grading_mode === 'authoritative' ? '模式A：权威默认量规' : '模式B：自定义量规' }}
            </el-tag>
            <div style="font-size: 12px; color: #475569; margin-top: 4px">
              {{ row.matched_rubric_name || '自动匹配权威量规' }}
            </div>
          </template>
        </el-table-column>

        <el-table-column label="当前状态" width="145" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="dark">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="总分 / 认知水平" width="180" align="center">
          <template #default="{ row }">
            <div v-if="row.final_score !== null && row.final_score !== undefined">
              <span style="font-size: 20px; font-weight: 700; color: #16a34a">
                {{ row.final_score }}
              </span>
              <span style="font-size: 12px; color: #64748b"> / 100</span>
              <div
                v-if="row.cognitive_level"
                style="font-size: 12px; color: #334155; margin-top: 2px"
              >
                {{ row.cognitive_level.split('/')[0] }}
              </div>
            </div>
            <span v-else style="color: #94a3b8; font-size: 13px">暂未出分</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="goDetail(row.id)"
            >
              {{ row.status === 'needs_clarification' ? '去澄清疑问' : '详情与复核' }}
            </el-button>
            <el-button
              size="small"
              type="success"
              plain
              :loading="gradingId === row.id"
              @click="handleSingleEvaluate(row)"
            >
              AI 评分
            </el-button>
            <el-popconfirm
              title="确定要删除这份作业记录吗？"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 弹窗 1：上传单份作业 -->
    <el-dialog
      v-model="singleUploadVisible"
      title="上传单份学生作业（支持文本 / 图片 / PDF / Word）"
      width="650px"
    >
      <el-form :model="uploadForm" label-width="115px">
        <el-form-item label="选择提交学生" required>
          <el-select
            v-model="uploadForm.student_id"
            placeholder="请选择学生"
            style="width: 100%"
          >
            <el-option
              v-for="stu in students"
              :key="stu.id"
              :label="`${stu.full_name} (${stu.student_no} · ${stu.class_name || ''})`"
              :value="stu.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="作业题目名称" required>
          <el-input
            v-model="uploadForm.assignment_title"
            placeholder="例如：人工智能生成内容对基础教育评价范式的冲击与重构"
          />
        </el-form-item>

        <el-form-item label="作业题型" required>
          <el-select v-model="uploadForm.question_type" style="width: 100%">
            <el-option label="开放论述题（自动匹配 SOLO 五水平量规）" value="开放论述题" />
            <el-option label="案例分析与科学探究题（自动匹配布鲁姆六层级量规）" value="案例分析与科学探究题" />
            <el-option label="编程与算法题（自动匹配算法工程量规）" value="编程与算法题" />
          </el-select>
        </el-form-item>

        <el-form-item label="题目具体要求" required>
          <el-input
            v-model="uploadForm.question_prompt"
            type="textarea"
            :rows="3"
            placeholder="请输入题干材料与评分考察要求..."
          />
        </el-form-item>

        <el-form-item label="自动评分模式">
          <el-radio-group v-model="uploadForm.grading_mode">
            <el-radio value="authoritative">模式 A：权威默认量规（SOLO / 布鲁姆自动匹配）</el-radio>
            <el-radio value="custom">模式 B：指定已确认的自定义量规</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="uploadForm.grading_mode === 'custom'" label="选择自定义量规">
          <el-select
            v-model="uploadForm.rubric_id"
            placeholder="请选择自定义量规"
            style="width: 100%"
          >
            <el-option
              v-for="r in customRubrics"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="上传作业文件">
          <input
            type="file"
            accept=".txt,.md,.pdf,.docx,.png,.jpg,.jpeg,.webp"
            @change="onSingleFileChange"
          />
          <div style="font-size: 12px; color: #64748b; margin-top: 4px">
            支持 .txt / .docx / .pdf / .png / .jpg / .webp（图片与扫描版 PDF 将调用 Gemini 多模态原生识别）
          </div>
        </el-form-item>

        <el-form-item label="或输入作业文本">
          <el-input
            v-model="uploadForm.text_content"
            type="textarea"
            :rows="5"
            placeholder="可直接粘贴学生作答文本（若同时上传文件，系统将自动合并解析）..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="singleUploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitSingleUpload">
          确认上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 弹窗 2：批量上传多份作业文件 -->
    <el-dialog
      v-model="batchUploadVisible"
      title="批量上传学生作业（支持多文件同时导入）"
      width="620px"
    >
      <el-form :model="batchForm" label-width="115px">
        <el-form-item label="统一作业题目" required>
          <el-input
            v-model="batchForm.assignment_title"
            placeholder="请输入本次批量导入的作业题目"
          />
        </el-form-item>
        <el-form-item label="作业题型" required>
          <el-select v-model="batchForm.question_type" style="width: 100%">
            <el-option label="开放论述题（匹配 SOLO 量规）" value="开放论述题" />
            <el-option label="案例分析与科学探究题（匹配布鲁姆量规）" value="案例分析与科学探究题" />
            <el-option label="编程与算法题（匹配程序设计量规）" value="编程与算法题" />
          </el-select>
        </el-form-item>
        <el-form-item label="题目要求说明" required>
          <el-input
            v-model="batchForm.question_prompt"
            type="textarea"
            :rows="3"
          />
        </el-form-item>
        <el-form-item label="选择多个文件" required>
          <input
            type="file"
            multiple
            accept=".txt,.md,.pdf,.docx,.png,.jpg,.jpeg,.webp"
            @change="onBatchFilesChange"
          />
          <div style="font-size: 12px; color: #64748b; margin-top: 6px">
            提示：建议文件名包含学号或学生姓名（如 <code>2026001_林知夏_作业.docx</code>），系统会自动归档至对应学生名下。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchUploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitBatchUpload">
          开始批量导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../../api'

const router = useRouter()
const loading = ref(false)
const uploading = ref(false)
const batchGrading = ref(false)
const gradingId = ref(null)

const submissions = ref([])
const students = ref([])
const rubrics = ref([])
const selectedRows = ref([])

const filters = reactive({
  keyword: '',
  status_filter: ''
})

const singleUploadVisible = ref(false)
const batchUploadVisible = ref(false)
const singleFile = ref(null)
const batchFiles = ref([])

const uploadForm = reactive({
  student_id: null,
  assignment_title: '人工智能生成内容 (AIGC) 对基础教育评价范式的冲击与重构',
  question_type: '开放论述题',
  question_prompt:
    '请结合教育学原理与实际教学情境，论述生成式人工智能对传统作业评价带来的挑战，并提出具有可行性的过程性评价改革方案。',
  grading_mode: 'authoritative',
  rubric_id: null,
  text_content: ''
})

const batchForm = reactive({
  assignment_title: '人工智能生成内容 (AIGC) 对基础教育评价范式的冲击与重构',
  question_type: '开放论述题',
  question_prompt:
    '请结合教育学原理与实际教学情境，论述生成式人工智能对传统作业评价带来的挑战，并提出具有可行性的过程性评价改革方案。',
  grading_mode: 'authoritative'
})

const customRubrics = computed(() =>
  rubrics.value.filter((r) => r.mode === 'custom')
)

const gradedCount = computed(
  () =>
    submissions.value.filter((s) =>
      ['graded', 'reviewed'].includes(s.status)
    ).length
)

const clarificationCount = computed(
  () =>
    submissions.value.filter((s) => s.status === 'needs_clarification').length
)

const averageScore = computed(() => {
  const scored = submissions.value.filter(
    (s) => s.final_score !== null && s.final_score !== undefined
  )
  if (!scored.length) return '0.0'
  const sum = scored.reduce((acc, cur) => acc + Number(cur.final_score), 0)
  return (sum / scored.length).toFixed(1)
})

onMounted(() => {
  loadData()
  loadMeta()
})

async function loadData() {
  loading.value = true
  try {
    submissions.value = await api.listSubmissions({
      keyword: filters.keyword || undefined,
      status_filter: filters.status_filter || undefined
    })
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  students.value = await api.listStudents()
  rubrics.value = await api.listRubrics()
  if (students.value.length && !uploadForm.student_id) {
    uploadForm.student_id = students.value[0].id
  }
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

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

function goDetail(id) {
  router.push(`/teacher/submissions/${id}`)
}

function openSingleUpload() {
  singleFile.value = null
  uploadForm.text_content = ''
  singleUploadVisible.value = true
}

function onSingleFileChange(e) {
  const files = e.target.files
  singleFile.value = files && files.length ? files[0] : null
}

function onBatchFilesChange(e) {
  batchFiles.value = Array.from(e.target.files || [])
}

async function submitSingleUpload() {
  if (!uploadForm.assignment_title || !uploadForm.question_prompt) {
    ElMessage.warning('请填写作业题目与具体要求')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('assignment_title', uploadForm.assignment_title)
    fd.append('question_prompt', uploadForm.question_prompt)
    fd.append('question_type', uploadForm.question_type)
    if (uploadForm.student_id) fd.append('student_id', uploadForm.student_id)
    fd.append('grading_mode', uploadForm.grading_mode)
    if (uploadForm.rubric_id) fd.append('rubric_id', uploadForm.rubric_id)
    if (uploadForm.text_content) fd.append('text_content', uploadForm.text_content)
    if (singleFile.value) fd.append('file', singleFile.value)

    const created = await api.uploadSubmission(fd)
    ElMessage.success(`作业上传成功（学生：${created.student_name}）`)
    singleUploadVisible.value = false
    await loadData()
  } finally {
    uploading.value = false
  }
}

async function submitBatchUpload() {
  if (!batchFiles.value.length) {
    ElMessage.warning('请先选择要批量上传的作业文件')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('assignment_title', batchForm.assignment_title)
    fd.append('question_prompt', batchForm.question_prompt)
    fd.append('question_type', batchForm.question_type)
    fd.append('grading_mode', batchForm.grading_mode)
    batchFiles.value.forEach((f) => fd.append('files', f))

    const res = await api.batchUploadSubmissions(fd)
    ElMessage.success(`成功批量上传 ${res.length} 份作业！`)
    batchUploadVisible.value = false
    await loadData()
  } finally {
    uploading.value = false
  }
}

async function handleSingleEvaluate(row) {
  gradingId.value = row.id
  try {
    const res = await api.evaluateSubmission(row.id, {
      grading_mode: row.grading_mode || 'authoritative',
      rubric_id: row.rubric_id
    })
    if (res.status === 'needs_clarification') {
      ElMessage.warning(
        `作业 #${row.id} 检测到模糊疑问点，已暂停盲目打分，请进入详情页澄清！`
      )
      router.push(`/teacher/submissions/${row.id}`)
    } else {
      ElMessage.success(`作业 #${row.id} 评分完成：${res.total_score} 分`)
      await loadData()
    }
  } finally {
    gradingId.value = null
  }
}

async function handleBatchEvaluate() {
  const ids = selectedRows.value.map((r) => r.id)
  if (!ids.length) return
  batchGrading.value = true
  try {
    const res = await api.batchEvaluateSubmissions({
      submission_ids: ids,
      grading_mode: 'authoritative'
    })
    ElMessage.success(res.message)
    await loadData()
  } finally {
    batchGrading.value = false
  }
}

async function handleDelete(id) {
  await api.deleteSubmission(id)
  ElMessage.success('作业记录已删除')
  await loadData()
}

async function handleExportExcel() {
  try {
    await api.exportExcel(filters.status_filter)
    ElMessage.success('Excel 成绩单已生成并开始下载')
  } catch {
    ElMessage.error('导出 Excel 失败')
  }
}
</script>

<style scoped>
.stat-card {
  border-radius: 10px;
}
.stat-label {
  font-size: 13px;
  color: #64748b;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  margin: 6px 0;
  color: #0f172a;
}
.stat-value .unit {
  font-size: 14px;
  font-weight: 400;
}
.stat-sub {
  font-size: 12px;
  color: #94a3b8;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.filters,
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
