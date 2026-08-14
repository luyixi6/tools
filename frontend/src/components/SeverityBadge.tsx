import React from 'react'
import { useI18n } from '../i18n'

interface Props {
  severity: 'critical' | 'high' | 'medium' | 'low'
}

const shortLabels: Record<string, string> = {
  critical: 'CRIT', high: 'HIGH', medium: 'MED', low: 'LOW',
}

export default function SeverityBadge({ severity }: Props) {
  const { t } = useI18n()
  const label = t(`severity.${severity}`)
  return (
    <span className={`badge ${severity}`} title={label}>
      {label === `severity.${severity}` ? (shortLabels[severity] ?? severity.toUpperCase()) : label}
    </span>
  )
}
