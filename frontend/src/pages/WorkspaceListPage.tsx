import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, CardContent, CardFooter, CardHeader, Input, Modal, Select, useToast } from '../components/ui'
import { useWorkspaceStore, type WorkspacePlan } from '../store/workspaceStore'

export function WorkspaceListPage() {
  const { pushToast } = useToast()
  const navigate = useNavigate()
  const workspaces = useWorkspaceStore((state) => state.workspaces)
  const activeWorkspaceId = useWorkspaceStore((state) => state.activeWorkspaceId)
  const setActiveWorkspace = useWorkspaceStore((state) => state.setActiveWorkspace)
  const createWorkspace = useWorkspaceStore((state) => state.createWorkspace)

  const [openCreateModal, setOpenCreateModal] = useState(false)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [description, setDescription] = useState('')
  const [plan, setPlan] = useState<WorkspacePlan>('Starter')

  const validName = name.trim().length >= 3
  const validSlug = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug.trim())
  const canCreate = validName && validSlug

  const sortedWorkspaces = useMemo(
    () => [...workspaces].sort((a, b) => Number(b.id === activeWorkspaceId) - Number(a.id === activeWorkspaceId)),
    [activeWorkspaceId, workspaces],
  )

  const resetCreateForm = (): void => {
    setName('')
    setSlug('')
    setDescription('')
    setPlan('Starter')
  }

  const handleCreateWorkspace = async (): Promise<void> => {
    if (!canCreate) {
      pushToast('Name and slug are required. Slug uses lowercase letters, numbers, and dashes.', 'warning')
      return
    }

    try {
      const workspace = await createWorkspace({
        name: name.trim(),
        slug: slug.trim(),
        description: description.trim(),
        plan,
      })
      pushToast(`Workspace "${workspace.name}" created.`, 'success')
      resetCreateForm()
      setOpenCreateModal(false)
    } catch (err: any) {
      console.error('createWorkspace failed', err)
      pushToast(`Failed to create workspace: ${err?.message ?? 'Unknown error'}`, 'error')
      // keep form open so user can retry
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Workspaces</h1>
          <p className="mt-1 text-sm text-fg/70">Manage all workspaces and switch context for your team.</p>
        </div>
        <Button onClick={() => setOpenCreateModal(true)}>Create Workspace</Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {sortedWorkspaces.map((workspace) => {
          const isActive = workspace.id === activeWorkspaceId
          return (
            <Card key={workspace.id} className={isActive ? 'border-primary/50' : ''}>
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-lg font-semibold text-fg">{workspace.name}</p>
                    <p className="text-xs uppercase tracking-widest text-fg/55">{workspace.slug}</p>
                  </div>
                  <span className="rounded-full border border-border px-2 py-0.5 text-xs text-fg/70">{workspace.plan}</span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-fg/80">{workspace.description || 'No description yet.'}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-fg/70">
                  <span className="rounded-md bg-secondary px-2 py-1">{workspace.membersCount} members</span>
                  <span className="rounded-md bg-secondary px-2 py-1">{workspace.projectsCount} projects</span>
                  <span className="rounded-md bg-secondary px-2 py-1">Created {workspace.createdAt}</span>
                </div>
              </CardContent>
              <CardFooter className="flex gap-2">
                <Button
                  variant={isActive ? 'secondary' : 'primary'}
                  onClick={() => {
                    if (isActive) return
                    setActiveWorkspace(workspace.id)
                    pushToast(`Active workspace set to ${workspace.name}.`, 'info')
                  }}
                >
                  {isActive ? 'Current Workspace' : 'Set Active'}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setActiveWorkspace(workspace.id)
                    navigate('/workspace/settings')
                  }}
                >
                  Settings
                </Button>
              </CardFooter>
            </Card>
          )
        })}
      </div>

      <Modal
        open={openCreateModal}
        title="Create Workspace"
        onClose={() => {
          resetCreateForm()
          setOpenCreateModal(false)
        }}
        onConfirm={handleCreateWorkspace}
        confirmLabel="Create"
      >
        <div className="space-y-3">
          <Input
            label="Workspace Name"
            placeholder="Example: Product Team"
            value={name}
            onChange={(event) => setName(event.target.value)}
            state={name.length === 0 || validName ? 'default' : 'error'}
            helperText={name.length > 0 && !validName ? 'Use at least 3 characters.' : undefined}
          />
          <Input
            label="Slug"
            placeholder="product-team"
            value={slug}
            onChange={(event) => setSlug(event.target.value.toLowerCase().replace(/\s+/g, '-'))}
            state={slug.length === 0 || validSlug ? 'default' : 'error'}
            helperText={slug.length > 0 && !validSlug ? 'Use lowercase, numbers, and dashes only.' : undefined}
          />
          <Input
            label="Description"
            placeholder="What this workspace is for"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <Select
            label="Plan"
            value={plan}
            options={[
              { value: 'Starter', label: 'Starter' },
              { value: 'Pro', label: 'Pro' },
              { value: 'Enterprise', label: 'Enterprise' },
            ]}
            onChange={(event) => setPlan(event.target.value as WorkspacePlan)}
          />
        </div>
      </Modal>
    </section>
  )
}
