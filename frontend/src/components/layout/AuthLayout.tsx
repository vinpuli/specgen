import { Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-primary/10 via-bg to-accent/15 px-4 py-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(37,99,235,0.12),_transparent_45%)]" />
      <section className="relative w-full max-w-md rounded-xl border border-border bg-surface p-7 shadow-card sm:p-9">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">SpecGen</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-fg">Authentication</h1>
        <p className="mt-1 text-sm text-fg/70">Centered auth layout scaffold for login and onboarding screens.</p>
        <div className="mt-6">
          <Outlet />
        </div>
      </section>
    </main>
  )
}
