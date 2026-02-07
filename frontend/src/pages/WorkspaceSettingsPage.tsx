import { useEffect, useMemo, useState } from 'react'
import { Button, Input, Select, useToast } from '../components/ui'
import { useWorkspaceStore, type WorkspacePlan } from '../store/workspaceStore'

export function WorkspaceSettingsPage() {
  const { pushToast } = useToast()
  const activeWorkspaceId = useWorkspaceStore((state) => state.activeWorkspaceId)
  const workspaces = useWorkspaceStore((state) => state.workspaces)
  const updateWorkspace = useWorkspaceStore((state) => state.updateWorkspace)

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === activeWorkspaceId) ?? null,
    [activeWorkspaceId, workspaces],
  )

  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [description, setDescription] = useState('')
  const [plan, setPlan] = useState<WorkspacePlan>('Starter')

  useEffect(() => {
    if (!activeWorkspace) {
      return
    }
    setName(activeWorkspace.name)
    setSlug(activeWorkspace.slug)
    setDescription(activeWorkspace.description)
    setPlan(activeWorkspace.plan)
  }, [activeWorkspace])

  if (!activeWorkspace) {
    return <section className="rounded-lg border border-border bg-surface p-8 shadow-card">No active workspace found.</section>
  }

  const validName = name.trim().length >= 3
  const validSlug = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug.trim())
  const canSave = validName && validSlug

  const saveChanges = (): void => {
    if (!canSave) {
      pushToast('Fix validation errors before saving workspace settings.', 'warning')
      return
    }

    updateWorkspace(activeWorkspace.id, {
      name: name.trim(),
      slug: slug.trim(),
      description: description.trim(),
      plan,
    })
    pushToast('Workspace settings updated.', 'success')
  }

  return (
    <section className="rounded-lg border border-border bg-surface p-8 shadow-card">
      <h1 className="text-2xl font-semibold tracking-tight text-fg">Workspace Settings</h1>
      <p className="mt-2 text-sm text-fg/75">Update details for the currently active workspace.</p>

      <div className="mt-6 grid gap-4 lg:max-w-2xl">
        <Input
          label="Workspace Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          state={name.length === 0 || validName ? 'default' : 'error'}
          helperText={name.length > 0 && !validName ? 'Use at least 3 characters.' : undefined}
        />
        <Input
          label="Slug"
          value={slug}
          onChange={(event) => setSlug(event.target.value.toLowerCase().replace(/\s+/g, '-'))}
          state={slug.length === 0 || validSlug ? 'default' : 'error'}
          helperText={slug.length > 0 && !validSlug ? 'Use lowercase, numbers, and dashes only.' : undefined}
        />
        <Input
          label="Description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        <Select
          label="Plan"
          value={plan}
          onChange={(event) => setPlan(event.target.value as WorkspacePlan)}
          options={[
            { value: 'Starter', label: 'Starter' },
            { value: 'Pro', label: 'Pro' },
            { value: 'Enterprise', label: 'Enterprise' },
          ]}
        />
      </div>

      <div className="mt-6">
        <Button onClick={saveChanges} disabled={!canSave}>
          Save Workspace Settings
        </Button>
      </div>
    </section>
  )
}
