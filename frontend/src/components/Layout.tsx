import React, { useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useI18n, Lang } from '../i18n'
import { api } from '../api'
import './Layout.css'

export default function Layout() {
  const loc = useLocation()
  const { lang, setLang, t } = useI18n()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const isActive = (path: string) => loc.pathname.startsWith(path)

  const changeLang = (l: Lang) => {
    setLang(l)
    setSettingsOpen(false)
    api.updateConfig({ language: l } as any).catch(() => {})
  }

  return (
    <div className="layout">
      <nav className="nav">
        <div className="nav-brand">CPP Inspector</div>
        <div className="nav-links">
          <NavLink to="/" className={isActive('/') && !isActive('/scan') && !isActive('/analysis') && !isActive('/results') ? 'active' : ''}>
            {t('nav.config')}
          </NavLink>
          <NavLink to="/scan" className={isActive('/scan') || isActive('/analysis') || isActive('/results') ? 'active' : ''}>
            {t('nav.scan')}
          </NavLink>
        </div>
        <div className="nav-right">
          <div className="settings-wrapper">
            <button
              className="settings-btn"
              onClick={() => setSettingsOpen(o => !o)}
              title={t('settings.title')}
            >
              ⚙
            </button>
            {settingsOpen && (
              <div className="settings-dropdown">
                <div className="settings-label">{t('settings.language')}</div>
                <div className="settings-options">
                  <button
                    className={`lang-option ${lang === 'en' ? 'active' : ''}`}
                    onClick={() => changeLang('en')}
                  >
                    English
                  </button>
                  <button
                    className={`lang-option ${lang === 'zh' ? 'active' : ''}`}
                    onClick={() => changeLang('zh')}
                  >
                    中文
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
