import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAppStore, type SupportedLocale } from '../store/appStore'

export function SettingsPage() {
  const { t, i18n } = useTranslation()
  const locale = useAppStore((state) => state.locale)
  const accessToken = useAppStore((state) => state.accessToken)
  const setLocale = useAppStore((state) => state.setLocale)
  const setAccessToken = useAppStore((state) => state.setAccessToken)
  const clearSession = useAppStore((state) => state.clearSession)

  const [tokenDraft, setTokenDraft] = useState(accessToken ?? '')

  const applyLocale = (nextLocale: SupportedLocale): void => {
    setLocale(nextLocale)
    void i18n.changeLanguage(nextLocale)
  }

  const saveToken = (): void => {
    const token = tokenDraft.trim()
    setAccessToken(token.length > 0 ? token : null)
  }

  return (
    <section className="rounded-lg border border-border bg-surface p-8 shadow-card">
      <h1 className="text-2xl font-semibold tracking-tight">{t('settings.title')}</h1>
      <p className="mt-3 text-sm text-fg/75 sm:text-base">{t('settings.description')}</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-md border border-border bg-secondary/40 p-4">
          <p className="text-sm font-medium text-fg">{t('settings.language')}</p>
          <p className="mt-1 text-xs text-fg/70">{t('settings.languageHelper')}</p>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => applyLocale('en')}
              className={`rounded-md px-3 py-2 text-sm ${locale === 'en' ? 'bg-primary text-primary-foreground' : 'bg-surface text-fg/80'}`}
            >
              English
            </button>
            <button
              type="button"
              onClick={() => applyLocale('es')}
              className={`rounded-md px-3 py-2 text-sm ${locale === 'es' ? 'bg-primary text-primary-foreground' : 'bg-surface text-fg/80'}`}
            >
              Español
            </button>
          </div>
        </div>

        <div className="rounded-md border border-border bg-secondary/40 p-4">
          <p className="text-sm font-medium text-fg">{t('settings.sessionToken')}</p>
          <div className="mt-3 flex flex-col gap-2">
            <input
              value={tokenDraft}
              onChange={(event) => setTokenDraft(event.target.value)}
              placeholder={t('settings.tokenPlaceholder')}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none ring-primary/40 placeholder:text-fg/45 focus:ring"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={saveToken}
                className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
              >
                {t('settings.saveToken')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setTokenDraft('')
                  clearSession()
                }}
                className="rounded-md bg-danger px-3 py-2 text-sm font-medium text-primary-foreground"
              >
                {t('settings.clearToken')}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
