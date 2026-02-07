import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ProjectCard } from '../components/project'
import { Button, Input, Select } from '../components/ui'
import { httpClient } from '../lib/httpClient'

type ProjectStatus = 'Draft' | 'In Progress' | 'Blocked' | 'Completed'
type ProjectType = 'Greenfield' | 'Brownfield'

type ProjectItem = {
  id: string
  name: string
  status: ProjectStatus
  type: ProjectType
  owner: string
  updatedAt: string
}

const fallbackProjects: ProjectItem[] = [
  { id: 'p-001', name: 'Medication Reconciliation Flow', status: 'In Progress', type: 'Greenfield', owner: 'Priya', updatedAt: '2026-02-06T15:30:00.000Z' },
  { id: 'p-002', name: 'Admissions Intake Modernization', status: 'Draft', type: 'Brownfield', owner: 'Luca', updatedAt: '2026-02-05T10:12:00.000Z' },
  { id: 'p-003', name: 'Care Plan Audit Trail', status: 'Blocked', type: 'Brownfield', owner: 'Jules', updatedAt: '2026-02-03T08:25:00.000Z' },
  { id: 'p-004', name: 'Resident Portal V2', status: 'Completed', type: 'Greenfield', owner: 'Ana', updatedAt: '2026-01-29T18:44:00.000Z' },
]

async function fetchProjects(): Promise<ProjectItem[]> {
  try {
    const response = await httpClient.get<ProjectItem[]>('/api/v1/projects')
    if (Array.isArray(response.data)) {
      return response.data
    }
    return fallbackProjects
  } catch (err: any) {
    // log details and rethrow so callers (useQuery) can surface error state
    console.error('fetchProjects failed', { url: '/api/v1/projects', error: err })
    throw err
  }
}

export function ProjectsPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'All' | ProjectStatus>('All')
  const [typeFilter, setTypeFilter] = useState<'All' | ProjectType>('All')

  const { data = [], isLoading } = useQuery({
    queryKey: ['projects-list'],
    queryFn: fetchProjects,
  })

  const filteredProjects = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return [...data]
      .filter((project) => {
        const matchesSearch =
          normalizedSearch.length === 0 ||
          project.name.toLowerCase().includes(normalizedSearch) ||
          project.owner.toLowerCase().includes(normalizedSearch)
        const matchesStatus = statusFilter === 'All' || project.status === statusFilter
        const matchesType = typeFilter === 'All' || project.type === typeFilter
        return matchesSearch && matchesStatus && matchesType
      })
      .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
  }, [data, search, statusFilter, typeFilter])

  return (
    <section className="rounded-lg border border-border bg-surface p-8 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Projects</h1>
          <p className="mt-2 text-sm text-fg/75">Search and filter project work across your workspace.</p>
        </div>
        <Button onClick={() => navigate('/projects/new')}>Create Project</Button>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <Input
          label="Search"
          placeholder="Find by project or owner"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <Select
          label="Status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as 'All' | ProjectStatus)}
          options={[
            { value: 'All', label: 'All statuses' },
            { value: 'Draft', label: 'Draft' },
            { value: 'In Progress', label: 'In Progress' },
            { value: 'Blocked', label: 'Blocked' },
            { value: 'Completed', label: 'Completed' },
          ]}
        />
        <Select
          label="Type"
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value as 'All' | ProjectType)}
          options={[
            { value: 'All', label: 'All types' },
            { value: 'Greenfield', label: 'Greenfield' },
            { value: 'Brownfield', label: 'Brownfield' },
          ]}
        />
      </div>

      <div className="mt-5 rounded-md border border-border bg-secondary/35">
        {isLoading ? (
          <p className="p-4 text-sm text-fg/70">Loading projects...</p>
        ) : filteredProjects.length === 0 ? (
          <p className="p-4 text-sm text-fg/70">No projects match the current filters.</p>
        ) : (
          <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredProjects.map((project) => (
              <ProjectCard
                key={project.id}
                id={project.id}
                name={project.name}
                status={project.status}
                type={project.type}
                owner={project.owner}
                updatedAt={project.updatedAt}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
