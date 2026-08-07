import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthGuard } from '@/lib/auth'
import Gallery from '@/pages/Gallery'
import '@/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGuard>
      <Gallery />
    </AuthGuard>
  </StrictMode>,
)
