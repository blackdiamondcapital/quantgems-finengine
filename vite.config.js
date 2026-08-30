import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

const DEFAULT_SITE_URL = 'https://fs.quantgems.com'

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
    plugins: [
      vue(),
      siteUrlPlugin(siteUrl),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: [
          'quantgems-finengine-icon.svg',
          'pwa-icon.svg',
          'pwa-icon-192.png',
          'pwa-icon-512.png',
          'apple-touch-icon.png',
          'og-image.png',
          'robots.txt',
          'sitemap.xml',
        ],
        manifest: {
          name: 'QuantGems 財報引擎',
          short_name: '財報引擎',
          description:
            '快速看懂台股三大財報與關鍵財務比率，用基本面條件找出值得研究的好公司。',
          theme_color: '#07080c',
          background_color: '#07080c',
          display: 'standalone',
          orientation: 'any',
          scope: '/',
          start_url: '/',
          lang: 'zh-TW',
          categories: ['finance', 'productivity'],
          icons: [
            {
              src: '/pwa-icon-192.png',
              sizes: '192x192',
              type: 'image/png',
              purpose: 'any',
            },
            {
              src: '/pwa-icon-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'any',
            },
            {
              src: '/pwa-icon-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
            {
              src: '/pwa-icon.svg',
              sizes: 'any',
              type: 'image/svg+xml',
              purpose: 'any',
            },
          ],
        },
        workbox: {
          maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
          globPatterns: ['**/*.{js,css,html,svg,png,woff2,ico,webmanifest}'],
          // 舊版大圖僅保留相容路徑，勿進 SW 預快取
          globIgnores: ['**/quantgems-finengine-icon.png'],
          cleanupOutdatedCaches: true,
          clientsClaim: true,
          skipWaiting: true,
          navigateFallback: 'index.html',
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [
            {
              urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/i,
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'qg-font-cache-v2',
                expiration: { maxEntries: 16, maxAgeSeconds: 60 * 60 * 24 * 14 },
              },
            },
            {
              urlPattern: /\/api\/.*/i,
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-cache',
                expiration: { maxEntries: 80, maxAgeSeconds: 60 * 5 },
                networkTimeoutSeconds: 10,
              },
            },
          ],
        },
        devOptions: {
          enabled: false,
        },
      }),
    ],
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
