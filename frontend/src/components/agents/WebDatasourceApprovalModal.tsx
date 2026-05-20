import { useEffect, useMemo, useState } from 'react'
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
import { CheckCircle2, Globe, XCircle } from 'lucide-react'

export interface WebDiscoverCandidate {
  title: string
  url: string
  snippet?: string
  score?: number
  reason?: string
}

export interface WebDatasourceProposal {
  query: string
  reason: string
  selected_urls: string[]
  candidates: WebDiscoverCandidate[]
  proposed_name?: string
}

interface WebDatasourceApprovalModalProps {
  open: boolean
  proposal: WebDatasourceProposal | null
  onApprove: (selectedUrls: string[], name?: string) => void
  onReject: (reason: string) => void
}

export function WebDatasourceApprovalModal({
  open,
  proposal,
  onApprove,
  onReject,
}: WebDatasourceApprovalModalProps) {
  const urls = useMemo(
    () => proposal?.selected_urls ?? [],
    [proposal?.selected_urls]
  )
  const [selected, setSelected] = useState<string[]>([])
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectInput, setShowRejectInput] = useState(false)

  useEffect(() => {
    if (open) {
      setSelected(urls)
      setRejectReason('')
      setShowRejectInput(false)
    }
  }, [open, urls])

  const toggleUrl = (url: string, checked: boolean) => {
    setSelected((prev) =>
      checked ? [...new Set([...prev, url])] : prev.filter((u) => u !== url)
    )
  }

  const handleApprove = () => {
    onApprove(selected, proposal?.proposed_name)
    setShowRejectInput(false)
  }

  const handleRejectSubmit = () => {
    onReject(rejectReason.trim() || 'User declined importing web datasource')
    setShowRejectInput(false)
    setRejectReason('')
  }

  return (
    <Dialog open={open}>
      <DialogContent className='max-w-2xl max-h-[85vh] overflow-y-auto'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <Badge variant='outline' className='text-blue-700 border-blue-400'>
              Human Review Required
            </Badge>
            <Globe className='h-4 w-4' />
            Import data from the web?
          </DialogTitle>
          <DialogDescription>
            The agent found public dataset sources because existing datasources do not cover this
            question. Approve only the URLs you trust before they are added to your workspace.
            {proposal?.reason && (
              <span className='block mt-2 text-foreground/80'>{proposal.reason}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        {proposal?.query && (
          <div className='rounded-md bg-muted/60 p-3 text-sm'>
            <span className='font-medium'>Search need:</span> {proposal.query}
          </div>
        )}

        <div className='space-y-3'>
          <p className='text-xs uppercase tracking-wide text-muted-foreground'>
            Proposed dataset URLs
          </p>
          {urls.length === 0 ? (
            <p className='text-sm text-muted-foreground'>No URLs were proposed.</p>
          ) : (
            urls.map((url) => {
              const meta = proposal?.candidates?.find((c) => c.url === url)
              return (
                <label
                  key={url}
                  className='flex gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/40'
                >
                  <input
                    type='checkbox'
                    checked={selected.includes(url)}
                    onChange={(e) => toggleUrl(url, e.target.checked)}
                    className='mt-1 h-4 w-4'
                  />
                  <div className='min-w-0 flex-1'>
                    <div className='font-medium text-sm truncate'>
                      {meta?.title || url}
                    </div>
                    <div className='text-xs text-muted-foreground break-all'>{url}</div>
                    {meta?.snippet && (
                      <div className='text-xs mt-1 text-foreground/70 line-clamp-2'>
                        {meta.snippet}
                      </div>
                    )}
                  </div>
                </label>
              )
            })
          )}
        </div>

        {showRejectInput && (
          <div className='space-y-2'>
            <label className='text-xs text-muted-foreground'>
              Reason for declining (helps the agent choose another path):
            </label>
            <Textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className='text-sm min-h-20 resize-none'
              placeholder='e.g. "Use only internal HR data", "Wrong geography"'
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
                Decline import
              </Button>
              <Button onClick={handleApprove} disabled={selected.length === 0}>
                <CheckCircle2 className='h-4 w-4 mr-2' />
                Approve & import ({selected.length})
              </Button>
            </>
          ) : (
            <>
              <Button variant='ghost' onClick={() => setShowRejectInput(false)}>
                Cancel
              </Button>
              <Button variant='destructive' onClick={handleRejectSubmit}>
                <XCircle className='h-4 w-4 mr-2' />
                Confirm decline
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
