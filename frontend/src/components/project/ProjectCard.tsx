import { Link } from 'react-router-dom'
import { Badge, Button, Card, CardContent, CardFooter, CardHeader } from '../ui'

export type ProjectCardStatus = 'Draft' | 'In Progress' | 'Blocked' | 'Completed'
export type ProjectCardType = 'Greenfield' | 'Brownfield'

type ProjectCardProps = {
  id: string
  name: string
  status: ProjectCardStatus
  type: ProjectCardType
  owner: string
  updatedAt: string
}

function statusVariant(status: ProjectCardStatus): 'default' | 'success' | 'warning' | 'danger' {
  if (status === 'Completed') return 'success'
  if (status === 'Blocked') return 'danger'
  if (status === 'Draft') return 'warning'
  return 'default'
}

export function ProjectCard({ id, name, status, type, owner, updatedAt }: ProjectCardProps) {
  const d = new Date(updatedAt)
  const updatedText = Number.isFinite(d.getTime()) ? d.toLocaleString() : '—'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-base font-semibold text-fg">{name}</p>
            <p className="text-xs uppercase tracking-widest text-fg/60">{type}</p>
          </div>
          <Badge variant={statusVariant(status)}>{status}</Badge>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-2 text-sm text-fg/80">
          <p>
            <span className="font-medium text-fg">Owner:</span> {owner}
          </p>
          <p>
            <span className="font-medium text-fg">Updated:</span> {updatedText}
          </p>
        </div>
      </CardContent>

      <CardFooter className="flex justify-end">
        <Link to={`/projects/${id}`}>
          <Button size="sm" variant="secondary">
            Open Project
          </Button>
        </Link>
      </CardFooter>
    </Card>
  )
}
