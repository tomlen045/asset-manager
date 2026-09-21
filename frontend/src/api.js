import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

api.interceptors.request.use(cfg => {
  const t = localStorage.getItem('token')
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

api.interceptors.response.use(
  r => r.data,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      if (!location.hash.includes('login')) location.hash = '#/login'
    }
    const msg = err.response?.data
    const text = typeof msg === 'string' ? msg
      : Object.values(msg || {}).flat?.()[0] || '请求失败'
    ElMessage.error(String(text).slice(0, 120))
    return Promise.reject(err)
  }
)

export default api
