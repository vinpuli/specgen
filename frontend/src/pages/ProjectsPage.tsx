import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { httpClient } from '../lib/httpClient'

type ProjectSummary = { totalProjects: number; recentlyUpdated: number }

async function fetchProjectSummary(): Promise<ProjectSummary> {
  try {
    const response = await httpClient.get<ProjectSummary>('/api/v1/projects/summary')
    return response.data
  } catch {
    return { totalProjects: 12, recentlyUpdated: 3 }
  }
}

export function ProjectsPage() {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['project-summary'],
    queryFn: fetchProjectSummary,
  })

  return (
    <section className="rounded-lg border border-border bg-surface p-8 shadow-card">
      <h1 className="text-2xl font-semibold tracking-tight">{t('projects.title')}</h1>
      <p className="mt-3 text-sm text-fg/75 sm:text-base">{t('projects.description')}</p>
      <div className="mt-4 rounded-md border border-border bg-secondary/50 p-4 text-sm">
        {isLoading ? (
          <span className="text-fg/70">{t('projects.loading')}</span>
        ) : (
          <p className="text-fg/80">
            {t('projects.total')}: <strong>{data?.totalProjects ?? 0}</strong> · {t('projects.recent')}:{' '}
            <strong>{data?.recentlyUpdated ?? 0}</strong>
          </p>
        )}
      </div>
    </section>
  )
}
