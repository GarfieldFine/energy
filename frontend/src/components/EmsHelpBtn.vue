<script setup>
import { ref } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import EmsDrawer from '@/components/EmsDrawer.vue'

defineProps({
  title: { type: String, required: true },
  size: { type: [String, Number], default: '420px' },
})

const visible = ref(false)
</script>

<template>
  <el-button
    class="ems-help-btn"
    text
    type="primary"
    round
    size="small"
    :icon="QuestionFilled"
    aria-label="说明"
    @click="visible = true"
  />
  <EmsDrawer v-model="visible" :title="title" :size="size">
    <div class="ems-help-body"><slot /></div>
    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
    <template v-else #footer>
      <el-button type="primary" round @click="visible = false">知道了</el-button>
    </template>
  </EmsDrawer>
</template>

<style scoped>
.ems-help-btn {
  padding: 4px !important;
  min-height: 28px;
  margin-left: 4px;
}

.ems-help-body {
  font-size: 14px;
  line-height: 1.65;
  color: var(--feishu-text-secondary, #646a73);
}

.ems-help-body :deep(p) {
  margin: 0 0 10px;
}

.ems-help-body :deep(p:last-child) {
  margin-bottom: 0;
}
</style>
