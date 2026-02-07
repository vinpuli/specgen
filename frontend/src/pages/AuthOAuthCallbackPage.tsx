import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Button, LoadingSpinner, useToast } from '../components/ui'
import { useAppStore } from '../store/appStore'
import { authService } from '../services/authService'

type CallbackStatus = 'processing' | 'success' | 'error'

export function AuthOAuthCallbackPage() {
  const { pushToast } = useToast()
  const navigate = useNavigate()
  const params = useParams<{ provider: string }>()
  const [searchParams] = useSearchParams()
  const setTokens = useAppStore((state) => state.setTokens)
  const [status, setStatus] = useState<CallbackStatus>('processing')
  const [message, setMessage] = useState('Finalizing OAuth login...')
  const handledRef = useRef(false)
  const timeoutsRef = useRef<number[]>([])

  const providerName = useMemo(() => {
    const rawProvider = (params.provider ?? searchParams.get('provider') ?? 'provider').trim()
    if (rawProvider.length === 0) {
      return 'provider'
    }
    return rawProvider.charAt(0).toUpperCase() + rawProvider.slice(1).toLowerCase()
  }, [params.provider, searchParams])

  useEffect(() => {
    if (handledRef.current) {
      return
    }
    handledRef.current = true

    const error = searchParams.get('error') ?? searchParams.get('error_description')
    if (error) {
      setStatus('error')
      setMessage(`OAuth sign-in failed: ${error}`)
      pushToast(`OAuth error from ${providerName}.`, 'error')
      return
    }

    const callbackParams: Record<string, string> = {}
    searchParams.forEach((value, key) => {
      callbackParams[key] = value
    })
    const directToken = callbackParams.token ?? callbackParams.access_token
    // Remove sensitive tokens from the URL/history to avoid leakage
    if (directToken) {
      const url = new URL(window.location.href)
      url.searchParams.delete('token')
      url.searchParams.delete('access_token')
      window.history.replaceState({}, document.title, url.toString())
    }

    const provider = (params.provider ?? searchParams.get('provider') ?? '').trim().toLowerCase()
    if (!provider) {
      setStatus('error')
      setMessage('OAuth callback did not include a provider.')
      pushToast('OAuth callback missing provider.', 'warning')
      return
    }

    const run = async () => {
      try {
        const payload = await authService.verifyOAuthCallback(provider, callbackParams)
        if (!payload.accessToken) {
          if (!directToken) {
            throw new Error('Missing access token')
          }
          setTokens({
            accessToken: directToken,
            refreshToken: null,
            expiresInSeconds: 30 * 60,
          })
          setStatus('success')
          setMessage(`Signed in with ${providerName}. Redirecting...`)
          pushToast(`${providerName} sign-in complete (fallback).`, 'success')
          timeoutsRef.current.push(window.setTimeout(() => navigate('/'), 900))
          return
        }

        setTokens({
          accessToken: payload.accessToken,
          refreshToken: payload.refreshToken ?? null,
          expiresInSeconds: payload.expiresInSeconds ?? 30 * 60,
        })

        setStatus('success')
        setMessage(`Signed in with ${providerName}. Redirecting...`)
        pushToast(`${providerName} sign-in complete.`, 'success')
        timeoutsRef.current.push(window.setTimeout(() => navigate('/'), 900))
      } catch {
        if (directToken) {
          setTokens({
            accessToken: directToken,
            refreshToken: null,
            expiresInSeconds: 30 * 60,
          })
          setStatus('success')
          setMessage(`Signed in with ${providerName}. Redirecting...`)
          pushToast(`${providerName} sign-in complete (fallback).`, 'success')
          timeoutsRef.current.push(window.setTimeout(() => navigate('/'), 900))
          return
        }
        setStatus('error')
        setMessage(`Unable to complete OAuth sign-in with ${providerName}.`)
        pushToast(`${providerName} callback verification failed.`, 'error')
      }
    }

    void run()
    return () => {
      // clear any pending navigations/timeouts when component unmounts
      for (const t of timeoutsRef.current) {
        clearTimeout(t)
      }
      timeoutsRef.current = []
    }
  }, [navigate, params.provider, providerName, pushToast, searchParams, setTokens])

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg/75">Handling OAuth callback from {providerName}.</p>

      <div className="rounded-lg border border-border/70 bg-bg/55 p-4">
        <div className="flex items-center gap-3">
          {status === 'processing' ? <LoadingSpinner size="sm" /> : null}
          <p className="text-sm text-fg">{message}</p>
        </div>
      </div>

      {status === 'error' ? (
        <div className="space-y-2">
          <Button fullWidth onClick={() => navigate('/auth/login')}>
            Back to login
          </Button>
          <p className="text-center text-xs text-fg/70">
            Need an account?{' '}
            <Link to="/auth/signup" className="text-primary">
              Sign up
            </Link>
          </p>
        </div>
      ) : null}
    </div>
  )
}
