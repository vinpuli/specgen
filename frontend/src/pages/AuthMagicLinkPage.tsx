import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useToast, Button, Input } from '../components/ui'
import { useAppStore } from '../store/appStore'
import { authService } from '../services/authService'

export function AuthMagicLinkPage() {
  const { pushToast } = useToast()
  const setTokens = useAppStore((state) => state.setTokens)
  const [email, setEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [sending, setSending] = useState(false)
  const [verifying, setVerifying] = useState(false)

  const validEmail = /\S+@\S+\.\S+/.test(email)
  const validCode = verificationCode.trim().length >= 6

  const handleSendLink = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()

    if (!validEmail) {
      pushToast('Please enter a valid email address.', 'warning')
      return
    }

    setSending(true)
    try {
      await authService.requestMagicLink(email)
      pushToast('Magic link sent. Check your inbox.', 'success')
    } catch {
      pushToast('Failed to send magic link. Please try again.', 'error')
    } finally {
      setSending(false)
    }
  }

  const handleVerifyCode = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()

    if (!validEmail || !validCode) {
      pushToast('Enter a valid email and 6+ character code.', 'warning')
      return
    }

    setVerifying(true)
    try {
      const payload = await authService.verifyMagicLink({ email, code: verificationCode.trim() })
      if (!payload.accessToken) {
        pushToast('Verification failed. No access token received.', 'error')
        return
      }
      setTokens({
        accessToken: payload.accessToken,
        refreshToken: payload.refreshToken ?? null,
        expiresInSeconds: payload.expiresInSeconds ?? 30 * 60,
      })
      pushToast('Magic link verified.', 'success')
    } catch {
      pushToast('Verification failed. Please try again.', 'error')
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div className="space-y-5">
      <form className="space-y-4" onSubmit={handleSendLink}>
        <p className="text-sm text-fg/75">
          Sign in without a password. We&apos;ll send a secure link to your email.
        </p>

        <Input
          label="Email"
          type="email"
          placeholder="name@company.com"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          state={email.length === 0 || validEmail ? 'default' : 'error'}
          helperText={email.length > 0 && !validEmail ? 'Use a valid email address.' : undefined}
        />

        <Button fullWidth type="submit" disabled={!validEmail || sending}>
          {sending ? 'Sending Link...' : 'Send Magic Link'}
        </Button>
      </form>

      <div className="rounded-lg border border-border/70 bg-bg/55 p-4">
        <form className="space-y-3" onSubmit={handleVerifyCode}>
          <p className="text-xs uppercase tracking-widest text-fg/60">Already received a code?</p>
          <Input
            label="Verification Code"
            placeholder="Enter code"
            value={verificationCode}
            onChange={(event) => setVerificationCode(event.target.value)}
            state={verificationCode.length === 0 || validCode ? 'default' : 'error'}
            helperText={verificationCode.length > 0 && !validCode ? 'Enter at least 6 characters.' : undefined}
          />
          <Button fullWidth type="submit" variant="secondary" disabled={!validEmail || !validCode || verifying}>
            {verifying ? 'Verifying...' : 'Verify Code'}
          </Button>
        </form>
      </div>

      <p className="text-center text-xs text-fg/70">
        Prefer password login?{' '}
        <Link to="/auth/login" className="text-primary">
          Back to login
        </Link>
      </p>
    </div>
  )
}
