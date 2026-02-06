import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function NotFoundPage() {
  const { t } = useTranslation()

  return (
    <section className="rounded-lg border border-danger/30 bg-surface p-8 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-danger">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{t('notFound.title')}</h1>
      <p className="mt-3 text-sm text-fg/75 sm:text-base">
        {t('notFound.description')}
      </p>
      <Link to="/" className="mt-5 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
        {t('notFound.goHome')}
      </Link>
    </section>
  )
}
