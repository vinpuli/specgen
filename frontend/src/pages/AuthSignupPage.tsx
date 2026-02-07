import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useToast, Button, Input, Checkbox } from '../components/ui'

type StrengthLevel = 'Very Weak' | 'Weak' | 'Fair' | 'Good' | 'Strong'

function getPasswordStrength(password: string): { score: number; level: StrengthLevel } {
  if (password.length === 0) {
    return { score: 0, level: 'Very Weak' }
  }

  let score = 0
  if (password.length >= 8) score += 1
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1
  if (/\d/.test(password)) score += 1
  // award points separately for symbols and long length
  if (/[^A-Za-z0-9]/.test(password)) score += 1
  if (password.length >= 12) score += 1

  const levelByScore: Record<number, StrengthLevel> = {
    0: 'Very Weak',
    1: 'Weak',
    2: 'Fair',
    3: 'Good',
    4: 'Strong',
  }

  return { score, level: levelByScore[score] }
}

export function AuthSignupPage() {
  const { pushToast } = useToast()
  const { signup } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [acceptTerms, setAcceptTerms] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const validName = fullName.trim().length >= 2
  const validEmail = /\S+@\S+\.\S+/.test(email)
  const validPassword = password.length >= 8
  const passwordsMatch = password === confirmPassword
  const passwordStrength = getPasswordStrength(password)

  const canSubmit =
    validName &&
    validEmail &&
    validPassword &&
    passwordsMatch &&
    acceptTerms &&
    !submitting

  const handleSignup = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    if (!canSubmit) {
      pushToast('Please fix validation errors before creating your account.', 'warning')
      return
    }

    setSubmitting(true)
    try {
      await signup({ fullName: fullName.trim(), email, password })
      pushToast('Account created and signed in.', 'success')
    } catch {
      pushToast('Signup failed. Please try again.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSignup}>
      <Input
        label="Full Name"
        placeholder="Jane Smith"
        autoComplete="name"
        value={fullName}
        onChange={(event) => setFullName(event.target.value)}
        state={fullName.length === 0 || validName ? 'default' : 'error'}
        helperText={fullName.length > 0 && !validName ? 'Enter at least 2 characters.' : undefined}
      />

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

      <Input
        label="Password"
        type="password"
        placeholder="Create a password"
        autoComplete="new-password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        state={password.length === 0 || validPassword ? 'default' : 'error'}
        helperText={password.length > 0 && !validPassword ? 'Password must be at least 8 characters.' : undefined}
      />
      <div className="space-y-2 rounded-md border border-border/70 bg-bg/55 p-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-widest text-fg/60">Password strength</p>
          <p className="text-xs font-semibold text-fg">{passwordStrength.level}</p>
        </div>
        <div className="grid grid-cols-4 gap-1">
          {[1, 2, 3, 4].map((segment) => (
            <span
              key={segment}
              className={[
                'h-1.5 rounded-full',
                passwordStrength.score >= segment ? 'bg-primary' : 'bg-border',
              ].join(' ')}
            />
          ))}
        </div>
        <ul className="space-y-1 text-xs text-fg/70">
          <li className={password.length >= 8 ? 'text-success' : ''}>At least 8 characters</li>
          <li className={/[a-z]/.test(password) && /[A-Z]/.test(password) ? 'text-success' : ''}>
            Uppercase and lowercase letters
          </li>
          <li className={/\d/.test(password) ? 'text-success' : ''}>At least one number</li>
            <li className={/[^A-Za-z0-9]/.test(password) ? 'text-success' : ''}>At least one symbol</li>
            <li className={password.length >= 12 ? 'text-success' : ''}>At least 12 characters</li>
        </ul>
      </div>

      <Input
        label="Confirm Password"
        type="password"
        placeholder="Confirm your password"
        autoComplete="new-password"
        value={confirmPassword}
        onChange={(event) => setConfirmPassword(event.target.value)}
        state={confirmPassword.length === 0 || passwordsMatch ? 'default' : 'error'}
        helperText={confirmPassword.length > 0 && !passwordsMatch ? 'Passwords do not match.' : undefined}
      />

      <Checkbox
        label={
          <>
            I agree to the{' '}
            <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-primary">
              Terms of Service
            </a>{' '}
            and{' '}
            <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-primary">
              Privacy Policy
            </a>
          </>
        }
        checked={acceptTerms}
        onChange={(event) => setAcceptTerms(event.currentTarget.checked)}
      />

      <Button fullWidth type="submit" disabled={!canSubmit}>
        {submitting ? 'Creating Account...' : 'Create Account'}
      </Button>

      <p className="text-center text-xs text-fg/70">
        Already have an account?{' '}
        <Link to="/auth/login" className="text-primary">
          Sign in
        </Link>
      </p>
    </form>
  )
}
