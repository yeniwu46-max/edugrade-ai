<template>
  <div>
    <!-- 顶部说明与操作区 -->
    <el-card shadow="never" style="margin-bottom: 20px">
      <div class="header-bar">
        <div>
          <h3 style="margin: 0 0 6px 0; color: #0f172a">
            双模式评分量规库（模式 A 权威默认量规 & 模式 B 自定义量规学习）
          </h3>
          <div style="font-size: 13px; color: #64748b">
            模式 A 内置 SOLO 五水平与布鲁姆分类法；模式 B 支持上传 PDF / Word / 纯文本量规文档，经 AI 解析出维度与权重并由教师确认后启用。
          </div>
        </div>
        <el-button
          type="primary"
          size="large"
          icon="Upload"
          @click="openParseDialog"
        >
          上传并解析自定义量规 (模式 B)
        </el-button>
      </div>
    </el-card>

    <!-- 量规分类标签页 -->
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="模式 A：内置权威默认量规 (SOLO / 布鲁姆)" name="authoritative">
        <el-row :gutter="18">
          <el-col
            v-for="rubric in authoritativeRubrics"
            :key="rubric.id"
            :span="24"
            style="margin-bottom: 18px"
          >
            <el-card shadow="hover">
              <div class="rubric-card-header">
                <div>
                  <span class="rubric-title">{{ rubric.name }}</span>
                  <el-tag size="small" type="primary" style="margin-left: 10px">
                    框架: {{ rubric.framework_type }}
                  </el-tag>
                  <el-tag size="small" type="success" style="margin-left: 6px">
                    适用题型: {{ rubric.question_type }}
                  </el-tag>
                </div>
                <el-tag effect="plain">总分 {{ rubric.total_points }} 分</el-tag>
              </div>
              <p class="rubric-desc">{{ rubric.description }}</p>

              <el-table :data="rubric.dimensions" border size="small">
                <el-table-column prop="name" label="评价维度名称" width="230" />
                <el-table-column prop="weight" label="权重 (%)" width="95" align="center" />
                <el-table-column prop="max_score" label="满分" width="85" align="center" />
                <el-table-column prop="description" label="考察重点" width="240" />
                <el-table-column label="各水平等级描述 (SOLO 五水平 / 布鲁姆层级)">
                  <template #default="{ row }">
                    <div
                      v-for="(lv, idx) in row.levels"
                      :key="idx"
                      class="level-line"
                    >
                      <el-tag size="small" effect="plain" style="margin-right: 6px">
                        {{ lv.level_name }} ({{ lv.score_range }})
                      </el-tag>
                      <span>{{ lv.description }}</span>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="模式 B：已确认的自定义学习量规" name="custom">
        <el-empty
          v-if="customRubrics.length === 0"
          description="暂未添加自定义量规，请点击右上角「上传并解析自定义量规」体验模式 B"
        />
        <el-row v-else :gutter="18">
          <el-col
            v-for="rubric in customRubrics"
            :key="rubric.id"
            :span="24"
            style="margin-bottom: 18px"
          >
            <el-card shadow="hover">
              <div class="rubric-card-header">
                <div>
                  <span class="rubric-title">{{ rubric.name }}</span>
                  <el-tag size="small" type="warning" style="margin-left: 10px">
                    自定义解析量规
                  </el-tag>
                  <el-tag size="small" type="info" style="margin-left: 6px">
                    适用题型: {{ rubric.question_type }}
                  </el-tag>
                  <el-tag
                    v-if="rubric.source_filename"
                    size="small"
                    effect="plain"
                    style="margin-left: 6px"
                  >
                    来源: {{ rubric.source_filename }}
                  </el-tag>
                </div>
                <div>
                  <el-popconfirm
                    title="确定要删除该自定义量规吗？"
                    @confirm="handleDeleteRubric(rubric.id)"
                  >
                    <template #reference>
                      <el-button size="small" type="danger" plain>删除</el-button>
                    </template>
                  </el-popconfirm>
                </div>
              </div>
              <p class="rubric-desc">{{ rubric.description }}</p>

              <el-table :data="rubric.dimensions" border size="small">
                <el-table-column prop="name" label="评价维度名称" width="220" />
                <el-table-column prop="weight" label="权重 (%)" width="95" align="center" />
                <el-table-column prop="max_score" label="满分" width="85" align="center" />
                <el-table-column prop="description" label="考察重点" width="240" />
                <el-table-column label="等级划分标准">
                  <template #default="{ row }">
                    <div
                      v-for="(lv, idx) in row.levels"
                      :key="idx"
                      class="level-line"
                    >
                      <el-tag size="small" type="warning" effect="plain" style="margin-right: 6px">
                        {{ lv.level_name }} ({{ lv.score_range }})
                      </el-tag>
                      <span>{{ lv.description }}</span>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <!-- 弹窗：模式 B 自定义量规上传 -> AI 解析 -> 用户核对确认 -->
    <el-dialog
      v-model="parseDialogVisible"
      title="模式 B「自定义量规学习」：文档解析与人工确认"
      width="820px"
    >
      <el-steps :active="stepIndex" finish-status="success" simple style="margin-bottom: 18px">
        <el-step title="1. 上传量规文档或粘贴文本" />
        <el-step title="2. 核对并确认 AI 解析出的维度与权重" />
      </el-steps>

      <!-- 第一步：上传文件或输入量规描述 -->
      <div v-if="stepIndex === 0">
        <el-form label-position="top">
          <el-form-item label="方式一：上传量规文档（支持 PDF / Word .docx / 纯文本 .txt）">
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              @change="onRubricFileChange"
            />
          </el-form-item>

          <el-form-item label="方式二：直接粘贴或编辑量规评分标准文本（可点击下方示例一键填充）">
            <div style="margin-bottom: 8px">
              <el-button size="small" type="primary" plain @click="fillSampleRubric">
                一键填充示例：高中历史史料实证论述题评分量规
              </el-button>
            </div>
            <el-input
              v-model="rawRubricText"
              type="textarea"
              :rows="8"
              placeholder="请粘贴量规文本，包含评价维度、分值/权重以及各等级要求..."
            />
          </el-form-item>
        </el-form>
      </div>

      <!-- 第二步：展示 AI 解析出的结构化结果供用户核对与修改 -->
      <div v-else-if="parsedRubric">
        <el-alert
          title="请核对 AI 解析出的评分维度、权重及等级描述。您可以直接修改任意字段，确认无误后点击下方「确认无误并保存启用」。"
          type="success"
          :closable="false"
          show-icon
          style="margin-bottom: 14px"
        />

        <el-form :model="parsedRubric" label-width="100px">
          <el-row :gutter="16">
            <el-col :span="14">
              <el-form-item label="量规名称">
                <el-input v-model="parsedRubric.name" />
              </el-form-item>
            </el-col>
            <el-col :span="10">
              <el-form-item label="适用题型">
                <el-input v-model="parsedRubric.question_type" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="整体说明">
            <el-input v-model="parsedRubric.description" />
          </el-form-item>
        </el-form>

        <div
          v-for="(dim, dIdx) in parsedRubric.dimensions"
          :key="dIdx"
          class="parsed-dim-box"
        >
          <div class="parsed-dim-header">
            <el-input
              v-model="dim.name"
              style="width: 260px"
              placeholder="维度名称"
            >
              <template #prepend>维度 {{ dIdx + 1 }}</template>
            </el-input>
            <div>
              <span>权重/满分：</span>
              <el-input-number
                v-model="dim.weight"
                :min="5"
                :max="100"
                size="small"
                @change="(val) => (dim.max_score = val)"
              />
              <el-button
                size="small"
                type="danger"
                text
                style="margin-left: 8px"
                @click="removeDimension(dIdx)"
              >
                移除
              </el-button>
            </div>
          </div>
          <el-input
            v-model="dim.description"
            size="small"
            placeholder="维度考察重点描述"
            style="margin: 8px 0"
          />
          <div
            v-for="(lv, lIdx) in dim.levels"
            :key="lIdx"
            style="display: flex; gap: 8px; margin-top: 6px"
          >
            <el-input v-model="lv.level_name" size="small" style="width: 170px" />
            <el-input v-model="lv.score_range" size="small" style="width: 110px" />
            <el-input v-model="lv.description" size="small" style="flex: 1" />
          </div>
        </div>

        <el-button
          size="small"
          type="primary"
          plain
          icon="Plus"
          @click="addDimension"
        >
          新增评分维度
        </el-button>
      </div>

      <template #footer>
        <el-button @click="parseDialogVisible = false">取消</el-button>
        <el-button v-if="stepIndex === 1" @click="stepIndex = 0">
          返回上一步重新解析
        </el-button>
        <el-button
          v-if="stepIndex === 0"
          type="primary"
          :loading="parsing"
          @click="handleParseRubric"
        >
          使用 LLM 解析量规结构
        </el-button>
        <el-button
          v-else
          type="success"
          :loading="saving"
          @click="handleConfirmRubric"
        >
          确认无误并保存启用
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../api'

const activeTab = ref('authoritative')
const rubrics = ref([])

const parseDialogVisible = ref(false)
const stepIndex = ref(0)
const parsing = ref(false)
const saving = ref(false)

const rubricFile = ref(null)
const rawRubricText = ref('')
const parsedRubric = ref(null)
const parsedSourceFilename = ref('')

const authoritativeRubrics = computed(() =>
  rubrics.value.filter((r) => r.mode === 'authoritative')
)
const customRubrics = computed(() =>
  rubrics.value.filter((r) => r.mode === 'custom')
)

onMounted(() => {
  loadRubrics()
})

async function loadRubrics() {
  rubrics.value = await api.listRubrics()
}

function openParseDialog() {
  stepIndex.value = 0
  rubricFile.value = null
  rawRubricText.value = ''
  parsedRubric.value = null
  parseDialogVisible.value = true
}

function onRubricFileChange(e) {
  const files = e.target.files
  rubricFile.value = files && files.length ? files[0] : null
}

function fillSampleRubric() {
  rawRubricText.value = `高中历史《史料实证与历史解释》专题论述评分量规
一、核心观点与时空定位准确度(35%)：能够在特定历史时空框架下准确提炼核心论点，史实无硬伤。
二、一手与二手史料互证严密性(40%)：能结合至少两则不同来源史料进行交叉印证，揭示材料背后的因果联系。
三、历史思辨深度与学术表达规范(25%)：能够辩证评析历史事件的多重影响，语言严谨、史论结合。`
}

async function handleParseRubric() {
  if (!rubricFile.value && !rawRubricText.value.trim()) {
    ElMessage.warning('请上传量规文件或输入量规文本')
    return
  }
  parsing.value = true
  try {
    const fd = new FormData()
    if (rubricFile.value) fd.append('file', rubricFile.value)
    if (rawRubricText.value.trim()) fd.append('raw_text', rawRubricText.value.trim())

    const res = await api.parseCustomRubric(fd)
    parsedRubric.value = res.parsed_rubric
    parsedSourceFilename.value = res.source_filename
    stepIndex.value = 1
    ElMessage.success('AI 已成功解析出评分维度与等级描述，请核对确认')
  } finally {
    parsing.value = false
  }
}

function addDimension() {
  if (!parsedRubric.value) return
  parsedRubric.value.dimensions.push({
    name: '新增评价维度',
    weight: 20,
    max_score: 20,
    description: '请输入该维度的考察重点',
    levels: [
      {
        level_name: '优秀 (A)',
        score_range: '17-20分',
        min_ratio: 0.85,
        max_ratio: 1.0,
        description: '完全达成该维度高阶标准'
      },
      {
        level_name: '良好/及格 (B/C)',
        score_range: '0-16.5分',
        min_ratio: 0.0,
        max_ratio: 0.84,
        description: '基础达成或有待改进'
      }
    ]
  })
}

function removeDimension(idx) {
  parsedRubric.value.dimensions.splice(idx, 1)
}

async function handleConfirmRubric() {
  saving.value = true
  try {
    await api.confirmCustomRubric({
      ...parsedRubric.value,
      source_filename: parsedSourceFilename.value,
      raw_source_text: rawRubricText.value
    })
    ElMessage.success('自定义量规已确认并正式启用！')
    parseDialogVisible.value = false
    activeTab.value = 'custom'
    await loadRubrics()
  } finally {
    saving.value = false
  }
}

async function handleDeleteRubric(id) {
  await api.deleteRubric(id)
  ElMessage.success('自定义量规已删除')
  await loadRubrics()
}
</script>

<style scoped>
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.rubric-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.rubric-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.rubric-desc {
  font-size: 13px;
  color: #475569;
  margin: 10px 0 14px 0;
}
.level-line {
  margin-bottom: 6px;
  font-size: 12.5px;
  color: #334155;
  line-height: 1.5;
}
.parsed-dim-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.parsed-dim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
