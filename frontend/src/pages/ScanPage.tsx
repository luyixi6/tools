import React, { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { ModuleInfo, FileInfo, ScanInfo } from '../types'

const LAST_SCAN_KEY = 'cpp_inspector_last_scan_id'

function getLastScan(): string | null {
  try { return localStorage.getItem(LAST_SCAN_KEY) }
  catch { return null }
}

function setLastScan(scanId: string) {
  try { localStorage.setItem(LAST_SCAN_KEY, scanId) }
  catch {}
}

export default function ScanPage() {
  const nav = useNavigate()
  const { t, lang } = useI18n()
  const [searchParams] = useSearchParams()
  const urlScanId = searchParams.get('scanId')
  const [scanId, setScanId] = useState<string | null>(
    urlScanId || getLastScan() || null
  )
  const [scanList, setScanList] = useState<ScanInfo[]>([])
  const [projectRoot, setProjectRoot] = useState('')
  const [scan, setScan] = useState<ScanInfo | null>(null)
  const [modules, setModules] = useState<ModuleInfo[]>([])
  const [files, setFiles] = useState<FileInfo[]>([])
  const [selectedModules, setSelectedModules] = useState<Set<string>>(new Set())
  const [scanning, setScanning] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [scanLoaded, setScanLoaded] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [importText, setImportText] = useState('')
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState('')
  const [importMsgType, setImportMsgType] = useState<'ok' | 'err'>('ok')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadScanList = useCallback(() => {
    api.listScans().then(res => {
      setScanList(res.scans as ScanInfo[])
    }).catch(() => {})
  }, [])

  const loadModules = useCallback(async (sid: string) => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
    setLoading(true)
    setError('')
    setScanLoaded(false)
    try {
      const status = await api.getScanStatus(sid)
      setScan(status)

      if (status.status === 'completed') {
        const data = await api.getModules(sid)
        setModules(data.modules || [])
        setFiles(data.files || [])
        setSelectedModules(new Set((data.modules || []).map(m => m.id)))
        setLastScan(sid)
        setScanLoaded(true)
      } else if (status.status === 'scanning' || status.status === 'pending') {
        pollTimerRef.current = setTimeout(() => loadModules(sid), 1500)
        return
      } else if (status.status === 'failed') {
        setError(status.total_files === 0 ? t('scan.noFiles') : t('scan.failed'))
        setScanLoaded(true)
      } else {
        setScanLoaded(true)
      }
    } catch (e: any) {
      setError(e.message)
      setScanLoaded(true)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    api.getConfig().then(cfg => {
      if (cfg.project.root) setProjectRoot(cfg.project.root)
    }).catch(() => {})
    loadScanList()
  }, [loadScanList])

  useEffect(() => {
    if (scanId) {
      loadModules(scanId)
    } else {
      setScanLoaded(true)
    }
  }, [scanId, loadModules])

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
    }
  }, [])

  const startScan = async () => {
    if (!projectRoot.trim()) { setError(t('scan.projectRootRequired')); return }
    setScanning(true)
    setError('')
    try {
      const res = await api.scanProject(projectRoot.trim())
      setScanId(res.scan_id)
      setScanLoaded(false)
      await pollScan(res.scan_id)
    } catch (e: any) {
      setError(e.message)
    }
    setScanning(false)
  }

  const pollScan = async (sid: string): Promise<void> => {
    return new Promise(resolve => {
      const check = async () => {
        if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
        try {
          const status = await api.getScanStatus(sid)
          setScan(status)
          if (status.status === 'completed') {
            const data = await api.getModules(sid)
            setModules(data.modules)
            setFiles(data.files)
            setSelectedModules(new Set(data.modules.map(m => m.id)))
            setLastScan(sid)
            loadScanList()
            setScanLoaded(true)
            resolve()
          } else if (status.status === 'failed') {
            setError(status.total_files === 0 ? t('scan.noFiles') : t('scan.failed'))
            setScanLoaded(true)
            resolve()
          } else {
            pollTimerRef.current = setTimeout(check, 800)
          }
        } catch {
          pollTimerRef.current = setTimeout(check, 800)
        }
      }
      check()
    })
  }

  const clearScan = () => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
    setScanId(null)
    setScan(null)
    setModules([])
    setFiles([])
    setSelectedModules(new Set())
    setScanLoaded(false)
    setError('')
    try { localStorage.removeItem(LAST_SCAN_KEY) } catch {}
  }

  const switchScan = (sid: string) => {
    if (sid === scanId) return
    setScanId(sid)
    setModules([])
    setFiles([])
    setSelectedModules(new Set())
    setScanLoaded(false)
    setLastScan(sid)
  }

  const deleteScanEntry = async (sid: string) => {
    try {
      await api.deleteScan(sid)
      if (scanId === sid) {
        const remaining = scanList.filter(s => s.id !== sid)
        const next = remaining[0]?.id || null
        setScanId(next)
        setModules([])
        setFiles([])
        setScanLoaded(false)
        if (next) setLastScan(next)
        else { try { localStorage.removeItem(LAST_SCAN_KEY) } catch {} }
      }
      loadScanList()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const toggleModule = (id: string) => {
    const next = new Set(selectedModules)
    if (next.has(id)) next.delete(id); else next.add(id)
    setSelectedModules(next)
  }

  const toggleAll = () => {
    if (selectedModules.size === modules.length) {
      setSelectedModules(new Set())
    } else {
      setSelectedModules(new Set(modules.map(m => m.id)))
    }
  }

  const startAnalysis = async () => {
    if (!scanId || selectedModules.size === 0) return
    setAnalyzing(true)
    try {
      await api.startAnalysis(scanId, Array.from(selectedModules))
      nav(`/analysis/${scanId}`)
    } catch (e: any) {
      setError(e.message)
    }
    setAnalyzing(false)
  }

  const viewResults = () => {
    if (scanId) nav(`/results/${scanId}`)
  }

  const handleImport = async () => {
    if (!importText.trim()) {
      setImportMsg(t('scan.importError') + ': ' + t('scan.importHint'))
      setImportMsgType('err')
      return
    }
    setImporting(true)
    setImportMsg('')
    try {
      let report: any
      try {
        report = JSON.parse(importText)
      } catch {
        setImportMsg(t('scan.importError') + ': JSON 格式无效')
        setImportMsgType('err')
        setImporting(false)
        return
      }
      const res = await api.importReport(report)
      if (!res.scan_id) {
        setImportMsg(t('scan.importAllFixed', { count: res.already_fixed ?? 0 }))
        setImportMsgType('ok')
        setImporting(false)
        return
      }
      let msg = t('scan.importSuccess', { count: res.issues_imported })
      if (res.already_fixed) {
        msg += `，${t('scan.importAlreadyFixed', { count: res.already_fixed })}`
      }
      setImportMsg(msg)
      setImportMsgType('ok')
      setShowImport(false)
      setImportText('')
      loadScanList()
      setScanId(res.scan_id)
      setLastScan(res.scan_id)
      setTimeout(() => nav(`/results/${res.scan_id}`), 800)
    } catch (e: any) {
      setImportMsg(`${t('scan.importError')}: ${e.message}`)
      setImportMsgType('err')
    }
    setImporting(false)
  }

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      setImportText(String(reader.result || ''))
    }
    reader.readAsText(file)
  }

  const groupedFiles: Record<string, FileInfo[]> = {}
  files.forEach(f => {
    const dir = f.relative_path.includes('/')
      ? f.relative_path.split('/').slice(0, -1).join('/')
      : '(root)'
    if (!groupedFiles[dir]) groupedFiles[dir] = []
    groupedFiles[dir].push(f)
  })

  const moduleFileMap: Record<string, string[]> = {}
  modules.forEach(m => { moduleFileMap[m.id] = m.files })

  return (
    <div className="page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1>{t('scan.title')}</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {scanList.length > 0 && (
            <div className="history-bar">
              {scanList.map(s => (
                <span key={s.id} className={`history-tag ${s.id === scanId ? 'active' : ''}`}
                  onClick={() => switchScan(s.id)}
                  title={`${s.project_root} - ${t(`scanStatus.${s.status}`)} (${s.issue_count ?? 0} ${t('scan.issues')})`}
                >
                  {s.name || `#${s.id.slice(0, 8)}`}
                  <span className="history-count">{s.issue_count ?? 0}</span>
                  <span className="history-del" onClick={(e) => {
                    e.stopPropagation()
                    deleteScanEntry(s.id)
                  }}>&times;</span>
                </span>
              ))}
            </div>
          )}
          {scanId && modules.length > 0 && (
            <button onClick={viewResults} style={{ fontSize: 13 }}>{t('scan.viewResults')}</button>
          )}
          <button onClick={() => { setShowImport(true); setImportMsg(''); setImportText('') }} style={{ fontSize: 13 }}>
            {t('scan.importReport')}
          </button>
          {scanId && (
            <button onClick={clearScan} style={{ fontSize: 13 }}>{t('scan.newScan')}</button>
          )}
        </div>
      </div>

      {showImport && (
        <div className="import-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowImport(false) }}>
          <div className="import-modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>{t('scan.importTitle')}</h3>
              <button onClick={() => setShowImport(false)} style={{ fontSize: 13, padding: '4px 8px' }}>&times;</button>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
              {t('scan.importHint')}
            </div>
            <details style={{ marginBottom: 12, fontSize: 12 }}>
              <summary style={{ cursor: 'pointer', color: 'var(--accent)' }}>
                {lang === 'zh' ? '查看报告格式示例' : 'View format example'}
              </summary>
              <pre style={{
                background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6,
                padding: 10, fontSize: 11, overflow: 'auto', maxHeight: 200, margin: '8px 0 0',
              }}>{`{
  "project_root": "D:/your-cpp-project",
  "report_name": "可选：报告名称",
  "issues": [
    {
      "file_path": "src/foo.cpp",
      "severity": "high",
      "category": "memory_safety",
      "title": "问题标题",
      "description": "详细描述",
      "line_start": 10,
      "line_end": 12,
      "original_code": "delete m_connections;",
      "suggested_code": "delete[] m_connections;",
      "rule_reference": "C++ Core Guidelines"
    }
  ]
}`}</pre>
            </details>
            <textarea
              value={importText}
              onChange={e => setImportText(e.target.value)}
              placeholder={t('scan.importPlaceholder')}
              style={{ width: '100%', height: 220, fontFamily: 'monospace', fontSize: 12, resize: 'vertical' }}
            />
            <input type="file" ref={fileInputRef} accept=".json,.txt" style={{ display: 'none' }} onChange={handleImportFile} />
            <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
              <button className="primary" onClick={handleImport} disabled={importing}>
                {importing ? t('scan.starting') : t('scan.importBtn')}
              </button>
              <button onClick={() => fileInputRef.current?.click()}>{t('scan.importFile')}</button>
              <button onClick={() => setShowImport(false)}>{t('scan.importCancel')}</button>
            </div>
            {importMsg && (
              <div style={{ marginTop: 12, fontSize: 13, color: importMsgType === 'err' ? 'var(--red)' : 'var(--green)' }}>
                {importMsg}
              </div>
            )}
          </div>
        </div>
      )}

      {loading && !scanLoaded && (
        <div style={{ color: 'var(--text-secondary)', padding: 40, textAlign: 'center' }}>
          {t('scan.loadingData')}
        </div>
      )}

      {error && (
        <div style={{ color: 'var(--red)', margin: '8px 0 16px', fontSize: 13, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, border: '1px solid var(--red)' }}>
          {error}
        </div>
      )}

      {!scanId && (
        <div style={{ maxWidth: 500 }}>
          <div className="form-group">
            <label>{t('scan.projectRoot')}</label>
            <input value={projectRoot} onChange={e => setProjectRoot(e.target.value)}
              placeholder="e.g. D:/projects/my-cpp-app" style={{ width: '100%' }} />
          </div>
          <button className="primary" onClick={startScan} disabled={scanning}>
            {scanning ? t('scan.scanning') : t('scan.scanProject')}
          </button>
        </div>
      )}

      {scanning && (
        <div style={{ color: 'var(--text-secondary)', padding: 20, textAlign: 'center' }}>
          {t('scan.scanningFiles')}
        </div>
      )}

      {scanId && scanLoaded && modules.length === 0 && !error && !loading && (
        <div style={{ color: 'var(--text-secondary)', padding: 40, textAlign: 'center' }}>
          <p>{t('scan.noData')}</p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 12 }}>
            <button className="primary" onClick={viewResults}>{t('scan.viewReport')}</button>
            <button onClick={clearScan}>{t('scan.startNew')}</button>
          </div>
        </div>
      )}

      {scanId && modules.length > 0 && (
        <div className="scan-results">
          <div style={{ marginBottom: 16 }}>
            <span style={{ color: 'var(--text-secondary)' }}>
              {scan?.total_files} {t('scan.files')} &middot; {modules.length} {t('scan.modules')}
              &middot; {t('scan.status')}: {t(`scanStatus.${scan?.status || 'pending'}`)}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 24 }}>
            <div style={{ flex: '0 0 300px', borderRight: '1px solid var(--border)', paddingRight: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <strong>{t('scan.modules')}</strong>
                <button onClick={toggleAll} style={{ fontSize: 12, padding: '4px 8px' }}>
                  {selectedModules.size === modules.length ? t('scan.deselectAll') : t('scan.selectAll')}
                </button>
              </div>
              <div className="module-list">
                {modules.map(m => (
                  <label key={m.id} className="module-item" onClick={() => toggleModule(m.id)}>
                    <input type="checkbox" checked={selectedModules.has(m.id)} onChange={() => {}} />
                    <div>
                      <div className="module-name">{m.name}</div>
                      <div className="module-meta">
                        {m.files.length} {t('scan.files')} &middot; ~{m.estimated_tokens.toLocaleString()} {t('scan.tokens')}
                        {m.dependencies.length > 0 && <> &middot; {m.dependencies.length} {t('scan.deps')}</>}
                      </div>
                    </div>
                  </label>
                ))}
              </div>

              <button
                className="primary"
                style={{ marginTop: 16, width: '100%' }}
                onClick={startAnalysis}
                disabled={analyzing || selectedModules.size === 0}
              >
                {analyzing ? t('scan.starting') : t('scan.analyze', { count: selectedModules.size })}
              </button>
            </div>

            <div style={{ flex: 1 }}>
              <strong style={{ marginBottom: 12, display: 'block' }}>{t('scan.fileTree')}</strong>
              <div className="file-tree">
                {Object.entries(groupedFiles).map(([dir, dirFiles]) => (
                  <div key={dir} style={{ marginBottom: 12 }}>
                    <div className="tree-dir">{dir}/</div>
                    {dirFiles.map(f => {
                      const belongsTo = modules.filter(m =>
                        (moduleFileMap[m.id] || []).includes(f.path))
                      return (
                        <div key={f.relative_path} className="tree-file">
                          <span className="file-icon">{f.extension.startsWith('.h') ? 'H' : 'C'}</span>
                          <span>{f.relative_path.split('/').pop()}</span>
                          <span style={{ color: 'var(--text-secondary)', fontSize: 12, marginLeft: 8 }}>
                            {f.lines} {t('scan.lines')}
                          </span>
                          {belongsTo.map(m => (
                            <span key={m.id} className="badge low" style={{ marginLeft: 4 }}>
                              {m.name}
                            </span>
                          ))}
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
        .module-list { max-height: 400px; overflow-y: auto; }
        .module-item {
          display: flex; align-items: flex-start; gap: 8px; padding: 8px;
          border: 1px solid var(--border); border-radius: 6px; margin-bottom: 6px;
          cursor: pointer; transition: background 0.15s;
        }
        .module-item:hover { background: var(--bg-tertiary); }
        .module-name { font-size: 14px; font-weight: 600; }
        .module-meta { font-size: 12px; color: var(--text-secondary); }
        .tree-dir { font-size: 13px; color: var(--accent); font-weight: 600; margin-bottom: 4px; }
        .tree-file {
          display: flex; align-items: center; padding: 3px 0 3px 16px;
          font-size: 13px;
        }
        .file-icon {
          display: inline-flex; align-items: center; justify-content: center;
          width: 18px; height: 18px; border-radius: 3px; font-size: 10px; font-weight: 700;
          background: var(--bg-tertiary); color: var(--text-secondary); margin-right: 6px;
        }
        .history-bar { display: flex; gap: 4px; flex-wrap: wrap; }
        .history-tag {
          display: inline-flex; align-items: center; gap: 4px;
          padding: 3px 8px; border-radius: 4px; font-size: 12px;
          background: var(--bg-tertiary); border: 1px solid var(--border);
          cursor: pointer; color: var(--text-secondary);
        }
        .history-tag:hover { color: var(--text); border-color: var(--text-secondary); }
        .history-tag.active { color: var(--accent); border-color: var(--accent); }
        .history-count {
          font-size: 10px; background: var(--bg); border-radius: 8px;
          padding: 0 5px; color: var(--text-secondary);
        }
        .history-del { font-size: 14px; color: var(--red); line-height: 1; }
        .history-del:hover { color: #ff6b6b; }
        .import-overlay {
          position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.5); display: flex; align-items: center;
          justify-content: center; z-index: 1000;
        }
        .import-modal {
          background: var(--bg-secondary); border: 1px solid var(--border);
          border-radius: 8px; padding: 20px; width: 640px; max-width: 90vw;
          box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }
      `}</style>
    </div>
  )
}
