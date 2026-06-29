/**
 * 将数值从 from 过渡到 to，在每一帧调用 onUpdate（用于 KPI 数字滚动）
 */
export function runCountUp(to, onUpdate, { from = 0, duration = 650, easing = 'cubicOut' } = {}) {
  const easings = {
    cubicOut: (t) => 1 - (1 - t) ** 3,
    linear: (t) => t,
  }
  const ease = easings[easing] ?? easings.cubicOut
  const start = performance.now()
  const delta = to - from

  function frame(now) {
    const t = Math.min(1, (now - start) / duration)
    const v = from + delta * ease(t)
    onUpdate(v)
    if (t < 1) requestAnimationFrame(frame)
    else onUpdate(to)
  }
  requestAnimationFrame(frame)
}
