<script setup>
import * as echarts from 'echarts'
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const emit = defineEmits(['chartClick'])

const props = defineProps({
  option: { type: Object, required: true },
  theme: { type: String, default: undefined },
  /** 为 true 时派发饼图/柱状等点击，便于联动筛选 */
  enableClick: { type: Boolean, default: false },
})

const root = ref(null)
let chart

function resize() {
  chart?.resize()
}

function bindClick() {
  if (!chart) return
  chart.off('click')
  if (!props.enableClick) return
  chart.on('click', (params) => emit('chartClick', params))
}

onMounted(() => {
  if (!root.value) return
  chart = echarts.init(root.value, props.theme)
  chart.setOption(props.option)
  window.addEventListener('resize', resize)
  nextTick(bindClick)
})

watch(
  () => props.option,
  (o) => {
    if (chart && o) {
      chart.setOption(o, true)
      nextTick(bindClick)
    }
  },
  { deep: true },
)

watch(
  () => props.enableClick,
  () => nextTick(bindClick),
)

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = undefined
})

defineExpose({ resize })
</script>

<template>
  <div ref="root" class="app-chart" />
</template>

<style scoped>
.app-chart {
  width: 100%;
  min-height: 280px;
  height: 100%;
}
</style>
