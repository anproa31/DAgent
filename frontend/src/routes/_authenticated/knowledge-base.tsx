import { useCallback } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useDropzone } from 'react-dropzone'
import { IconFile, IconTrash, IconUpload } from '@tabler/icons-react'
import { toast } from 'sonner'
import {
  useDeleteKbDocument,
  useKbDocuments,
  useUploadKbDocument,
} from '@/hooks/use-memory'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/context/locale-context'

export const Route = createFileRoute('/_authenticated/knowledge-base')({
  component: KnowledgeBasePage,
})

const ACCEPT = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'text/csv': ['.csv'],
  'text/markdown': ['.md'],
}

function KnowledgeBasePage() {
  const { t } = useTranslation()
  const { data: documents = [], isLoading } = useKbDocuments()
  const upload = useUploadKbDocument()
  const remove = useDeleteKbDocument()

  const onDrop = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        try {
          const res = await upload.mutateAsync(file)
          toast.success(
            t('kb.uploadSuccess', {
              filename: res.filename,
              chunks: res.chunks_stored,
            })
          )
        } catch (e: unknown) {
          const detail =
            (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            t('kb.uploadFailed')
          toast.error(detail)
        }
      }
    },
    [upload, t]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ accept: ACCEPT, onDrop })

  return (
    <div className="container mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-bold">{t('kb.title')}</h1>
      <p className="mt-1 text-muted-foreground">{t('kb.subtitle')}</p>
      <p className="mt-1 text-sm text-muted-foreground">
        <strong>{t('kb.supported')}</strong> PDF, DOCX, TXT, CSV, Markdown
      </p>

      <div
        {...getRootProps()}
        className={cn(
          'mt-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-12 text-center transition-colors',
          isDragActive ? 'border-primary bg-primary/5' : 'border-border bg-muted/30'
        )}
      >
        <input {...getInputProps()} />
        <IconUpload className="h-6 w-6 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">
          {upload.isPending
            ? t('kb.uploading')
            : isDragActive
              ? t('kb.dropHere')
              : t('kb.dragDrop')}
        </span>
      </div>

      <h2 className="mt-8 mb-3 text-lg font-semibold">{t('kb.uploadedDocs')}</h2>
      {isLoading ? (
        <p className="text-muted-foreground">{t('common.loading')}</p>
      ) : documents.length === 0 ? (
        <p className="text-muted-foreground">{t('kb.empty')}</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {documents.map((doc) => (
            <li key={doc} className="flex items-center justify-between gap-2 px-4 py-3">
              <span className="flex min-w-0 items-center gap-2">
                <IconFile className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="truncate">{doc}</span>
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                disabled={remove.isPending}
                title={t('kb.deleteDoc')}
                onClick={() => remove.mutate(doc)}
              >
                <IconTrash className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
