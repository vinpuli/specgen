import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { PageContainer } from './PageContainer'
import { Sidebar } from './Sidebar'

export function MainLayout() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-bg to-secondary/60">
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <PageContainer>
            <Outlet />
          </PageContainer>
        </div>
      </div>
    </div>
  )
}
