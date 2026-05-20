import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'
import {
  IconDatabase,
  IconPlus,
  IconSql,
  IconTableImport,
  IconTrash,
} from '@tabler/icons-react'
import { useState } from 'react'
import { useTableList, type TableInfo } from '@/hooks/use-table-list'
import { useDeleteDatasource } from '@/hooks/use-datasources'
import { DATASOURCE_TYPE_LABELS, type DatasourceType } from '@/api/datasources'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { DatabaseConnectionModal } from '@/components/layout/database-connection-modal'

const DatasourceTypeIcon = ({ type }: { type: DatasourceType }) => {
  if (type === 'csv') {
    return <IconTableImport className="h-5 w-5 text-muted-foreground" />
  }
  if (type === 'sqlite') {
    return <IconSql className="h-5 w-5 text-muted-foreground" />
  }
  if (type === 'postgres') {
    return <IconDatabase className="h-5 w-5 text-muted-foreground" />
  }
  return <IconDatabase className="h-5 w-5 text-muted-foreground" />
}

const DatasourceCard = ({ table }: { table: TableInfo }) => {
  const deleteMutation = useDeleteDatasource()
  const label = DATASOURCE_TYPE_LABELS[table.datasourceType] ?? table.datasourceType

  const handleDelete = () => {
    deleteMutation.mutate(table.datasourceId)
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4 hover:bg-accent/50 transition-colors">
      <div className="flex items-center justify-between gap-2">
        <Link
          to="/table/$tableName"
          params={{ tableName: table.name }}
          className="flex min-w-0 flex-1 items-center gap-3"
        >
          <DatasourceTypeIcon type={table.datasourceType} />
          <span className="truncate font-medium">{table.name}</span>
        </Link>
        <div className="flex flex-shrink-0 items-center gap-1">
          <Badge variant="outline">{label}</Badge>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                disabled={deleteMutation.isPending}
                title="Remove datasource"
              >
                <IconTrash className="h-4 w-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Remove datasource?</AlertDialogTitle>
                <AlertDialogDescription>
                  <strong>{table.datasourceName}</strong> ({label}) will be
                  deregistered. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Remove
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/_authenticated/datasources')({
  component: DatasourcesPage,
})

function DatasourcesPage() {
  const { data: tables, isLoading, error } = useTableList()
  const [modalOpen, setModalOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div>Loading datasources...</div>
      </div>
    )
  }

  if (error || !tables) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="text-red-500">Failed to load datasources.</div>
        <button
          onClick={() => setModalOpen(true)}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md"
        >
          Add Datasource
        </button>
      </div>
    )
  }

  return (
    <>
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Datasources</h1>
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            <IconPlus className="h-4 w-4" />
            New Datasource
          </button>
        </div>

        {tables.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">No datasources connected yet.</p>
            <button
              onClick={() => setModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 mx-auto"
            >
              <IconPlus className="h-4 w-4" />
              Add Datasource
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tables.map((table) => (
              <DatasourceCard key={table.name} table={table} />
            ))}
          </div>
        )}
      </div>
      <DatabaseConnectionModal open={modalOpen} onOpenChange={setModalOpen} />
    </>
  )
}
