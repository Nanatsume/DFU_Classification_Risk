import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthGuard } from '@/lib/auth'
import CameraTest from '@/pages/CameraTest'
import '@/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGuard>
      <CameraTest />
    </AuthGuard>
  </StrictMode>,
)
