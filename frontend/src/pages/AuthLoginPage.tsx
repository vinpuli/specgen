import { Link } from 'react-router-dom'
import { Button, Input } from '../components/ui'

export function AuthLoginPage() {
  return (
    <div className="space-y-4">
      <Input label="Email" type="email" placeholder="name@company.com" />
      <Input label="Password" type="password" placeholder="••••••••" />
      <Button fullWidth>Sign In</Button>
      <p className="text-center text-xs text-fg/70">
        Demo auth route for layout scaffolding. <Link to="/" className="text-primary">Back to app</Link>
      </p>
    </div>
  )
}
