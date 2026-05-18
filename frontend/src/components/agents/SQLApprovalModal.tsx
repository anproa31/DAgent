import { useState } from 'react'
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

interface SQLApprovalModalProps {
  open: boolean
  sql: string
  explanation: string
  onApprove: (sql: string) => void
  onReject: (reason: string) => void
}

export function SQLApprovalModal({
  open,
  sql,
  explanation,
  onApprove,
  onReject,
}: SQLApprovalModalProps) {
  const [editedSql, setEditedSql] = useState(sql)
  const [isEditing, setIsEditing] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectInput, setShowRejectInput] = useState(false)

  // Sync edited SQL when sql prop changes
  if (!isEditing && editedSql !== sql) {
    setEditedSql(sql)
  }

  const handleApprove = () => {
    onApprove(editedSql)
    setIsEditing(false)
    setShowRejectInput(false)
  }

  const handleRejectSubmit = () => {
    onReject(rejectReason || 'Rejected by user')
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
            SQL Query Generated
          </DialogTitle>
          <DialogDescription>
            Review the generated SQL before it is executed against your database.
            {explanation && (
              <span className='block mt-1 text-foreground/80'>
                {explanation}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        {/* SQL editor */}
        <div className='space-y-2'>
          <div className='flex items-center justify-between'>
            <span className='text-xs text-muted-foreground font-mono uppercase tracking-wide'>
              SQL
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
              value={editedSql}
              onChange={(e) => setEditedSql(e.target.value)}
              className='font-mono text-sm min-h-36 resize-y'
              spellCheck={false}
            />
          ) : (
            <pre className='rounded-lg bg-muted p-4 text-sm font-mono overflow-x-auto whitespace-pre-wrap break-words max-h-64'>
              {editedSql}
            </pre>
          )}
        </div>

        {/* Rejection reason input */}
        {showRejectInput && (
          <div className='space-y-2'>
            <label className='text-xs text-muted-foreground'>
              Reason for rejection (optional — helps the agent regenerate):
            </label>
            <Textarea
              placeholder='e.g. "Missing filter for current month", "Wrong table used"…'
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
                {isEditing ? 'Approve Edited SQL' : 'Approve & Execute'}
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
