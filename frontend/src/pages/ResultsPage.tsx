import React, { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { CodeIssue, IssueSummary } from '../types'
import SeverityBadge from '../components/SeverityBadge'
import DiffViewer from './DiffViewer'

export default function ResultsPage() {
  const { scanId } = useParams<{ scanId: string }>()
  const { t, lang } = useI18n()

  const issueTitle = (issue: CodeIssue) =>
    lang === 'zh' ? (issue.title_zh || issue.title) : issue.title
  const issueDesc = (issue: CodeIssue) =>
    lang === 'zh' ? (issue.description_zh || issue.description) : issue.description
  const [issues, setIssues] = useState<CodeIssue[]>([])
  const [summary, setSummary] = useState<IssueSummary | null>(null)
  const [selected, setSelected] = useState<CodeIssue | null>(null)
  const [filter, setFilter] = useState({ severity: '', status: 'pending' })
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok')

  const loadIssues = useCallback(async () => {
    if (!scanId) return
    try {
      const data = await api.getIssues(scanId, filter)
      setIssues(data.issues)
      setSummary(data.summary)
      const idSet = new Set(data.issues.map((i: CodeIssue) => i.id))
      setSelected(prev => {
        if (prev && idSet.has(prev.id)) {
          const updated = data.issues.find((i: CodeIssue) => i.id === prev.id)
          return updated || (data.issues.length > 0 ? data.issues[0] : null)
        }
        return data.issues.length > 0 ? data.issues[0] : null
      })
    } catch (e: any) {
      setMsg(e.message)
      setMsgType('err')
    }
    setLoading(false)
  }, [scanId, filter])

  useEffect(() => { loadIssues() }, [loadIssues])

  const accept = async (id: string) => {
    setMsg('')
    try {
      const res = await api.acceptIssue(id)
      if (res.success) {
        updateIssueStatus(id, 'applied')
        setMsg(t('results.applied'))
        setMsgType('ok')
      } else {
        setMsg(`${t('results.failedApply')} ${res.error || 'unknown'}`)
        setMsgType('err')
      }
    } catch (e: any) {
      setMsg(`${t('common.error')} ${e.message}`)
      setMsgType('err')
    }
  }

  const reject = async (id: string) => {
    await api.rejectIssue(id)
    updateIssueStatus(id, 'rejected')
    setMsg(t('results.rejected'))
    setMsgType('ok')
  }

  const revert = async (id: string) => {
    setMsg('')
    try {
      const res = await api.revertIssue(id)
      if ((res as any).success) {
        updateIssueStatus(id, 'pending')
        setMsg(t('results.reverted'))
        setMsgType('ok')
      } else {
        setMsg(`${t('results.failedApply')} ${(res as any).error || 'unknown'}`)
        setMsgType('err')
      }
    } catch (e: any) {
      setMsg(`${t('common.error')} ${e.message}`)
      setMsgType('err')
    }
  }

  const updateIssueStatus = (id: string, status: string) => {
    setIssues(prev => prev.map(i => i.id === id ? { ...i, status } as CodeIssue : i))
    setSelected(prev => prev?.id === id ? { ...prev, status } as CodeIssue : prev)
  }

  const exportReport = async () => {
    if (!scanId) return
    try {
      const report = await api.exportReport(scanId)
      const savedPath = (report as any).saved_path
      setMsg(savedPath ? `${t('results.exported')}: ${savedPath}` : t('results.exported'))
      setMsgType('ok')
    } catch (e: any) {
      setMsg(`${t('common.error')} ${e.message}`)
      setMsgType('err')
    }
  }

  if (loading) return <div className="page" style={{ color: 'var(--text-secondary)' }}>{t('results.loading')}</div>

  return (
    <div className="page results-page">
      <div className="results-header">
        <h1>{t('results.title')}</h1>
        <div className="summary-stats">
          {summary && (
            <>
              <span>{t('results.total')} <strong>{summary.total}</strong></span>
              {Object.entries(summary.by_severity).map(([sev, count]) =>
                count > 0 && <SeverityBadge key={sev} severity={sev as any} />
              )}
            </>
          )}
        </div>
      </div>

      <div className="results-toolbar">
        <div className="filter-group">
          <select value={filter.severity} onChange={e => setFilter(f => ({ ...f, severity: e.target.value }))}>
            <option value="">{t('results.allSeverities')}</option>
            <option value="critical">{t('severity.critical')}</option>
            <option value="high">{t('severity.high')}</option>
            <option value="medium">{t('severity.medium')}</option>
            <option value="low">{t('severity.low')}</option>
          </select>
          <select value={filter.status} onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}>
            <option value="">{t('results.allStatus')}</option>
            <option value="pending">{t('status.pending')}</option>
            <option value="applied">{t('status.applied')}</option>
            <option value="rejected">{t('status.rejected')}</option>
            <option value="failed">{t('status.failed')}</option>
          </select>
        </div>
        <div className="action-group">
          <button onClick={exportReport} style={{ fontSize: 13 }}>{t('results.exportReport')}</button>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            {t('results.hint')}
          </span>
        </div>
      </div>

      <div className="results-body">
        <div className="issue-list">
          {issues.length === 0 && (
            <div style={{ color: 'var(--text-secondary)', padding: 24, textAlign: 'center' }}>
              {t('results.noIssues')}
            </div>
          )}
          {issues.map(issue => (
            <div
              key={issue.id}
              className={`issue-item ${selected?.id === issue.id ? 'selected' : ''}`}
              onClick={() => setSelected(issue)}
            >
              <div className="issue-top">
                <SeverityBadge severity={issue.severity} />
                <span className={`issue-status status-${issue.status}`}>{t(`status.${issue.status}`)}</span>
              </div>
              <div className="issue-title">{issueTitle(issue)}</div>
              <div className="issue-file">
                {issue.file_path.split(/[\\/]/).pop()}:{issue.line_start}
              </div>
            </div>
          ))}
        </div>

        <div className="issue-detail">
          {selected ? (
            <>
              <div className="detail-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <SeverityBadge severity={selected.severity} />
                  <strong>{issueTitle(selected)}</strong>
                </div>
                <div className="detail-actions">
                  {selected.status === 'pending' && (
                    <>
                      <button className="primary" onClick={() => accept(selected.id)}>
                        {t('results.acceptApply')}
                      </button>
                      <button className="danger" onClick={() => reject(selected.id)}>{t('results.reject')}</button>
                    </>
                  )}
                  {selected.status === 'applied' && (
                    <button onClick={() => revert(selected.id)}>{t('results.revert')}</button>
                  )}
                  {selected.status === 'rejected' && (
                    <button className="primary" onClick={() => accept(selected.id)}>
                      {t('results.acceptApply')}
                    </button>
                  )}
                  {selected.status === 'failed' && (
                    <button className="primary" onClick={() => accept(selected.id)}>
                      {t('results.retry')}
                    </button>
                  )}
                </div>
              </div>

              <div className="detail-meta">
                <span>{t('results.file')} <code>{selected.file_path}</code></span>
                <span>{t('results.line')} {selected.line_start}-{selected.line_end}</span>
                <span>{t('results.category')} {t(`category.${selected.category}`)}</span>
                {selected.rule_reference && <span>{t('results.rule')} {selected.rule_reference}</span>}
              </div>

              <div className="detail-desc">
                {issueDesc(selected)}
              </div>

              {selected.original_code && selected.suggested_code && (
                <div className="detail-diff">
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                    {selected.status === 'applied' ? t('results.appliedChange') : t('results.suggestedFix')}
                  </div>
                  <DiffViewer
                    original={selected.original_code}
                    modified={selected.suggested_code}
                    lineStart={selected.line_start}
                    lineEnd={selected.line_end}
                  />
                </div>
              )}
            </>
          ) : (
            <div style={{ color: 'var(--text-secondary)', padding: 48, textAlign: 'center' }}>
              {t('results.selectIssue')}
            </div>
          )}
        </div>
      </div>

      {msg && (
        <div style={{
          position: 'fixed', bottom: 20, right: 20,
          background: msgType === 'err' ? '#da3633' : '#238636',
          color: '#fff', borderRadius: 8, padding: '12px 20px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.4)', fontSize: 14,
          zIndex: 100,
        }}>
          {msg}
        </div>
      )}

      <style>{`
        .results-page { display: flex; flex-direction: column; height: calc(100vh - 96px); }
        .results-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .summary-stats { display: flex; gap: 8px; align-items: center; }
        .results-toolbar { display: flex; justify-content: space-between; margin-bottom: 16px; align-items: center; }
        .filter-group { display: flex; gap: 8px; }
        .action-group { display: flex; gap: 8px; align-items: center; }
        .results-body { flex: 1; display: flex; gap: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
        .issue-list { flex: 0 0 340px; overflow-y: auto; background: var(--bg-secondary); }
        .issue-item { padding: 12px 16px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.1s; }
        .issue-item:hover { background: var(--bg-tertiary); }
        .issue-item.selected { background: var(--bg-tertiary); border-left: 3px solid var(--accent); }
        .issue-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .issue-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; line-height: 1.3; }
        .issue-file { font-size: 12px; color: var(--text-secondary); font-family: monospace; }
        .issue-status { font-size: 11px; text-transform: uppercase; }
        .status-pending { color: var(--orange); }
        .status-applied { color: var(--green); }
        .status-rejected { color: var(--red); }
        .status-failed { color: var(--red); }
        .issue-detail { flex: 1; overflow-y: auto; padding: 20px; }
        .detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .detail-actions { display: flex; gap: 8px; }
        .detail-meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; }
        .detail-meta code { background: var(--bg-tertiary); padding: 1px 6px; border-radius: 3px; }
        .detail-desc { font-size: 14px; line-height: 1.6; margin-bottom: 16px; padding: 12px; background: var(--bg-secondary); border-radius: 6px; }
      `}</style>
    </div>
  )
}
