<template>
  <div class="login-wrapper">
    <el-card class="login-card" shadow="always">
      <div class="login-header">
        <div class="brand-pill">EduGrade AI</div>
        <h2>教学作业上传与自动评分系统</h2>
        <p class="subtitle">
          内置 SOLO 五水平 & 布鲁姆分类权威量规 · 自定义量规学习 · 多模态识图 · 模糊澄清机制
        </p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="登录账号（教师账号 / 学生学号）" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入账号，如 teacher 或 2026001"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item label="登录密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码（默认 123456）"
            prefix-icon="Lock"
            size="large"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          style="width: 100%; margin-top: 8px; font-weight: 600"
          @click="handleLogin"
        >
          立即登录系统
        </el-button>
      </el-form>

      <div class="quick-demo-box">
        <div class="quick-title">本地演示快捷填充（点击即可一键登录）：</div>
        <div class="quick-btns">
          <el-button
            size="small"
            type="primary"
            plain
            @click="quickFill('teacher', '123456')"
          >
            教师端：张明远 (teacher)
          </el-button>
          <el-button
            size="small"
            type="success"
            plain
            @click="quickFill('2026001', '123456')"
          >
            学生端：林知夏 (2026001-已评分)
          </el-button>
          <el-button
            size="small"
            type="warning"
            plain
            @click="quickFill('2026002', '123456')"
          >
            学生端：陈宇轩 (2026002-待澄清)
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: 'teacher',
  password: '123456'
})

const rules = {
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入登录密码', trigger: 'blur' }]
}

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const user = await authStore.login(form.username, form.password)
      ElMessage.success(`欢迎回来，${user.full_name}！`)
      router.push(
        user.role === 'teacher' ? '/teacher/submissions' : '/student/dashboard'
      )
    } finally {
      loading.value = false
    }
  })
}

function quickFill(username, password) {
  form.username = username
  form.password = password
  handleLogin()
}
</script>

<style scoped>
.login-wrapper {
  min-height: calc(100vh - 80px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-card {
  width: 480px;
  border-radius: 12px;
  padding: 12px 16px;
}
.login-header {
  text-align: center;
  margin-bottom: 24px;
}
.brand-pill {
  display: inline-block;
  background: #1e3a8a;
  color: #fff;
  font-weight: 700;
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 13px;
  margin-bottom: 10px;
}
.login-header h2 {
  margin: 0 0 8px 0;
  color: #0f172a;
}
.subtitle {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.quick-demo-box {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px dashed #e2e8f0;
}
.quick-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
}
.quick-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
