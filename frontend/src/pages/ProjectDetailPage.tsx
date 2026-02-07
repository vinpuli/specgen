import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge, Button } from '../components/ui'

type DetailStatus = 'Draft' | 'In Progress' | 'Blocked' | 'Completed'

type ProjectDetail = {
  id: string
  name: string
  status: DetailStatus
  type: 'Greenfield' | 'Brownfield'
  owner: string
  description: string
  updatedAt: string
  createdAt: string
  targetRelease: string
  completion: number
  openDecisions: number
  activeQuestions: number
  latestActivity: string
}

const detailData: Record<string, ProjectDetail> = {
  'p-001': {
    id: 'p-001',
    name: 'Medication Reconciliation Flow',
    status: 'In Progress',
    type: 'Greenfield',
    owner: 'Priya',
    description: 'Build guided med reconciliation workflows for admission and transfer moments.',
    updatedAt: '2026-02-06T15:30:00.000Z',
    createdAt: '2026-01-12T11:10:00.000Z',
    targetRelease: '2026-03-15',
    completion: 64,
    openDecisions: 5,
    activeQuestions: 3,
    latestActivity: 'Updated branch strategy and generated revised architecture draft.',
  },
  'p-002': {
    id: 'p-002',
    name: 'Admissions Intake Modernization',
    status: 'Draft',
    type: 'Brownfield',
    owner: 'Luca',
    description: 'Modernize intake forms and orchestrate handoffs from legacy system screens.',
    updatedAt: '2026-02-05T10:12:00.000Z',
    createdAt: '2026-01-25T08:22:00.000Z',
    targetRelease: '2026-04-02',
    completion: 22,
    openDecisions: 8,
    activeQuestions: 6,
    latestActivity: 'Imported repository baseline and queued discovery questions.',
  },
}

function statusVariant(status: DetailStatus): 'default' | 'success' | 'warning' | 'danger' {
  if (status === 'Completed') return 'success'
  if (status === 'Blocked') return 'danger'
  if (status === 'Draft') return 'warning'
  return 'default'
}

export function ProjectDetailPage() {
  const { projectId = '' } = useParams<{ projectId: string }>()

  const project = useMemo(() => {
    return detailData[projectId] ?? {
      id: projectId,
      name: 'Project Overview',
      status: 'Draft' as const,
      type: 'Greenfield' as const,
      owner: 'Unassigned',
      description: 'Project detail placeholder. Populate with API-backed project data.',
      updatedAt: new Date().toISOString(),
      createdAt: new Date().toISOString(),
      targetRelease: 'TBD',
      completion: 0,
      openDecisions: 0,
      activeQuestions: 0,
      latestActivity: 'No activity available yet.',
    }
  }, [projectId])

  return (
    <section className="space-y-5">
      <div className="rounded-lg border border-border bg-surface p-8 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-widest text-fg/60">Project Overview</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-fg">{project.name}</h1>
            <p className="mt-2 text-sm text-fg/75">{project.description}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={statusVariant(project.status)}>{project.status}</Badge>
            <span className="rounded-md border border-border bg-secondary/35 px-2 py-1 text-xs text-fg/75">
              {project.type}
            </span>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <div className="rounded-md border border-border bg-secondary/25 p-3">
            <p className="text-xs uppercase tracking-widest text-fg/60">Owner</p>
            <p className="mt-1 text-sm font-medium text-fg">{project.owner}</p>
          </div>
          <div className="rounded-md border border-border bg-secondary/25 p-3">
            <p className="text-xs uppercase tracking-widest text-fg/60">Completion</p>
            <p className="mt-1 text-sm font-medium text-fg">{project.completion}%</p>
          </div>
          <div className="rounded-md border border-border bg-secondary/25 p-3">
            <p className="text-xs uppercase tracking-widest text-fg/60">Open Decisions</p>
            <p className="mt-1 text-sm font-medium text-fg">{project.openDecisions}</p>
          </div>
          <div className="rounded-md border border-border bg-secondary/25 p-3">
            <p className="text-xs uppercase tracking-widest text-fg/60">Active Questions</p>
            <p className="mt-1 text-sm font-medium text-fg">{project.activeQuestions}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
          <h2 className="text-lg font-semibold text-fg">Timeline</h2>
          <div className="mt-4 space-y-3 text-sm text-fg/80">
            <p>
              <span className="font-medium text-fg">Created:</span>{' '}
              {new Date(project.createdAt).toLocaleString()}
            </p>
            <p>
              <span className="font-medium text-fg">Last Updated:</span>{' '}
              {new Date(project.updatedAt).toLocaleString()}
            </p>
            <p>
              <span className="font-medium text-fg">Target Release:</span> {project.targetRelease}
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
          <h2 className="text-lg font-semibold text-fg">Latest Activity</h2>
          <p className="mt-3 text-sm text-fg/80">{project.latestActivity}</p>
          <div className="mt-5 flex gap-2">
            <Button variant="secondary">Open Decisions</Button>
            <Button variant="ghost">View Conversation</Button>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <Link to="/projects" className="text-sm text-primary hover:underline">
          Back to project list
        </Link>
      </div>
    </section>
  )
}
