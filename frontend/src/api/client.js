import axios from 'axios'

/** 空字符串时使用相对路径，配合 Vite 代理同源访问 /api */
const baseURL = import.meta.env.VITE_API_BASE ?? ''

export const http = axios.create({
  baseURL: baseURL.replace(/\/$/, '') || undefined,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

const TOKEN_KEY = 'ems_auth_token'
const stored = typeof localStorage !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : ''
if (stored) {
  http.defaults.headers.common.Authorization = `Bearer ${stored}`
}

/** 设置 / 清除 JWT */
export function setHttpAuthToken(token) {
  const t = (token || '').trim()
  if (t) http.defaults.headers.common.Authorization = `Bearer ${t}`
  else delete http.defaults.headers.common.Authorization
}

/** 手机端可动态切换 API 根地址（直连后端时） */
export function setHttpBaseURL(url) {
  const u = (url || '').trim().replace(/\/$/, '')
  http.defaults.baseURL = u || undefined
}

http.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    const msg =
      err.response?.data?.detail ??
      err.response?.data?.error ??
      err.message ??
      '请求失败'
    const error = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    error.status = status
    return Promise.reject(error)
  },
)

export function apiUrl(path) {
  const b = baseURL.replace(/\/$/, '')
  const p = path.startsWith('/') ? path : `/${path}`
  return b ? `${b}${p}` : p
}
