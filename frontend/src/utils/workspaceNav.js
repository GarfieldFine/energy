import { useAuthStore } from '@/stores/auth'
import { defaultHomePath } from '@/utils/permissions'

const SCREEN_RETURN_KEY = 'ems_screen_from_workspace'

/** 新标签页打开数据大屏（保留原工作台标签页；不可使用 noopener，否则无法回到原页） */
export function openDataScreen(router) {
  sessionStorage.setItem(SCREEN_RETURN_KEY, router.currentRoute.value.fullPath)
  const url = router.resolve({ path: '/screen' }).href
  const opened = window.open(url, 'ems_data_screen')
  if (!opened) {
    sessionStorage.removeItem(SCREEN_RETURN_KEY)
    router.push('/screen')
    return
  }
  opened.focus()
}

/**
 * 从全屏大屏返回：聚焦并关闭当前标签，回到打开大屏前的原工作台页。
 */
export function returnToWorkspace(router) {
  sessionStorage.removeItem(SCREEN_RETURN_KEY)

  if (typeof window !== 'undefined' && window.opener && !window.opener.closed) {
    try {
      window.opener.focus()
    } catch {
      /* 忽略 focus 失败 */
    }
    window.close()
    return
  }

  if (window.history.length > 1) {
    router.back()
    return
  }

  const auth = useAuthStore()
  const target = defaultHomePath(auth.role) || auth.firstAllowedPath()
  router.replace(target)
}
