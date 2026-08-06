import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthGuard } from '@/lib/auth'
import Home from '@/pages/Home'
import '@/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGuard>
      <Home />
    </AuthGuard>
  </StrictMode>,
)
