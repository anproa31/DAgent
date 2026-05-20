import { useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import type { DatasourceRecord } from '@/services/api/datasources'
import { useDatasources, useDeleteDatasource } from '@/hooks/use-datasources'
import { ExistingDatasourceList } from '@/features/datasources/components/existing-datasource-list'
import { DeleteDatasourceDialog } from '@/features/datasources/components/delete-datasource-dialog'
import { AddDatasourceWizard } from '@/features/datasources/components/wizard/add-datasource-wizard'
import { useDatasourceWizard } from '@/features/datasources/hooks/use-datasource-wizard'

export interface DatabaseConnectionModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DatabaseConnectionModal({
  open,
  onOpenChange,
}: DatabaseConnectionModalProps) {
  const { data: datasources, isLoading: isDatasourcesLoading } = useDatasources()
  const deleteMutation = useDeleteDatasource()
  const [pendingDelete, setPendingDelete] = useState<DatasourceRecord | null>(
    null
  )

  const wizard = useDatasourceWizard(onOpenChange)

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return
    try {
      await deleteMutation.mutateAsync(pendingDelete.id)
      toast.success(`Removed ${pendingDelete.name}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to remove')
    } finally {
      setPendingDelete(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={wizard.handleClose}>
      <DialogContent className='max-h-[85vh] min-w-3xl overflow-y-auto'>
        <DialogHeader>
          <DialogTitle className='text-center text-2xl font-bold'>
            Datasources
          </DialogTitle>
        </DialogHeader>

        <Tabs
          value={wizard.tab}
          onValueChange={wizard.handleTabChange}
          className='mt-2'
        >
          <TabsList className='grid w-full grid-cols-2'>
            <TabsTrigger value='add'>Add new</TabsTrigger>
            <TabsTrigger value='manage'>
              Registered{' '}
              <Badge variant='secondary' className='ml-2'>
                {datasources?.length ?? 0}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value='manage' className='pt-4'>
            <ExistingDatasourceList
              datasources={datasources}
              isLoading={isDatasourcesLoading}
              onDelete={setPendingDelete}
              isDeleting={deleteMutation.isPending}
            />
          </TabsContent>

          <TabsContent value='add' className='pt-2'>
            <AddDatasourceWizard
              wizard={wizard}
              onDone={() => wizard.handleClose(false)}
              onAddAnother={() => {
                wizard.resetWizard()
                wizard.setTab('add')
              }}
            />
          </TabsContent>
        </Tabs>
      </DialogContent>

      <DeleteDatasourceDialog
        pendingDelete={pendingDelete}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        onConfirm={handleConfirmDelete}
      />
    </Dialog>
  )
}
