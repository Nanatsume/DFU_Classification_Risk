import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthGuard } from '@/lib/auth'
import Roi from '@/pages/Roi'
import '@/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGuard>
      <Roi />
    </AuthGuard>
  </StrictMode>,
)
