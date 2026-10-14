<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 20px">
      <div class="header-bar">
        <div style="display: flex; gap: 12px; align-items: center">
          <el-input
            v-model="keyword"
            placeholder="按学生姓名、学号或班级搜索..."
            clearable
            prefix-icon="Search"
            style="width: 280px"
            @clear="loadStudents"
            @keyup.enter="loadStudents"
          />
          <el-button type="primary" plain @click="loadStudents">查询</el-button>
        </div>
        <el-button type="primary" icon="Plus" @click="openCreateDialog">
          新增学生档案
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="students" border stripe>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="student_no" label="学号（登录账号）" width="160" />
        <el-table-column prop="full_name" label="学生姓名" width="160" />
        <el-table-column prop="class_name" label="所属班级" width="220" />
        <el-table-column prop="email" label="联系邮箱" min-width="200" />
        <el-table-column label="账号状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '正常启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openEditDialog(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定要删除该学生账号吗？"
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

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑学生信息' : '新增学生档案'"
      width="480px"
    >
      <el-form :model="form" label-width="95px">
        <el-form-item label="学号" required>
          <el-input v-model="form.student_no" placeholder="如 2026004（同时作为学生登录名）" />
        </el-form-item>
        <el-form-item label="学生姓名" required>
          <el-input v-model="form.full_name" placeholder="请输入学生姓名" />
        </el-form-item>
        <el-form-item label="所属班级">
          <el-input v-model="form.class_name" placeholder="如 高二(1)班 创新实验班" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="可选：student@edu.cn" />
        </el-form-item>
        <el-form-item v-if="!editingId" label="初始密码">
          <el-input v-model="form.password" placeholder="默认 123456" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../api'

const students = ref([])
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref(null)

const form = reactive({
  student_no: '',
  full_name: '',
  class_name: '高二(1)班 创新实验班',
  email: '',
  password: '123456'
})

onMounted(() => {
  loadStudents()
})

async function loadStudents() {
  students.value = await api.listStudents(keyword.value)
}

function openCreateDialog() {
  editingId.value = null
  form.student_no = ''
  form.full_name = ''
  form.class_name = '高二(1)班 创新实验班'
  form.email = ''
  form.password = '123456'
  dialogVisible.value = true
}

function openEditDialog(row) {
  editingId.value = row.id
  form.student_no = row.student_no
  form.full_name = row.full_name
  form.class_name = row.class_name || ''
  form.email = row.email || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.student_no || !form.full_name) {
    ElMessage.warning('请填写学号与学生姓名')
    return
  }
  if (editingId.value) {
    await api.updateStudent(editingId.value, form)
    ElMessage.success('学生信息已更新')
  } else {
    await api.createStudent(form)
    ElMessage.success('新学生档案已创建')
  }
  dialogVisible.value = false
  await loadStudents()
}

async function handleDelete(id) {
  await api.deleteStudent(id)
  ElMessage.success('已删除该学生记录')
  await loadStudents()
}
</script>

<style scoped>
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
