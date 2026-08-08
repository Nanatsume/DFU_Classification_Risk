import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthGuard } from '@/lib/auth'
import CrfDetail from '@/pages/CrfDetail'
import '@/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGuard>
      <CrfDetail />
    </AuthGuard>
  </StrictMode>,
)
