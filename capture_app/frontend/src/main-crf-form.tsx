import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthGuard } from '@/lib/auth'
import CrfForm from '@/pages/CrfForm'
import '@/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGuard>
      <CrfForm />
    </AuthGuard>
  </StrictMode>,
)
