import React from 'react'
import { DiffEditor } from '@monaco-editor/react'
import { useI18n } from '../i18n'

interface Props {
  original: string
  modified: string
  lineStart?: number
  lineEnd?: number
}

export default function DiffViewer({ original, modified, lineStart = 1, lineEnd }: Props) {
  const { t } = useI18n()
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
      <div style={{
        fontSize: 12, color: 'var(--text-secondary)',
        padding: '6px 12px', background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border)',
      }}>
        {t('results.lineLabel', { start: lineStart, end: lineEnd && lineEnd !== lineStart ? ` - ${lineEnd}` : '' })}
      </div>
      <DiffEditor
        height="240px"
        language="cpp"
        original={original}
        modified={modified}
        theme="vs-dark"
        options={{
          readOnly: true,
          renderSideBySide: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          lineNumbers: 'off',
          folding: false,
          renderOverviewRuler: false,
        }}
      />
    </div>
  )
}
