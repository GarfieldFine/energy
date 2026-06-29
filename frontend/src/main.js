import './styles/feishu-ui.css'
import 'element-plus/dist/index.css'
import './styles/ems-theme.css'
import './styles/print.css'
import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { http } from './api/client'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.status === 401 && router.currentRoute.value.name !== 'login') {
      useAuthStore().logout()
      router.replace({
        name: 'login',
        query: { redirect: router.currentRoute.value.fullPath },
      })
    }
    return Promise.reject(err)
  },
)

app.mount('#app')
