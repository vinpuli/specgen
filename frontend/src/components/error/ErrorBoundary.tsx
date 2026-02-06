import type { ErrorInfo, ReactNode } from 'react'
import { Component } from 'react'
import { useTranslation } from 'react-i18next'

type ErrorBoundaryState = {
  hasError: boolean
}

type ErrorBoundaryProps = {
  children: ReactNode
}

class ErrorBoundaryBase extends Component<
  ErrorBoundaryProps & { title: string; description: string; resetLabel: string },
  ErrorBoundaryState
> {
  public state: ErrorBoundaryState = { hasError: false }

  public static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary captured an error', error, errorInfo)
  }

  private handleReset = (): void => {
    this.setState({ hasError: false })
  }

  public render(): ReactNode {
    const { hasError } = this.state
    const { children, title, description, resetLabel } = this.props

    if (!hasError) {
      return children
    }

    return (
      <main className="min-h-screen bg-gradient-to-b from-bg to-secondary/60 px-6 py-14">
        <section className="mx-auto w-full max-w-xl rounded-lg border border-danger/30 bg-surface p-8 shadow-card">
          <p className="text-xs font-semibold uppercase tracking-widest text-danger">Error</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-3 text-sm text-fg/75">{description}</p>
          <button
            type="button"
            onClick={this.handleReset}
            className="mt-5 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            {resetLabel}
          </button>
        </section>
      </main>
    )
  }
}

export function ErrorBoundary({ children }: ErrorBoundaryProps) {
  const { t } = useTranslation()
  return (
    <ErrorBoundaryBase
      title={t('errors.boundaryTitle')}
      description={t('errors.boundaryDescription')}
      resetLabel={t('errors.reset')}
    >
      {children}
    </ErrorBoundaryBase>
  )
}
