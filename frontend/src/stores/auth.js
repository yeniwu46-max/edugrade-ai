/**
 * 用户认证与角色状态管理 (src/stores/auth.js)
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('edugrade_token') || '')
  const user = ref(
    JSON.parse(localStorage.getItem('edugrade_user') || 'null')
  )

  const isLoggedIn = computed(() => Boolean(token.value && user.value))
  const isTeacher = computed(() => user.value?.role === 'teacher')
  const isStudent = computed(() => user.value?.role === 'student')

  async function login(username, password) {
    const res = await api.login({ username, password })
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('edugrade_token', res.access_token)
    localStorage.setItem('edugrade_user', JSON.stringify(res.user))
    return res.user
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('edugrade_token')
    localStorage.removeItem('edugrade_user')
  }

  return {
    token,
    user,
    isLoggedIn,
    isTeacher,
    isStudent,
    login,
    logout
  }
})
