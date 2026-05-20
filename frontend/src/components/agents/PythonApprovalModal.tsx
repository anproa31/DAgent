import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, XCircle, Edit3 } from 'lucide-react'

interface PythonApprovalModalProps {
  open: boolean
  code: string
  risk: string
  onApprove: (code: string) => void
  onReject: (reason: string, code: string) => void
}

export function PythonApprovalModal({
  open,
  code,
  risk,
  onApprove,
  onReject,
}: PythonApprovalModalProps) {
  const [editedCode, setEditedCode] = useState(code)
  const [isEditing, setIsEditing] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectInput, setShowRejectInput] = useState(false)
  const hasCodeChanged = editedCode !== code

  useEffect(() => {
    if (open) {
      setEditedCode(code)
    }
  }, [code, open])

  const handleApprove = () => {
    onApprove(editedCode)
    setIsEditing(false)
    setShowRejectInput(false)
  }

  const handleRejectSubmit = () => {
    const reason =
      rejectReason.trim() ||
      (hasCodeChanged ? 'Python edited by user' : 'Rejected by user')
    onReject(reason, editedCode)
    setShowRejectInput(false)
    setRejectReason('')
  }

  return (
    <Dialog open={open}>
      <DialogContent className='max-w-2xl'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <Badge variant='outline' className='text-amber-600 border-amber-400'>
              Human Review Required
            </Badge>
            Python Code Generated
            {risk && (
              <Badge variant='secondary' className='text-xs uppercase'>
                {risk} risk
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Review the generated Python before it runs in the sandbox.
          </DialogDescription>
        </DialogHeader>

        <div className='space-y-2'>
          <div className='flex items-center justify-between'>
            <span className='text-xs text-muted-foreground font-mono uppercase tracking-wide'>
              Python
            </span>
            <Button
              variant='ghost'
              size='sm'
              onClick={() => setIsEditing(!isEditing)}
              className='text-xs h-7'
            >
              <Edit3 className='h-3 w-3 mr-1' />
              {isEditing ? 'Lock' : 'Edit'}
            </Button>
          </div>

          {isEditing ? (
            <Textarea
              value={editedCode}
              onChange={(e) => setEditedCode(e.target.value)}
              className='font-mono text-sm min-h-36 resize-y'
              spellCheck={false}
            />
          ) : (
            <pre className='rounded-lg bg-muted p-4 text-sm font-mono overflow-x-auto whitespace-pre-wrap break-words max-h-64'>
              {editedCode}
            </pre>
          )}
        </div>

        {showRejectInput && (
          <div className='space-y-2'>
            <label className='text-xs text-muted-foreground'>
              Reason for rejection or edit the code (required — helps the agent
              regenerate):
            </label>
            <Textarea
              placeholder='e.g. "Avoid network calls", "Use df_result instead"…'
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className='text-sm min-h-20 resize-none'
            />
          </div>
        )}

        <DialogFooter className='gap-2 sm:justify-between'>
          {!showRejectInput ? (
            <>
              <Button
                variant='outline'
                className='text-destructive hover:text-destructive'
                onClick={() => setShowRejectInput(true)}
              >
                <XCircle className='h-4 w-4 mr-2' />
                Reject & Regenerate
              </Button>
              <Button onClick={handleApprove}>
                <CheckCircle2 className='h-4 w-4 mr-2' />
                {isEditing ? 'Approve Edited Code' : 'Approve & Execute'}
              </Button>
            </>
          ) : (
            <>
              <Button
                variant='ghost'
                onClick={() => {
                  setShowRejectInput(false)
                  setRejectReason('')
                }}
              >
                Cancel
              </Button>
              <Button
                variant='destructive'
                onClick={handleRejectSubmit}
                disabled={!rejectReason.trim() && !hasCodeChanged}
              >
                <XCircle className='h-4 w-4 mr-2' />
                Send Rejection
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
