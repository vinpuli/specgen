import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useToast, Button, Input } from '../components/ui'
import { authService } from '../services/authService'

export function AuthForgotPasswordPage() {
  const { pushToast } = useToast()
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const validEmail = /\S+@\S+\.\S+/.test(email)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()

    if (!validEmail) {
      pushToast('Please enter a valid email address.', 'warning')
      return
    }

    setSubmitting(true)
    try {
      await authService.requestPasswordReset(email)
      pushToast('Password reset email sent.', 'success')
    } catch {
      pushToast('Failed to send reset email. Please try again.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <p className="text-sm text-fg/75">
        Enter your email and we&apos;ll send password reset instructions.
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

      <Button fullWidth type="submit" disabled={!validEmail || submitting}>
        {submitting ? 'Sending...' : 'Send Reset Link'}
      </Button>

      <p className="text-center text-xs text-fg/70">
        Remembered your password?{' '}
        <Link to="/auth/login" className="text-primary">
          Back to login
        </Link>
      </p>
    </form>
  )
}
