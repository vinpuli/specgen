import { NavLink } from 'react-router-dom'
import { Select, type SelectOption } from '../ui'

const workspaceOptions: SelectOption[] = [
  { value: 'default', label: 'Default Workspace' },
  { value: 'clinical', label: 'Clinical Team' },
  { value: 'operations', label: 'Operations Team' },
]

const navItems = [
  { to: '/', label: 'Home' },
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
  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-border bg-surface/95 px-4 py-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">SpecGen</p>
        <p className="mt-1 text-sm text-fg/70">Workspace</p>
        <div className="mt-3">
          <Select options={workspaceOptions} defaultValue="default" aria-label="Workspace switcher" />
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
