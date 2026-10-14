/**
 * 前端路由与角色权限守卫 (src/router/index.js)
 * 区分教师端 (/teacher/*) 与学生端 (/student/*)
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

import LoginView from '../views/LoginView.vue'
import TeacherDashboard from '../views/teacher/TeacherDashboard.vue'
import SubmissionDetailView from '../views/teacher/SubmissionDetailView.vue'
import RubricManageView from '../views/teacher/RubricManageView.vue'
import StudentManageView from '../views/teacher/StudentManageView.vue'
import StudentDashboard from '../views/student/StudentDashboard.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { public: true }
  },
  {
    path: '/',
    redirect: () => {
      const user = JSON.parse(localStorage.getItem('edugrade_user') || 'null')
      if (!user) return '/login'
      return user.role === 'teacher' ? '/teacher/submissions' : '/student/dashboard'
    }
  },
  // 教师端路由
  {
    path: '/teacher/submissions',
    name: 'TeacherDashboard',
    component: TeacherDashboard,
    meta: { role: 'teacher' }
  },
  {
    path: '/teacher/submissions/:id',
    name: 'SubmissionDetail',
    component: SubmissionDetailView,
    meta: { role: 'teacher' }
  },
  {
    path: '/teacher/rubrics',
    name: 'RubricManage',
    component: RubricManageView,
    meta: { role: 'teacher' }
  },
  {
    path: '/teacher/students',
    name: 'StudentManage',
    component: StudentManageView,
    meta: { role: 'teacher' }
  },
  // 学生端路由
  {
    path: '/student/dashboard',
    name: 'StudentDashboard',
    component: StudentDashboard,
    meta: { role: 'student' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  if (to.meta.public) {
    if (authStore.isLoggedIn) {
      return next(authStore.isTeacher ? '/teacher/submissions' : '/student/dashboard')
    }
    return next()
  }
  if (!authStore.isLoggedIn) {
    return next('/login')
  }
  if (to.meta.role === 'teacher' && !authStore.isTeacher) {
    return next('/student/dashboard')
  }
  if (to.meta.role === 'student' && !authStore.isStudent) {
    return next('/teacher/submissions')
  }
  next()
})

export default router
