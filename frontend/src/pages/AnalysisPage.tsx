import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useI18n } from '../i18n'
import ProgressBar from '../components/ProgressBar'

interface ProgressData {
  type: string
  scan_id: string
  total_modules?: number
  modules_completed?: number
  total_issues?: number
  current_module?: { module_id: string; module_name: string; status: string; total_files: number; files_completed: number; issues_found: number }
  message?: string
}

export default function AnalysisPage() {
  const { scanId } = useParams<{ scanId: string }>()
  const nav = useNavigate()
  const { t } = useI18n()
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [completed, setCompleted] = useState(false)
  const [totalIssues, setTotalIssues] = useState(0)
  const [log, setLog] = useState<string[]>([])

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wsRef = useRef<(() => void) | null>(null)
  const mountedRef = useRef(true)
  const finishedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    finishedRef.current = false
    if (!scanId) return

    const clearTimer = () => {
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    }

    const startPoll = () => {
      if (timerRef.current) return
      timerRef.current = setInterval(async () => {
        try {
          const s = await api.getScanStatus(scanId)
          if (s.status === 'completed' || s.status === 'failed') {
            clearTimer()
            finish(s.status === 'completed' ? s.total_files : 0)
          }
        } catch {}
      }, 2000)
    }

    const finish = (issues: number) => {
      if (finishedRef.current || !mountedRef.current) return
      finishedRef.current = true
      clearTimer()
      if (wsRef.current) { wsRef.current(); wsRef.current = null }
      setTotalIssues(issues)
      setCompleted(true)
      if (issues > 0) {
        timeoutRef.current = setTimeout(() => {
          if (mountedRef.current) nav(`/results/${scanId}`)
        }, 1200)
      }
    }

    const connectWs = () => {
      try {
        wsRef.current = api.connectWs(scanId, (data: any) => {
          if (!mountedRef.current) return
          const d = data as ProgressData
          setProgress(d)
          setLog(prev => [...prev.slice(-50), d.message || d.type])
          if (d.type === 'analysis_complete') {
            finish(d.total_issues || 0)
          } else if (d.type === 'analysis_error') {
            clearTimer()
            setCompleted(true)
          }
        })
      } catch {
        startPoll()
      }
    }

    const checkStatus = async () => {
      try {
        const s = await api.getScanStatus(scanId)
        if (!mountedRef.current) return
        if (s.status === 'completed') {
          const issues = await api.getIssues(scanId)
          finish(issues.summary.total)
          return
        }
        if (s.status === 'scanning' || s.status === 'pending') {
          timeoutRef.current = setTimeout(checkStatus, 1000)
          return
        }
        connectWs()
        startPoll()
      } catch {
        timeoutRef.current = setTimeout(checkStatus, 2000)
      }
    }

    checkStatus()

    return () => {
      mountedRef.current = false
      clearTimer()
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null }
      if (wsRef.current) { wsRef.current(); wsRef.current = null }
    }
  }, [scanId])

  const total = progress?.total_modules || 0
  const done = progress?.modules_completed || 0
  const cur = progress?.current_module

  return (
    <div className="page" style={{ maxWidth: 700 }}>
      <h1 style={{ marginBottom: 24 }}>{t('analysis.title')}</h1>

      {!completed && (
        <>
          <ProgressBar value={done} max={total || 1} label={t('analysis.modules', { done, total })} />
          {cur && (
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
              border: '1px solid var(--border)', marginTop: 16,
            }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>
                {t('analysis.current', { name: cur.module_name })}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {t('analysis.status', { status: t(`scanStatus.${cur.status}`) })} &middot; {t('analysis.files', { done: cur.files_completed, total: cur.total_files })}
                &middot; {t('analysis.issuesFound', { count: cur.issues_found })}
              </div>
            </div>
          )}
        </>
      )}

      {completed && (
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 8, padding: 24,
          border: '1px solid var(--border)', textAlign: 'center',
        }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>&#10003;</div>
          <h2>{t('analysis.complete')}</h2>
          <p style={{ color: 'var(--text-secondary)', margin: '8px 0 16px' }}>
            {t('analysis.issuesTotal', { count: totalIssues })}
          </p>
          {totalIssues > 0 && (
            <button className="primary" onClick={() => nav(`/results/${scanId}`)} style={{ fontSize: 16, padding: '12px 32px' }}>
              {t('analysis.viewResults')}
            </button>
          )}
        </div>
      )}

      {log.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <strong style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{t('analysis.log')}</strong>
          <div style={{
            background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6,
            padding: 12, marginTop: 8, maxHeight: 200, overflow: 'auto',
            fontFamily: 'monospace', fontSize: 12,
          }}>
            {log.map((l, i) => (
              <div key={i} style={{ color: 'var(--text-secondary)', padding: '1px 0' }}>{l}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
