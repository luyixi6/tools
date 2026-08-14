import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { ProviderInfo } from '../types'

export default function ConfigPage() {
  const nav = useNavigate()
  const { t } = useI18n()
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [provider, setProvider] = useState('anthropic')
  const [apiKey, setApiKey] = useState('')
  const [apiKeySet, setApiKeySet] = useState(false)
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [projectRoot, setProjectRoot] = useState('')
  const [maxTokens, setMaxTokens] = useState(8192)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [msgType, setMsgType] = useState<'ok' | 'err'>('ok')

  useEffect(() => {
    Promise.all([api.providers(), api.getConfig()]).then(([prov, cfg]) => {
      setProviders(prov.providers)
      setProvider(cfg.api.provider)
      setApiKeySet(cfg.api.api_key_set || false)
      setModel(cfg.api.model || '')
      setBaseUrl(cfg.api.base_url || '')
      setMaxTokens(cfg.api.max_tokens)
      setProjectRoot(cfg.project.root || '')
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const selected = providers.find(p => p.id === provider)

  const save = async () => {
    setSaving(true)
    setMsg('')
    try {
      const apiPayload: any = { provider, model, base_url: baseUrl, max_tokens: maxTokens }
      if (apiKey.trim()) {
        apiPayload.api_key = apiKey.trim()
      }
      await api.updateConfig({
        api: apiPayload,
        project: { root: projectRoot } as any,
      } as any)
      setApiKey('')
      setApiKeySet(true)
      setMsg(t('config.saved'))
      setMsgType('ok')
    } catch (e: any) {
      setMsg(`${t('common.error')} ${e.message}`)
      setMsgType('err')
    }
    setSaving(false)
  }

  const goScan = () => nav('/scan')

  if (loading) return <div className="page">{t('common.loading')}</div>

  return (
    <div className="page" style={{ maxWidth: 600 }}>
      <h1 style={{ marginBottom: 24 }}>{t('config.title')}</h1>

      <div className="form-group">
        <label>{t('config.llmProvider')}</label>
        <select value={provider} onChange={e => {
          setProvider(e.target.value)
          const p = providers.find(x => x.id === e.target.value)
          if (p && !model) setModel(p.default_model)
        }}>
          {providers.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label>{t('config.apiKey')}</label>
        <input
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder={apiKeySet ? t('config.apiKeySetPlaceholder') : t('config.apiKeyPlaceholder')}
        />
        <span className="hint">
          {apiKeySet ? t('config.apiKeySet') : t('config.apiKeyPlaceholder')}
        </span>
      </div>

      <div className="form-group">
        <label>{t('config.model')}</label>
        <input value={model} onChange={e => setModel(e.target.value)}
          placeholder={selected?.default_model || t('config.model')} />
      </div>

      {provider !== 'anthropic' && (
        <div className="form-group">
          <label>{t('config.baseUrl')}</label>
          <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)}
            placeholder={t('config.baseUrlPlaceholder')} />
        </div>
      )}

      <div className="form-group">
        <label>{t('config.maxTokens')}</label>
        <input type="number" value={maxTokens} onChange={e => setMaxTokens(Number(e.target.value))} />
      </div>

      <div className="form-group">
        <label>{t('config.projectRoot')}</label>
        <input value={projectRoot} onChange={e => setProjectRoot(e.target.value)}
          placeholder="e.g. D:/projects/my-cpp-app" />
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
        <button onClick={save} disabled={saving}>{saving ? t('config.saving') : t('config.save')}</button>
        <button className="primary" onClick={goScan}>{t('config.goScan')} &rarr;</button>
      </div>

      {msg && (
        <div style={{ marginTop: 12, fontSize: 13, color: msgType === 'err' ? 'var(--red)' : 'var(--green)' }}>
          {msg}
        </div>
      )}

      <style>{`
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
        .form-group input, .form-group select { width: 100%; }
        .hint { font-size: 12px; color: var(--text-secondary); margin-top: 4px; display: block; }
      `}</style>
    </div>
  )
}
