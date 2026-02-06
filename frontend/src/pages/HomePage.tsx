import { useTranslation } from 'react-i18next'

export function HomePage() {
  const { t } = useTranslation()

  return (
    <section className="rounded-lg border border-border bg-surface p-8 shadow-card">
      <h1 className="text-3xl font-semibold tracking-tight">{t('home.title')}</h1>
      <p className="mt-3 max-w-2xl text-sm text-fg/75 sm:text-base">
        {t('home.description')}
      </p>
    </section>
  )
}
