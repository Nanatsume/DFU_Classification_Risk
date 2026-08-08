/* Confirms a destructive delete by requiring the exact code (research id, etc.) to be typed back
   — a plain confirm() is too easy to click through by habit. Generic so any "delete X" action in
   the app can reuse it, not just the CRF list. */

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export function DeleteConfirmDialog({
  open, onOpenChange, code, title, description, onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** the exact string the user must type to enable the delete button, e.g. the research id */
  code: string
  title: string
  description: string
  onConfirm: () => void | Promise<void>
}) {
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const matches = typed.trim() === code

  function close(next: boolean) {
    if (!next) {
      setTyped('')
      setBusy(false)
    }
    onOpenChange(next)
  }

  async function handleConfirm() {
    if (!matches || busy) return
    setBusy(true)
    try {
      await onConfirm()
      close(false)
    } catch {
      setBusy(false) // let the caller's own error handling (alert, etc.) show through; keep dialog open
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-destructive">{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <label className="text-muted-foreground block text-xs">
            พิมพ์ <span className="text-foreground font-mono font-semibold">{code}</span> เพื่อยืนยัน
          </label>
          <Input
            autoFocus
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={code}
            className="font-mono"
            onKeyDown={(e) => { if (e.key === 'Enter' && matches) handleConfirm() }}
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => close(false)}>ยกเลิก</Button>
          <Button type="button" variant="destructive" disabled={!matches || busy} onClick={handleConfirm}>
            {busy ? 'กำลังลบ…' : 'ลบถาวร'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
