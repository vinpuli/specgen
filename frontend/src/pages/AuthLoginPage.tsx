import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useToast, Button, Input } from '../components/ui'

export function AuthLoginPage() {
  const { pushToast } = useToast()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const emailState = email.length === 0 || /\S+@\S+\.\S+/.test(email) ? 'default' : 'error'
  const passwordState = password.length === 0 || password.length >= 8 ? 'default' : 'error'

  const canSubmit = /\S+@\S+\.\S+/.test(email) && password.length >= 8 && !submitting

  const handleLogin = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    if (!canSubmit) {
      pushToast('Enter a valid email and password (8+ chars).', 'warning')
      return
    }

    setSubmitting(true)
    try {
      await login({ email, password })
      pushToast('Login successful.', 'success')
      navigate('/')
    } catch {
      pushToast('Login failed. Check credentials and try again.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const handleOAuth = (provider: 'Google' | 'GitHub'): void => {
    const providerSlug = provider.toLowerCase()
    const demoToken = `oauth_${providerSlug}_demo_token`
    pushToast(`Redirecting to ${provider} callback (demo).`, 'info')
    navigate(`/auth/callback/${providerSlug}?token=${encodeURIComponent(demoToken)}`)
  }

  return (
    <form className="space-y-4" onSubmit={handleLogin}>
      <Input
        label="Email"
        type="email"
        placeholder="name@company.com"
        autoComplete="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        state={emailState}
        helperText={emailState === 'error' ? 'Use a valid email address.' : undefined}
      />

      <div className="space-y-2">
        <Input
          label="Password"
          type="password"
          placeholder="********"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          state={passwordState}
          helperText={passwordState === 'error' ? 'Password must be at least 8 characters.' : undefined}
        />
        <div className="flex justify-between text-xs">
          <Link to="/auth/magic-link" className="text-primary hover:underline">
            Use magic link
          </Link>
          <Link to="/auth/2fa" className="text-primary hover:underline">
            2FA verify
          </Link>
          <Link to="/auth/forgot-password" className="text-primary hover:underline">
            Forgot password?
          </Link>
        </div>
      </div>

      <Button fullWidth type="submit" disabled={!canSubmit}>
        {submitting ? 'Signing In...' : 'Sign In'}
      </Button>

      <div className="flex items-center gap-3 py-1">
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs uppercase tracking-widest text-fg/55">or continue with</span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Button type="button" variant="secondary" fullWidth onClick={() => handleOAuth('Google')}>
          Google
        </Button>
        <Button type="button" variant="secondary" fullWidth onClick={() => handleOAuth('GitHub')}>
          GitHub
        </Button>
      </div>

      <p className="text-center text-xs text-fg/70">
        New here?{' '}
        <Link to="/auth/signup" className="text-primary">
          Create an account
        </Link>
      </p>
    </form>
  )
}
