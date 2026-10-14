/**
 * 统一 API 请求封装层 (src/api/index.js)
 * - 自动在请求头注入 JWT Bearer Token
 * - 统一处理 401 登录过期与后端详细错误提示
 * - 封装认证、学生管理、双模式量规、作业上传、AI评分、模糊澄清、教师复核与 Excel 导出接口
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 65000
})

// 请求拦截器：附加 JWT Token
http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('edugrade_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：统一处理错误提示
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || error.message || '请求失败'
    if (status === 401) {
      localStorage.removeItem('edugrade_token')
      localStorage.removeItem('edugrade_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    ElMessage.error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    return Promise.reject(error)
  }
)

export const api = {
  // 1. 系统状态与认证
  getHealth: () => http.get('/api/health'),
  login: (data) => http.post('/api/auth/login', data),
  getMe: () => http.get('/api/auth/me'),

  // 2. 学生信息管理
  listStudents: (keyword = '') =>
    http.get('/api/students', { params: keyword ? { keyword } : {} }),
  createStudent: (data) => http.post('/api/students', data),
  updateStudent: (id, data) => http.put(`/api/students/${id}`, data),
  deleteStudent: (id) => http.delete(`/api/students/${id}`),

  // 3. 双模式量规管理（内置权威量规 + 自定义量规 LLM 解析确认）
  listRubrics: (mode = '') =>
    http.get('/api/rubrics', { params: mode ? { mode } : {} }),
  getRubric: (id) => http.get(`/api/rubrics/${id}`),
  parseCustomRubric: (formData) =>
    http.post('/api/rubrics/parse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  confirmCustomRubric: (data) => http.post('/api/rubrics/confirm', data),
  updateRubric: (id, data) => http.put(`/api/rubrics/${id}`, data),
  deleteRubric: (id) => http.delete(`/api/rubrics/${id}`),

  // 4. 作业上传与列表查询
  listSubmissions: (params = {}) => http.get('/api/submissions', { params }),
  getSubmissionDetail: (id) => http.get(`/api/submissions/${id}`),
  uploadSubmission: (formData) =>
    http.post('/api/submissions/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  batchUploadSubmissions: (formData) =>
    http.post('/api/submissions/batch-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  deleteSubmission: (id) => http.delete(`/api/submissions/${id}`),

  // 5. AI 双模式评分、模糊澄清、教师复核与 Excel 导出
  evaluateSubmission: (id, data) =>
    http.post(`/api/grading/${id}/evaluate`, data),
  submitClarification: (id, data) =>
    http.post(`/api/grading/${id}/clarify`, data),
  batchEvaluateSubmissions: (data) =>
    http.post('/api/grading/batch-evaluate', data),
  reviewSubmission: (id, data) =>
    http.put(`/api/grading/${id}/review`, data),

  exportExcel: async (statusFilter = '') => {
    const token = localStorage.getItem('edugrade_token')
    const response = await axios.get('/api/grading/export/excel', {
      params: statusFilter ? { status_filter: statusFilter } : {},
      headers: { Authorization: `Bearer ${token}` },
      responseType: 'blob'
    })
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `EduGrade_作业评分成绩单_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }
}
