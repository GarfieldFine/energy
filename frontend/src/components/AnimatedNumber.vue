<script setup>
import { ref, watch } from 'vue'
import { runCountUp } from '@/composables/useCountUp'

const props = defineProps({
  value: { type: Number, default: 0 },
  digits: { type: Number, default: 0 },
  animateOnMount: { type: Boolean, default: true },
  duration: { type: Number, default: 650 },
})

const display = ref(0)

function format(n) {
  const d = props.digits
  const rounded = d > 0 ? Math.round(n * 10 ** d) / 10 ** d : Math.round(n)
  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: d,
    minimumFractionDigits: d > 0 ? d : 0,
  }).format(rounded)
}

watch(
  () => props.value,
  (v, oldV) => {
    if (v == null || Number.isNaN(Number(v))) return
    const target = Number(v)
    if (oldV === undefined && !props.animateOnMount) {
      display.value = target
      return
    }
    const from = oldV === undefined ? 0 : display.value
    runCountUp(
      target,
      (n) => {
        display.value = n
      },
      { from, duration: props.duration },
    )
  },
  { immediate: true },
)
</script>

<template>
  <span class="animated-num">{{ format(display) }}</span>
</template>

<style scoped>
.animated-num {
  font-variant-numeric: tabular-nums;
  font-family: var(--ems-font-number, inherit);
}
</style>
