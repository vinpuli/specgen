import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/auth'
import { AuthLayout, MainLayout } from './components/layout'
import { AuthForgotPasswordPage } from './pages/AuthForgotPasswordPage'
import { AuthLoginPage } from './pages/AuthLoginPage'
import { AuthMagicLinkPage } from './pages/AuthMagicLinkPage'
import { AuthOAuthCallbackPage } from './pages/AuthOAuthCallbackPage'
import { AuthSignupPage } from './pages/AuthSignupPage'
import { AuthTwoFactorPage } from './pages/AuthTwoFactorPage'
import { CreateProjectWizardPage } from './pages/CreateProjectWizardPage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { SettingsPage } from './pages/SettingsPage'
import { WorkspaceListPage } from './pages/WorkspaceListPage'
import { WorkspaceMembersPage } from './pages/WorkspaceMembersPage'
import { WorkspaceSettingsPage } from './pages/WorkspaceSettingsPage'

function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/projects/new" element={<CreateProjectWizardPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/workspaces" element={<WorkspaceListPage />} />
          <Route path="/workspace/settings" element={<WorkspaceSettingsPage />} />
          <Route path="/workspace/members" element={<WorkspaceMembersPage />} />
        </Route>
      </Route>

      <Route path="/auth" element={<AuthLayout />}>
        <Route path="login" element={<AuthLoginPage />} />
        <Route path="signup" element={<AuthSignupPage />} />
        <Route path="forgot-password" element={<AuthForgotPasswordPage />} />
        <Route path="magic-link" element={<AuthMagicLinkPage />} />
        <Route path="2fa" element={<AuthTwoFactorPage />} />
        <Route path="callback/:provider" element={<AuthOAuthCallbackPage />} />
        <Route path="callback" element={<AuthOAuthCallbackPage />} />
      </Route>

      <Route path="/home" element={<Navigate to="/" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App
