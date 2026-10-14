<template>
  <div class="app-layout">
    <!-- 顶部导航栏（登录后展示） -->
    <el-header v-if="authStore.isLoggedIn" class="top-header">
      <div class="brand-area" @click="goHome">
        <div class="logo-badge">EduGrade AI</div>
        <span class="brand-title">教学作业上传与双模式自动评分系统</span>
        <el-tag
          size="small"
          :type="authStore.isTeacher ? 'primary' : 'success'"
          effect="dark"
          style="margin-left: 10px"
        >
          {{ authStore.isTeacher ? '教师教研端' : '学生学习端' }}
        </el-tag>
      </div>

      <!-- 教师端导航菜单 -->
      <el-menu
        v-if="authStore.isTeacher"
        mode="horizontal"
        :default-active="activePath"
        router
        class="nav-menu"
        background-color="transparent"
        text-color="#e2e8f0"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/teacher/submissions">
          <el-icon><DocumentChecked /></el-icon>
          <span>作业管理与智能批改</span>
        </el-menu-item>
        <el-menu-item index="/teacher/rubrics">
          <el-icon><Collection /></el-icon>
          <span>双模式量规库 (SOLO/布鲁姆 & 自定义学习)</span>
        </el-menu-item>
        <el-menu-item index="/teacher/students">
          <el-icon><User /></el-icon>
          <span>学生名册管理</span>
        </el-menu-item>
      </el-menu>

      <!-- 学生端导航菜单 -->
      <el-menu
        v-else
        mode="horizontal"
        :default-active="activePath"
        router
        class="nav-menu"
        background-color="transparent"
        text-color="#e2e8f0"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/student/dashboard">
          <el-icon><Reading /></el-icon>
          <span>我的作业与诊断反馈报告</span>
        </el-menu-item>
      </el-menu>

      <!-- 右侧用户信息与快捷角色切换 -->
      <div class="user-area">
        <el-tag
          v-if="healthInfo"
          size="small"
          :type="healthInfo.gemini_api_key_configured ? 'success' : 'warning'"
          effect="plain"
          style="margin-right: 12px"
        >
          LLM: {{ healthInfo.llm_provider.toUpperCase() }}
          ({{ healthInfo.gemini_api_key_configured ? healthInfo.gemini_model : '本地启发式引擎已就绪' }})
        </el-tag>

        <el-dropdown trigger="click" @command="handleUserCommand">
          <span class="user-dropdown-link">
            <el-avatar :size="28" style="background: #3b82f6; margin-right: 8px">
              {{ authStore.user?.full_name?.slice(0, 1) || 'U' }}
            </el-avatar>
            <span>{{ authStore.user?.full_name }}</span>
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                账号：{{ authStore.user?.username }}
                <span v-if="authStore.user?.class_name">（{{ authStore.user.class_name }}）</span>
              </el-dropdown-item>
              <el-dropdown-item divided command="switch_teacher">
                一键切换：张明远老师 (教师端)
              </el-dropdown-item>
              <el-dropdown-item command="switch_student_1">
                一键切换：林知夏 2026001 (学生端-已评分)
              </el-dropdown-item>
              <el-dropdown-item command="switch_student_2">
                一键切换：陈宇轩 2026002 (学生端-待澄清)
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <!-- 主内容区域 -->
    <main class="main-container">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from './stores/auth'
import { api } from './api'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const healthInfo = ref(null)

const activePath = computed(() => {
  if (route.path.startsWith('/teacher/submissions')) return '/teacher/submissions'
  return route.path
})

onMounted(async () => {
  try {
    healthInfo.value = await api.getHealth()
  } catch {
    // ignore
  }
})

function goHome() {
  router.push(authStore.isTeacher ? '/teacher/submissions' : '/student/dashboard')
}

async function handleUserCommand(cmd) {
  if (cmd === 'logout') {
    authStore.logout()
    router.push('/login')
    return
  }
  const accountMap = {
    switch_teacher: 'teacher',
    switch_student_1: '2026001',
    switch_student_2: '2026002'
  }
  const targetUsername = accountMap[cmd]
  if (targetUsername) {
    const u = await authStore.login(targetUsername, '123456')
    ElMessage.success(`已切换至 ${u.full_name}（${u.role === 'teacher' ? '教师端' : '学生端'}）`)
    router.push(u.role === 'teacher' ? '/teacher/submissions' : '/student/dashboard')
  }
}
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.top-header {
  height: 62px;
  background: linear-gradient(90deg, #0f172a 0%, #1e3a8a 100%);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.15);
}
.brand-area {
  display: flex;
  align-items: center;
  cursor: pointer;
}
.logo-badge {
  background: #3b82f6;
  color: #fff;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  margin-right: 10px;
  font-size: 14px;
}
.brand-title {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.4px;
}
.nav-menu {
  border-bottom: none !important;
  flex: 1;
  margin-left: 36px;
}
.user-area {
  display: flex;
  align-items: center;
}
.user-dropdown-link {
  display: flex;
  align-items: center;
  color: #f8fafc;
  cursor: pointer;
  font-size: 14px;
}
.main-container {
  flex: 1;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
  box-sizing: border-box;
}
</style>
