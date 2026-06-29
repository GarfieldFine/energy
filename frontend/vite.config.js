import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
// ElementPlus 自动导入插件
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  // 插件集合（合并了所有需要的插件）
  plugins: [
    vue(),
    vueDevTools(),
    // ElementPlus 自动导入配置
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  // @ 路径别名配置
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8765', changeOrigin: true },
      '/docs': { target: 'http://127.0.0.1:8765', changeOrigin: true },
      '/redoc': { target: 'http://127.0.0.1:8765', changeOrigin: true },
      '/openapi.json': { target: 'http://127.0.0.1:8765', changeOrigin: true },
    },
  },
})
