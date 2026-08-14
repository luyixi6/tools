import type { ScanInfo, ModuleInfo, FileInfo, CodeIssue, IssueSummary, ProviderInfo, AppConfig } from './types'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  health: () => request<{ status: string; version: string }>(`${BASE}/health`),

  providers: () => request<{ providers: ProviderInfo[] }>(`${BASE}/providers`),

  listScans: () => request<{ scans: ScanInfo[] }>(`${BASE}/scans`),

  getReportSchema: () =>
    request<{ schema_version: string; description: string; example: any }>(`${BASE}/report/schema`),

  importReport: (report: any) =>
    request<{ scan_id: string; name: string; issues_imported: number; skipped: number; already_fixed?: number; message?: string }>(
      `${BASE}/report/import`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report),
      }
    ),

  exportReport: (scanId: string) =>
    request<any>(`${BASE}/report/export/${scanId}`),

  deleteScan: (scanId: string) =>
    request<{ scan_id: string; deleted: boolean }>(`${BASE}/scans/${scanId}`, { method: 'DELETE' }),

  getConfig: () => request<AppConfig>(`${BASE}/config`),

  updateConfig: (data: Partial<AppConfig>) =>
    request<{ status: string }>(`${BASE}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  scanProject: (projectRoot: string) =>
    request<{ scan_id: string; status: string }>(`${BASE}/project/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_root: projectRoot }),
    }),

  getScanStatus: (scanId: string) =>
    request<ScanInfo>(`${BASE}/project/status/${scanId}`),

  getModules: (scanId: string) =>
    request<{
      scan: ScanInfo
      modules: ModuleInfo[]
      files: FileInfo[]
    }>(`${BASE}/project/modules/${scanId}`),

  startAnalysis: (scanId: string, moduleIds: string[]) =>
    request<{ scan_id: string; status: string; selected_modules: number }>(
      `${BASE}/analyze/start`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_id: scanId, module_ids: moduleIds }),
      }
    ),

  getIssues: (scanId: string, params?: { module_id?: string; severity?: string; status?: string }) => {
    const qs = new URLSearchParams()
    if (params?.module_id) qs.set('module_id', params.module_id)
    if (params?.severity) qs.set('severity', params.severity)
    if (params?.status) qs.set('status', params.status)
    const q = qs.toString()
    return request<{ scan_id: string; issues: CodeIssue[]; summary: IssueSummary }>(
      `${BASE}/issues/${scanId}${q ? '?' + q : ''}`
    )
  },

  acceptIssue: (issueId: string) =>
    request<{ issue_id: string; success: boolean; file_path: string; error?: string; backup_path?: string }>(
      `${BASE}/issues/${issueId}/accept`, { method: 'POST' }
    ),

  rejectIssue: (issueId: string) =>
    request<{ issue_id: string; status: string }>(`${BASE}/issues/${issueId}/reject`, { method: 'POST' }),

  revertIssue: (issueId: string) =>
    request<{ issue_id: string; success: boolean; error?: string }>(
      `${BASE}/issues/${issueId}/revert`, { method: 'POST' }
    ),

  batchIssues: (issueIds: string[], action: 'accept' | 'reject') =>
    request<{ results: { issue_id: string; success: boolean; status: string; error?: string }[] }>(
      `${BASE}/issues/batch`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue_ids: issueIds, action }),
      }
    ),

  applyFixes: (scanId: string) =>
    request<{ scan_id: string; results: { issue_id: string; success: boolean; error?: string; backup_path?: string }[] }>(
      `${BASE}/issues/apply`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_id: scanId }),
      }
    ),

  connectWs: (scanId: string, onMessage: (data: unknown) => void): (() => void) => {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/ws/scan/${scanId}`)
    ws.onmessage = (e) => onMessage(JSON.parse(e.data))
    ws.onerror = (e) => console.error('WebSocket error:', e)
    return () => ws.close()
  },
}
