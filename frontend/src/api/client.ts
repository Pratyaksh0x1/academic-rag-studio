export type Mode = 'local' | 'cloud'

export interface Source {
  filename?: string
  title?: string
  url?: string
  score?: number
  text_snippet?: string
  snippet?: string
  type?: string
}

export interface QueryResponse {
  query: string
  answer: string
  mode: string
  confidence_score: number
  sources: Source[]
  retrieved_chunks: Array<Record<string, unknown>>
  warnings: string[]
}

export interface StatusResponse {
  status: string
  mode: Mode
  index_stats: Record<string, unknown>
  ollama: Record<string, unknown>
  services: Record<string, boolean>
}

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = window.localStorage.getItem('academic-rag-token')
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `Request failed with ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  status: () => request<StatusResponse>('/api/status'),
  register: (username: string, password: string) => request<{ access_token: string }>('/auth/register', {
    method: 'POST', body: JSON.stringify({ username, password }),
  }),
  login: (username: string, password: string) => request<{ access_token: string }>('/auth/login', {
    method: 'POST', body: JSON.stringify({ username, password }),
  }),
  setMode: (mode: Mode) => request<{ mode: Mode; message: string }>('/api/mode', {
    method: 'POST', body: JSON.stringify({ mode }),
  }),
  query: (query: string, mode: Mode) => request<QueryResponse>('/api/query', {
    method: 'POST', body: JSON.stringify({ query, mode }),
  }),
  upload: (file: File, rebuild = false) => {
    const body = new FormData()
    body.append('file', file)
    return request<{ message: string; parse_details: Record<string, unknown>; index_stats: Record<string, unknown> }>('/api/ingest?rebuild=' + rebuild, {
      method: 'POST', body,
    })
  },
  reindex: () => request<{ message: string; index_stats: Record<string, unknown> }>('/api/reindex', { method: 'POST' }),
  evaluate: () => request<{ metrics: Record<string, number> }>('/api/evaluate'),
}
