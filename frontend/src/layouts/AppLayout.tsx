import { useEffect } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAppStore, type SupportedLocale } from '../store/appStore'

function linkClass(isActive: boolean): string {
  return [
    'rounded-md px-3 py-2 text-sm font-medium transition',
    isActive
      ? 'bg-primary text-primary-foreground shadow-sm'
      : 'text-fg/70 hover:bg-secondary hover:text-fg',
  ].join(' ')
}

export function AppLayout() {
  const { t, i18n } = useTranslation()
  const setLocale = useAppStore((state) => state.setLocale)

  useEffect(() => {
    const normalized = (i18n.resolvedLanguage ?? 'en').startsWith('es') ? 'es' : 'en'
    setLocale(normalized as SupportedLocale)
  }, [i18n.resolvedLanguage, setLocale])

  const navItems = [
    { to: '/', label: t('nav.home') },
    { to: '/projects', label: t('nav.projects') },
    { to: '/settings', label: t('nav.settings') },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-b from-bg to-secondary/60">
      <header className="border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">SpecGen</p>
            <p className="text-sm text-fg/70">{t('layout.subtitle')}</p>
          </div>
          <nav className="flex items-center gap-1 rounded-lg border border-border bg-surface p-1">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => linkClass(isActive)}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
