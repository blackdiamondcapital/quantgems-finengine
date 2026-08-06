import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const distDir = resolve(process.cwd(), 'dist')
const indexPath = resolve(distDir, 'index.html')

const pages = [
  {
    file: 'financial-statements.html',
    path: '/financial-statements',
    type: 'WebPage',
    title: '台股財報查詢與多期比較｜QuantGems® 財報引擎',
    description: '查詢上市櫃公司損益表、資產負債表、現金流量表與財務比率，以表格及趨勢圖比較單季、累計與多期財報變化。',
  },
  {
    file: 'financial-screener.html',
    path: '/financial-screener',
    type: 'CollectionPage',
    title: '台股基本面選股｜ROE、毛利率與財務比率篩選｜QuantGems®',
    description: '依市場、產業、ROE、ROA、毛利率、負債比、流動比、本益比與殖利率等條件篩選台股，快速建立基本面研究清單。',
  },
]

function replaceMeta(html, selector, value) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const pattern = new RegExp(`(<meta[^>]+${escaped}[^>]+content=")[^"]*(")`, 'i')
  return html.replace(pattern, `$1${value}$2`)
}

function replaceLink(html, relation, hreflang, value) {
  const language = hreflang ? `[^>]+hreflang="${hreflang}"` : ''
  const pattern = new RegExp(`(<link[^>]+rel="${relation}"${language}[^>]+href=")[^"]*(")`, 'i')
  return html.replace(pattern, `$1${value}$2`)
}

const baseHtml = await readFile(indexPath, 'utf8')
const originMatch = baseHtml.match(/<link rel="canonical" href="([^"]+)"/i)
const origin = originMatch ? new URL(originMatch[1]).origin : 'https://fs.quantgems.com'

await mkdir(distDir, { recursive: true })

for (const page of pages) {
  const url = `${origin}${page.path}`
  let html = baseHtml.replace(/<title>[^<]*<\/title>/i, `<title>${page.title}</title>`)
  html = replaceMeta(html, 'name="description"', page.description)
  html = replaceMeta(html, 'property="og:title"', page.title)
  html = replaceMeta(html, 'property="og:description"', page.description)
  html = replaceMeta(html, 'property="og:url"', url)
  html = replaceMeta(html, 'name="twitter:title"', page.title)
  html = replaceMeta(html, 'name="twitter:description"', page.description)
  html = replaceLink(html, 'canonical', '', url)
  html = replaceLink(html, 'alternate', 'zh-Hant', url)
  html = replaceLink(html, 'alternate', 'x-default', url)

  const pageSchema = {
    '@context': 'https://schema.org',
    '@type': page.type,
    '@id': `${url}#webpage`,
    url,
    name: page.title,
    description: page.description,
    inLanguage: 'zh-Hant',
    isPartOf: { '@id': `${origin}/#website` },
    about: { '@id': `${origin}/#webapp` },
  }
  html = html.replace(
    '</head>',
    `    <script type="application/ld+json">${JSON.stringify(pageSchema)}</script>\n  </head>`,
  )

  await writeFile(resolve(distDir, page.file), html)
}

const sitemapPath = resolve(distDir, 'sitemap.xml')
const sitemap = await readFile(sitemapPath, 'utf8')
const buildDate = new Date().toISOString().slice(0, 10)
await writeFile(sitemapPath, sitemap.replace(/<lastmod>[^<]+<\/lastmod>/g, `<lastmod>${buildDate}</lastmod>`))

console.log(`Generated ${pages.length} SEO entry pages and refreshed sitemap dates.`)
