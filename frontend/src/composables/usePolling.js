import { onUnmounted } from 'vue'

/**
 * @param {() => void} fn
 * @param {number} intervalMs
 */
export function usePolling(fn, intervalMs) {
  const id = setInterval(fn, intervalMs)
  onUnmounted(() => clearInterval(id))
  return () => clearInterval(id)
}
