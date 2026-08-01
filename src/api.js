async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { Accept: 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
  meta: () => request('/api/meta'),
  fields: (kind) =>
    kind
      ? request(`/api/fields?kind=${encodeURIComponent(kind)}`)
      : request('/api/fields'),
  stats: () => request('/api/stats'),
  search: (q) => request(`/api/symbols/search?q=${encodeURIComponent(q)}&limit=16`),
  overview: (code, { basis = 'single' } = {}) => {
    const qs = new URLSearchParams()
    if (basis) qs.set('basis', basis)
    const q = qs.toString()
    return request(`/api/reports/${encodeURIComponent(code)}/overview${q ? `?${q}` : ''}`)
  },
  statement: (code, kind, limit = 8, { full = false, basis = 'single' } = {}) => {
    const qs = new URLSearchParams({ limit: String(limit) })
    if (full) qs.set('full', '1')
    if ((kind === 'income' || kind === 'combined' || kind === 'ratios') && basis) {
      qs.set('basis', basis)
    }
    return request(`/api/reports/${encodeURIComponent(code)}/${kind}?${qs}`)
  },
  screenerMeta: () => request('/api/screener/meta'),
  screener: (params = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return
      qs.set(k, String(v))
    })
    const q = qs.toString()
    return request(`/api/screener${q ? `?${q}` : ''}`)
  },
}
