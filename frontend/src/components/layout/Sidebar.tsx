import { NavLink } from 'react-router-dom'
import { Select, type SelectOption } from '../ui'
import { useWorkspaceStore } from '../../store/workspaceStore'

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/workspaces', label: 'Workspaces' },
  { to: '/workspace/settings', label: 'Workspace Settings' },
  { to: '/workspace/members', label: 'Workspace Members' },
  { to: '/projects', label: 'Projects' },
  { to: '/settings', label: 'Settings' },
]

function linkClass(isActive: boolean): string {
  return [
    'rounded-md px-3 py-2 text-sm font-medium transition',
    isActive ? 'bg-primary text-primary-foreground' : 'text-fg/75 hover:bg-secondary hover:text-fg',
  ].join(' ')
}

export function Sidebar() {
  const workspaces = useWorkspaceStore((state) => state.workspaces)
  const activeWorkspaceId = useWorkspaceStore((state) => state.activeWorkspaceId)
  const setActiveWorkspace = useWorkspaceStore((state) => state.setActiveWorkspace)

  const workspaceOptions: SelectOption[] = (workspaces ?? []).length
    ? workspaces.map((workspace) => ({ value: workspace.id, label: workspace.name }))
    : []

  // ensure activeWorkspaceId is valid for the current options
  const validActiveWorkspaceId = workspaceOptions.find((o) => o.value === activeWorkspaceId)
    ? activeWorkspaceId
    : workspaceOptions.length > 0
    ? workspaceOptions[0].value
    : ''

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-border bg-surface/95 px-4 py-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">SpecGen</p>
        <p className="mt-1 text-sm text-fg/70">Workspace</p>
        <div className="mt-3">
          <Select
            options={workspaceOptions}
            value={validActiveWorkspaceId}
            onChange={(event) => {
              const next = event.target.value || undefined
              // tolerate empty/undefined selections
              if (!next) {
                setActiveWorkspace('')
                return
              }
              setActiveWorkspace(next)
            }}
            aria-label="Workspace switcher"
            disabled={workspaceOptions.length === 0}
          />
        </div>
      </div>

      <nav className="mt-6 flex flex-col gap-1">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => linkClass(isActive)}>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto rounded-md border border-border bg-secondary/40 p-3 text-xs text-fg/70">
        Sidebar with workspace switcher is active.
      </div>
    </aside>
  )
}
