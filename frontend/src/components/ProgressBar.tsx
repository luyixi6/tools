import React from 'react'

interface Props {
  value: number
  max: number
  label?: string
}

export default function ProgressBar({ value, max, label }: Props) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ margin: '8px 0' }}>
      {label && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>{label}</div>}
      <div style={{ background: 'var(--bg-tertiary)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: 'var(--accent)',
          transition: 'width 0.3s', borderRadius: 4,
        }} />
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2, textAlign: 'right' }}>
        {value}/{max} ({pct}%)
      </div>
    </div>
  )
}
