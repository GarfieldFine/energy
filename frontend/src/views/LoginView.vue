<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { defaultHomePath } from '@/utils/permissions'
import * as api from '@/api'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({
  username: '',
  password: '',
})

const demoAccounts = ref([])

async function onSubmit() {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  try {
    const user = await auth.login(form.username.trim(), form.password)
    ElMessage.success(`欢迎，${user.display_name || user.username}`)
    const redirect = route.query.redirect
    if (typeof redirect === 'string' && redirect.startsWith('/')) {
      router.replace(redirect)
    } else {
      router.replace(defaultHomePath(user.role))
    }
  } catch (e) {
    ElMessage.error(e.message ?? '登录失败')
  }
}

function quickFill(username, password) {
  form.username = username
  form.password = password
}

onMounted(async () => {
  try {
    const res = await api.getAuthDemoAccounts()
    demoAccounts.value = res.items ?? []
  } catch {
    demoAccounts.value = [
      { username: 'admin', role_label: '系统管理员' },
      { username: 'energy', role_label: '能源管理员' },
      { username: 'ops', role_label: '运维工程师' },
    ]
  }
})
</script>

<template>
  <div class="login-page">
    <div class="login-bg-shape login-bg-shape--1" aria-hidden="true" />
    <div class="login-bg-shape login-bg-shape--2" aria-hidden="true" />

    <div class="login-card">
      <div class="login-brand">
        <span class="login-mark">EMS</span>
        <div>
          <h1>建筑能源智能管理系统</h1>
          <p>实习版 · 三角色登录</p>
        </div>
      </div>

      <el-form label-position="top" class="login-form" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            placeholder="admin / energy / ops"
            autocomplete="username"
            size="large"
          >
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="演示密码见下方"
            autocomplete="current-password"
            size="large"
            @keyup.enter="onSubmit"
          >
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" round class="login-btn" size="large" :loading="auth.loading" @click="onSubmit">
          登录
        </el-button>
      </el-form>

      <div class="demo-block">
        <div class="demo-title">演示账号（点击填入）</div>
        <div class="demo-list">
          <el-tag
            v-for="acc in demoAccounts"
            :key="acc.username"
            class="demo-tag"
            effect="plain"
            round
            @click="quickFill(acc.username, acc.username === 'admin' ? 'admin123' : acc.username === 'energy' ? 'energy123' : 'ops123')"
          >
            {{ acc.username }} · {{ acc.role_label }}
          </el-tag>
        </div>
        <p class="demo-hint">admin/admin123 · energy/energy123 · ops/ops123</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--feishu-bg, #f5f6f7);
  padding: 24px;
  position: relative;
  overflow: hidden;
}

.login-bg-shape {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  pointer-events: none;
}

.login-bg-shape--1 {
  width: 420px;
  height: 420px;
  background: rgba(51, 112, 255, 0.18);
  top: -120px;
  right: -80px;
}

.login-bg-shape--2 {
  width: 320px;
  height: 320px;
  background: rgba(51, 112, 255, 0.1);
  bottom: -80px;
  left: -60px;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: var(--feishu-surface, #fff);
  border-radius: var(--feishu-radius-lg, 16px);
  padding: 36px 32px 28px;
  box-shadow: var(--feishu-shadow-lg, 0 8px 28px rgba(31, 35, 41, 0.12));
  position: relative;
  z-index: 1;
}

.login-brand {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 32px;
}

.login-mark {
  width: 52px;
  height: 52px;
  border-radius: var(--feishu-radius-md, 12px);
  background: linear-gradient(145deg, #4e83fd, #3370ff);
  color: #fff;
  font-weight: 800;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(51, 112, 255, 0.35);
}

.login-brand h1 {
  margin: 0;
  font-size: 18px;
  line-height: 1.35;
  color: var(--feishu-text, #1f2329);
  font-weight: 600;
}

.login-brand p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--feishu-text-secondary, #646a73);
}

.login-form :deep(.el-form-item__label) {
  color: var(--feishu-text-secondary, #646a73);
  font-weight: 500;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
}

.demo-block {
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px solid var(--feishu-border, #dee0e3);
}

.demo-title {
  font-size: 13px;
  color: var(--feishu-text-secondary, #646a73);
  margin-bottom: 10px;
}

.demo-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.demo-tag {
  cursor: pointer;
  transition: background 0.15s;
}

.demo-tag:hover {
  background: var(--feishu-primary-light, #e1eaff);
  border-color: var(--feishu-primary, #3370ff);
  color: var(--feishu-primary, #3370ff);
}

.demo-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #a9aeb8;
  line-height: 1.5;
}
</style>
