const SITE_URL = 'https://fs.quantgems.com'

const PAGE_SEO = {
  landing: {
    path: '/',
    title: 'QuantGems® 財報引擎｜快速看懂台股財報與基本面選股',
    description: '一站掌握台股損益表、資產負債表、現金流量與關鍵財務比率；快速比較單季與累計趨勢，找出值得深入研究的公司。',
  },
  engine: {
    path: '/financial-statements',
    title: '台股財報查詢與多期比較｜QuantGems® 財報引擎',
    description: '查詢上市櫃公司損益表、資產負債表、現金流量表與財務比率，以表格及趨勢圖比較單季、累計與多期財報變化。',
  },
  screener: {
    path: '/financial-screener',
    title: '台股基本面選股｜ROE、毛利率與財務比率篩選｜QuantGems®',
    description: '依市場、產業、ROE、ROA、毛利率、負債比、流動比、本益比與殖利率等條件篩選台股，快速建立基本面研究清單。',
  },
}

function setMeta(selector, attribute, value) {
  const node = document.head.querySelector(selector)
  if (node) node.setAttribute(attribute, value)
}

export function resolveViewFromLocation() {
  if (typeof window === 'undefined') return 'landing'
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  const params = new URLSearchParams(window.location.search)

  if (path === '/financial-screener' || params.get('view') === 'screener') return 'screener'
  if (path === '/financial-statements' || params.get('view') === 'engine') return 'engine'
  return 'landing'
}

export function pagePath(view) {
  return PAGE_SEO[view]?.path || PAGE_SEO.landing.path
}

export function updatePageSeo(view) {
  if (typeof document === 'undefined') return
  const seo = PAGE_SEO[view] || PAGE_SEO.landing
  const canonicalUrl = `${SITE_URL}${seo.path}`

  document.title = seo.title
  setMeta('meta[name="description"]', 'content', seo.description)
  setMeta('meta[property="og:title"]', 'content', seo.title)
  setMeta('meta[property="og:description"]', 'content', seo.description)
  setMeta('meta[property="og:url"]', 'content', canonicalUrl)
  setMeta('meta[name="twitter:title"]', 'content', seo.title)
  setMeta('meta[name="twitter:description"]', 'content', seo.description)
  setMeta('link[rel="canonical"]', 'href', canonicalUrl)
  setMeta('link[rel="alternate"][hreflang="zh-Hant"]', 'href', canonicalUrl)
  setMeta('link[rel="alternate"][hreflang="x-default"]', 'href', canonicalUrl)
}
