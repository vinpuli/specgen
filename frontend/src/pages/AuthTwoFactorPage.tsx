import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Input, useToast } from '../components/ui'
import { authService } from '../services/authService'

export function AuthTwoFactorPage() {
  const { pushToast } = useToast()
  const [setupLoading, setSetupLoading] = useState(false)
  const [verifyLoading, setVerifyLoading] = useState(false)
  const [secret, setSecret] = useState('')
  const [otpauthUrl, setOtpauthUrl] = useState('')
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState('')
  const [code, setCode] = useState('')

  const validCode = /^\d{6}$/.test(code.trim())

  const handleSetup = async (): Promise<void> => {
    if (secret) {
      const confirmed = window.confirm('A 2FA secret already exists. Regenerating will invalidate the current setup. Continue?')
      if (!confirmed) return
    }
    setSetupLoading(true)
    try {
      const payload = await authService.setupTwoFactor()
      setSecret(payload.secret)
      setOtpauthUrl(payload.otpauthUrl)
      setQrCodeDataUrl(payload.qrCodeDataUrl ?? '')
      pushToast('2FA setup generated. Add it to your authenticator app.', 'success')
    } catch {
      pushToast('Failed to generate 2FA setup. Please try again.', 'error')
    } finally {
      setSetupLoading(false)
    }
  }

  const handleVerify = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()
    if (!validCode) {
      pushToast('Enter a valid 6-digit code.', 'warning')
      return
    }

    setVerifyLoading(true)
    try {
      await authService.verifyTwoFactor(code.trim())
      pushToast('2FA code verified.', 'success')
      navigate('/')
    } catch {
      pushToast('2FA verification failed.', 'error')
    } finally {
      setVerifyLoading(false)
    }
  }

  const navigate = useNavigate()

  return (
    <div className="space-y-5">
      <div className="space-y-3 rounded-lg border border-border/70 bg-bg/55 p-4">
        <p className="text-sm text-fg/75">
          Set up two-factor authentication to secure your account with time-based one-time codes.
        </p>
        <Button type="button" fullWidth onClick={handleSetup} disabled={setupLoading}>
          {setupLoading ? 'Generating Setup...' : 'Generate 2FA Setup'}
        </Button>

        {secret ? (
          <div className="space-y-2 text-xs text-fg/75">
            <p>
              <span className="font-semibold text-fg">Secret:</span> {secret}
            </p>
            <p className="break-all">
              <span className="font-semibold text-fg">OTP URL:</span> {otpauthUrl}
            </p>
            {qrCodeDataUrl ? (
              <img src={qrCodeDataUrl} alt="2FA QR code" className="h-40 w-40 rounded-md border border-border bg-surface p-2" />
            ) : null}
          </div>
        ) : null}
      </div>

      <form className="space-y-3 rounded-lg border border-border/70 bg-bg/55 p-4" onSubmit={handleVerify}>
        <Input
          label="Verification Code"
          placeholder="123456"
          inputMode="numeric"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          state={code.length === 0 || validCode ? 'default' : 'error'}
          helperText={code.length > 0 && !validCode ? 'Code must be exactly 6 digits.' : undefined}
        />

        <Button fullWidth type="submit" variant="secondary" disabled={!validCode || verifyLoading}>
          {verifyLoading ? 'Verifying...' : 'Verify 2FA Code'}
        </Button>
      </form>

      <p className="text-center text-xs text-fg/70">
        Back to{' '}
        <Link to="/auth/login" className="text-primary">
          login
        </Link>
      </p>
    </div>
  )
}
