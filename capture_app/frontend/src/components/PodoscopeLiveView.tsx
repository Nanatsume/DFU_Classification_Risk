/* Live MJPEG view of the podoscope, shared by the camera-test page and the real capture page —
   both point the same <img> at GET /api/camera-test/preview (server.py, backed by
   capture_source.PodoscopeLivePreview). The server holds one cv2 handle open for as long as this
   element exists and releases it the moment the element (and so the request behind it) goes
   away, whether that's a toggle turning off or navigating off the page. Pressing capture while
   this is open does not conflict with it: /api/capture and /api/camera-test/capture both lift a
   still from the frame this is already holding (see server.py's _grab_podoscope_or_source)
   rather than opening a second handle.

   The crosshair is a plain overlay div, independent of the stream itself, for lining the foot up
   on the rig the way the OS camera app's own grid does. */

import { useState } from 'react'
import { cn } from '@/lib/utils'

/** `className` overrides the outer wrapper's sizing (default: a standalone 16:9 box with a
 *  bottom margin) — the capture page instead fills a fixed 4:3 slot that already exists, and
 *  passes `className="h-full w-full"` with no margin or aspect ratio of its own. */
export function PodoscopeLiveView({ className }: { className?: string }) {
  const [state, setState] = useState<'connecting' | 'ok' | 'failed'>('connecting')
  // Bust the cache on mount so toggling off and back on opens a fresh stream rather than an
  // <img> the browser thinks is already loaded.
  const [src] = useState(() => '/api/camera-test/preview?t=' + Date.now())

  return (
    <div className={cn('relative mb-3 aspect-video w-full overflow-hidden rounded-md bg-black', className)}>
      <img
        src={src}
        alt="วิดีโอสดจากกล้อง Podoscope"
        className="h-full w-full object-contain"
        onLoad={() => setState('ok')}
        onError={() => setState('failed')}
      />
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-0 bottom-0 left-1/2 w-px -translate-x-1/2 bg-white/50" />
        <div className="absolute top-1/2 right-0 left-0 h-px -translate-y-1/2 bg-white/50" />
      </div>
      {state === 'connecting' && (
        <div className="absolute inset-0 flex items-center justify-center text-[12px] text-white/70">
          กำลังเชื่อมต่อวิดีโอสด…
        </div>
      )}
      {state === 'failed' && (
        <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-[12px] text-white/80">
          ต่อวิดีโอสดไม่ได้ — ตรวจว่าอยู่โหมดกล้องจริง (ไม่ใช่โหมดจำลอง)
          และไม่มีโปรแกรมอื่นถือกล้องอยู่ (Logi Capture, OBS, Teams)
        </div>
      )}
    </div>
  )
}
