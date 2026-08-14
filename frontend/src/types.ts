export interface ScanInfo {
  id: string
  name?: string
  project_root: string
  status: string
  total_files: number
  total_modules: number
  modules_completed: number
  created_at: string
  completed_at: string | null
  issue_count?: number
}

export interface ModuleInfo {
  id: string
  name: string
  files: string[]
  dependencies: string[]
  estimated_tokens: number
  partition_count: number
}

export interface FileInfo {
  id: number
  scan_id: string
  path: string
  relative_path: string
  size_bytes: number
  lines: number
  extension: string
}

export interface CodeIssue {
  id: string
  scan_id: string
  module_id: string
  file_path: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  category: string
  title: string
  description: string
  title_zh?: string
  description_zh?: string
  line_start: number
  line_end: number
  original_code: string
  suggested_code: string
  rule_reference: string
  status: 'pending' | 'accepted' | 'rejected' | 'applied' | 'failed'
  created_at: string
}

export interface IssueSummary {
  total: number
  by_severity: Record<string, number>
  pending: number
  accepted: number
  rejected: number
}

export interface ProviderInfo {
  id: string
  name: string
  default_model: string
}

export interface AppConfig {
  language?: string
  api: {
    provider: string
    api_key: string
    api_key_set?: boolean
    model: string
    base_url: string
    max_tokens: number
  }
  project: {
    root: string
    compile_commands: string
    exclude_dirs: string[]
    exclude_patterns: string[]
  }
  analysis: {
    static_check: boolean
    dynamic_check: boolean
    tools: { clang_tidy: boolean; cppcheck: boolean }
    rules: string[]
  }
  chunking: {
    strategy: string
    max_tokens_per_batch: number
    max_file_tokens: number
  }
  batch: {
    concurrent_modules: number
    rate_limit_rpm: number
  }
}
