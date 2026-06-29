import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api'
import { setHttpAuthToken } from '@/api/client'
import {
  canAccessRoute,
  canWriteIncidents,
  defaultHomePath,
  ROUTE_ROLES,
} from '@/utils/permissions'

const TOKEN_KEY = 'ems_auth_token'
const USER_KEY = 'ems_auth_user'

function loadStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const initialToken = localStorage.getItem(TOKEN_KEY) || ''
if (initialToken) setHttpAuthToken(initialToken)

export const useAuthStore = defineStore('auth', () => {
  const token = ref(initialToken)
  const user = ref(loadStoredUser())
  const loading = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const role = computed(() => user.value?.role ?? '')
  const roleLabel = computed(() => user.value?.role_label ?? '')
  const displayName = computed(() => user.value?.display_name ?? user.value?.username ?? '')
  const canWriteIncidentsFlag = computed(() => canWriteIncidents(role.value))

  function setSession(accessToken, userInfo) {
    token.value = accessToken
    user.value = userInfo
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY, JSON.stringify(userInfo))
    setHttpAuthToken(accessToken)
  }

  function clearSession() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setHttpAuthToken('')
  }

  async function login(username, password) {
    loading.value = true
    try {
      const res = await api.postAuthLogin({ username, password })
      setSession(res.access_token, res.user)
      return res.user
    } finally {
      loading.value = false
    }
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      const res = await api.getAuthMe()
      if (res.user) {
        user.value = res.user
        localStorage.setItem(USER_KEY, JSON.stringify(res.user))
      }
      return res.user
    } catch {
      clearSession()
      return null
    }
  }

  function logout() {
    clearSession()
  }

  function hasRoute(name) {
    return canAccessRoute(name, role.value)
  }

  function firstAllowedPath() {
    const home = defaultHomePath(role.value)
    const homeName = home.replace(/^\//, '')
    if (homeName && canAccessRoute(homeName, role.value)) {
      return home
    }

    const order = [
      'dashboard',
      'energy',
      'stats',
      'incidents',
      'knowledge',
      'twin',
      'operations',
      'benchmark',
      'pricing',
      'admin',
    ]
    for (const name of order) {
      if (canAccessRoute(name, role.value)) {
        if (name === 'dashboard') return '/dashboard'
        return `/${name}`
      }
    }
    return defaultHomePath(role.value)
  }

  return {
    token,
    user,
    loading,
    isLoggedIn,
    role,
    roleLabel,
    displayName,
    canWriteIncidents: canWriteIncidentsFlag,
    routeRoles: ROUTE_ROLES,
    setSession,
    clearSession,
    login,
    fetchMe,
    logout,
    hasRoute,
    firstAllowedPath,
  }
})
