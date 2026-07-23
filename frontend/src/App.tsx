import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Activity, ArrowUpRight, BookOpen, Check, Cloud, Database, FileUp, Gauge, Layers3, LogIn, LogOut, RefreshCw, Send, Server, ShieldCheck, Sparkles, UploadCloud, WifiOff, X } from 'lucide-react'
import { api, Mode, QueryResponse, Source, StatusResponse } from './api/client'
import { Scene3D } from './components/Scene3D'
import './styles/index.css'

interface Message { role: 'user' | 'assistant'; text: string; result?: QueryResponse }

const starterQuestions = [
  'What are the core findings across my indexed papers?',
  'Compare the methodologies used in the uploaded research.',
  'Explain the evidence behind the main conclusion.',
]

function App() {
  const [mode, setMode] = useState<Mode>('local')
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [showAuth, setShowAuth] = useState(false)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem('academic-rag-token')))
  const [uploading, setUploading] = useState(false)

  const indexStats = status?.index_stats ?? {}
  const nodeCount = Number(indexStats.total_nodes ?? indexStats.total_chunks ?? indexStats.count ?? 0)
  const documentCount = Number(indexStats.document_count ?? indexStats.documents ?? 0)
  const lastMessage = messages[messages.length - 1]
  const confidence = lastMessage?.result?.confidence_score ?? 0
  const connectionLabel = status ? 'API connected' : 'Connecting to API'

  const metrics = useMemo(() => [
    { label: 'Indexed nodes', value: nodeCount ? nodeCount.toLocaleString() : '—', icon: Layers3 },
    { label: 'Source papers', value: documentCount ? documentCount.toString() : '—', icon: BookOpen },
    { label: 'Answer confidence', value: confidence ? `${Math.round(confidence * 100)}%` : '—', icon: Gauge },
  ], [confidence, documentCount, nodeCount])

  useEffect(() => {
    void refreshStatus()
  }, [])

  async function refreshStatus() {
    try {
      const next = await api.status()
      setStatus(next)
      setMode(next.mode)
    } catch {
      setToast('Backend is offline. Start uvicorn on port 8000 to enable live research.')
    }
  }

  async function changeMode(nextMode: Mode) {
    setMode(nextMode)
    try {
      await api.setMode(nextMode)
      await refreshStatus()
      setToast(`${nextMode === 'local' ? 'Local' : 'Cloud'} mode active`)
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'Could not change mode')
    }
  }

  async function submitQuery(event?: FormEvent) {
    event?.preventDefault()
    const cleanQuery = query.trim()
    if (!cleanQuery || busy) return
    setBusy(true)
    setMessages((current) => [...current, { role: 'user', text: cleanQuery }])
    setQuery('')
    try {
      const result = await api.query(cleanQuery, mode)
      setMessages((current) => [...current, { role: 'assistant', text: result.answer, result }])
    } catch (error) {
      setMessages((current) => [...current, { role: 'assistant', text: error instanceof Error ? error.message : 'The request could not be completed.' }])
    } finally {
      setBusy(false)
    }
  }

  async function uploadFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setToast('Upload a PDF research paper')
      return
    }
    setUploading(true)
    try {
      const result = await api.upload(file)
      setToast(result.message)
      await refreshStatus()
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function reindex() {
    setBusy(true)
    try {
      const result = await api.reindex()
      setToast(result.message)
      await refreshStatus()
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'Re-index failed')
    } finally {
      setBusy(false)
    }
  }

  async function authenticate(event: FormEvent) {
    event.preventDefault()
    try {
      const result = authMode === 'login' ? await api.login(username, password) : await api.register(username, password)
      localStorage.setItem('academic-rag-token', result.access_token)
      setAuthenticated(true)
      setShowAuth(false)
      setToast(authMode === 'login' ? 'Signed in to research workspace' : 'Workspace account created')
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'Authentication failed')
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup"><div className="brand-mark"><Sparkles size={17} /></div><div><strong>Academic RAG</strong><span>research studio</span></div></div>
        <div className="topbar-right">
          <span className={`connection ${status ? 'online' : ''}`}><span className="pulse-dot" />{connectionLabel}</span>
          <button className="icon-button" onClick={() => void refreshStatus()} title="Refresh system status"><RefreshCw size={16} /></button>
          {authenticated ? <button className="user-button" onClick={() => { localStorage.removeItem('academic-rag-token'); setAuthenticated(false); setToast('Signed out') }}><LogOut size={15} />Sign out</button> : <button className="user-button" onClick={() => setShowAuth(true)}><LogIn size={15} />Sign in</button>}
        </div>
      </header>

      <main className="workspace-grid">
        <aside className="sidebar">
          <div className="eyebrow">Workspace</div>
          <h1>Research,<br /><em>connected.</em></h1>
          <p className="sidebar-intro">Ask grounded questions across your academic library, then follow the evidence back to its source.</p>
          <div className="mode-block">
            <div className="section-label">Execution mode</div>
            <div className="mode-switch"><button className={mode === 'local' ? 'active' : ''} onClick={() => void changeMode('local')}><WifiOff size={14} />Local</button><button className={mode === 'cloud' ? 'active' : ''} onClick={() => void changeMode('cloud')}><Cloud size={14} />Cloud</button></div>
            <p className="mode-note">{mode === 'local' ? 'Ollama + BGE models. Private by default.' : 'GPT-4o-mini + hosted embeddings.'}</p>
          </div>
          <div className="sidebar-actions">
            <label className={`upload-button ${uploading ? 'disabled' : ''}`}><UploadCloud size={16} />{uploading ? 'Indexing paper...' : 'Add research PDF'}<input type="file" accept="application/pdf" disabled={uploading} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadFile(file); event.currentTarget.value = '' }} /></label>
            <button className="quiet-button" onClick={() => void reindex()} disabled={busy}><RefreshCw size={15} />Re-index library</button>
          </div>
          <div className="sidebar-footer"><ShieldCheck size={15} /><span>Offline-first workspace<br /><small>Data stays in your environment</small></span></div>
        </aside>

        <section className="main-column">
          <div className="section-heading"><div><div className="eyebrow">Knowledge field</div><h2>Live research graph</h2></div><span className="graph-status"><Activity size={14} />{nodeCount ? `${nodeCount} nodes indexed` : 'Awaiting index'}</span></div>
          <div className="graph-panel"><Scene3D active={busy} nodeCount={nodeCount} /><div className="graph-overlay"><div><span className="tiny-label">ACTIVE MODE</span><strong>{mode === 'local' ? 'LOCAL / PRIVATE' : 'CLOUD / EXTENDED'}</strong></div><div className="graph-legend"><span><i className="cyan" />retrieval nodes</span><span><i className="gold" />source links</span></div></div><div className="graph-caption"><Database size={15} />{documentCount ? `${documentCount} papers mapped into your research space` : 'Upload a paper to populate your research space'}<ArrowUpRight size={15} /></div></div>

          <div className="metrics-row">{metrics.map(({ label, value, icon: Icon }) => <div className="metric" key={label}><Icon size={16} /><span>{label}</span><strong>{value}</strong></div>)}</div>

          <div className="chat-section"><div className="section-heading"><div><div className="eyebrow">Research assistant</div><h2>Ask your library</h2></div><span className="source-count"><Server size={14} />{messages.length ? `${messages.filter((message) => message.role === 'assistant').length} answers` : 'Ready'}</span></div><div className="chat-surface">
            {messages.length === 0 ? <div className="empty-chat"><div className="empty-icon"><Sparkles size={20} /></div><h3>Start with a research question</h3><p>Responses are grounded in indexed documents and carry their source excerpts with them.</p><div className="starter-list">{starterQuestions.map((starter) => <button key={starter} onClick={() => setQuery(starter)}>{starter}<ArrowUpRight size={14} /></button>)}</div></div> : <div className="messages">{messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><div className="message-label">{message.role === 'user' ? 'You' : 'RAG assistant'}</div><div className="message-body">{message.text}</div>{message.result && <SourceCards sources={message.result.sources} warnings={message.result.warnings} />}</div>)}</div>}
            <form className="query-form" onSubmit={submitQuery}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask about your indexed research..." /><button type="submit" disabled={busy || !query.trim()} title="Send question"><Send size={17} /></button></form>
          </div></div>
        </section>
      </main>

      {toast && <button className="toast" onClick={() => setToast('')}><Check size={15} />{toast}<X size={14} /></button>}
      {showAuth && <div className="modal-backdrop" onClick={() => setShowAuth(false)}><form className="auth-modal" onSubmit={authenticate} onClick={(event) => event.stopPropagation()}><div className="modal-header"><div><div className="eyebrow">Workspace access</div><h2>{authMode === 'login' ? 'Welcome back' : 'Create account'}</h2></div><button type="button" className="icon-button" onClick={() => setShowAuth(false)}><X size={16} /></button></div><label>Username<input required minLength={3} value={username} onChange={(event) => setUsername(event.target.value)} /></label><label>Password<input required minLength={4} type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><button className="primary-button" type="submit">{authMode === 'login' ? 'Sign in' : 'Register'}<ArrowUpRight size={16} /></button><button type="button" className="switch-auth" onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>{authMode === 'login' ? 'Need an account? Register' : 'Already registered? Sign in'}</button></form></div>}
    </div>
  )
}

function SourceCards({ sources, warnings }: { sources: Source[]; warnings: string[] }) {
  return <div className="sources"><div className="sources-title"><FileUp size={13} />Evidence trail</div>{warnings.map((warning) => <div className="warning" key={warning}>{warning}</div>)}{sources.slice(0, 3).map((source, index) => <div className="source-card" key={`${source.filename ?? source.title ?? 'source'}-${index}`}><span className="source-index">0{index + 1}</span><div><strong>{source.filename ?? source.title ?? 'Research source'}</strong><p>{source.text_snippet ?? source.snippet ?? 'Source excerpt available in the retrieval context.'}</p></div>{source.score !== undefined && <span className="score">{Math.round(source.score * 100)}%</span>}</div>)}</div>
}

export default App
