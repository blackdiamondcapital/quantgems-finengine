import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const DEFAULT_SITE_URL = 'https://quantgems-finengine.vercel.app'

function siteUrlPlugin(siteUrl) {
  return {
    name: 'inject-site-url',
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        if (!html.includes('%VITE_SITE_URL%')) return html
        return html.split('%VITE_SITE_URL%').join(siteUrl)
      },
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const siteUrl = String(env.VITE_SITE_URL || process.env.VITE_SITE_URL || DEFAULT_SITE_URL)
    .trim()
    .replace(/\/$/, '') || DEFAULT_SITE_URL

  return {
    plugins: [vue(), siteUrlPlugin(siteUrl)],
    server: {
      port: 5178,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8787',
          changeOrigin: true,
        },
      },
    },
  }
})
