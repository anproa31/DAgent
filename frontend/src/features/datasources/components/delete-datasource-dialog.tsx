import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DATASOURCE_TYPE_LABELS,
  type DatasourceRecord,
} from '@/services/api/datasources'

export interface DeleteDatasourceDialogProps {
  pendingDelete: DatasourceRecord | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

export function DeleteDatasourceDialog({
  pendingDelete,
  onOpenChange,
  onConfirm,
}: DeleteDatasourceDialogProps) {
  return (
    <AlertDialog
      open={!!pendingDelete}
      onOpenChange={(o) => !o && onOpenChange(false)}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove datasource?</AlertDialogTitle>
          <AlertDialogDescription>
            {pendingDelete && (
              <>
                <strong>{pendingDelete.name}</strong> (
                {DATASOURCE_TYPE_LABELS[pendingDelete.type] ??
                  pendingDelete.type}
                ) will be deregistered. Files uploaded to the registry are
                removed from disk; remote connections are simply forgotten.
              </>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className='bg-destructive text-destructive-foreground hover:bg-destructive/90'
          >
            Remove
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
