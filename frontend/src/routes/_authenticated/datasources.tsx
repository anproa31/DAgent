import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'
import { IconDatabase, IconPlus, IconTableImport, IconSql } from '@tabler/icons-react'
import { useTableList } from '@/hooks/use-table-list'
import { DATASOURCE_TYPE_LABELS, type DatasourceType } from '@/api/datasources'
import { Badge } from '@/components/ui/badge'
import { DatabaseConnectionModal } from '@/components/layout/database-connection-modal'
import { useState } from 'react'

const DatasourceCard = ({ name, type }: { name: string; type: DatasourceType }) => {
  const label = DATASOURCE_TYPE_LABELS[type] ?? type

  return (
    <Link to="/table/$tableName" params={{ tableName: name }} className="block">
      <div className="rounded-lg border border-border bg-card p-4 hover:bg-accent/50 transition-colors">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {type === 'csv' && <IconTableImport className="h-5 w-5 text-muted-foreground" />}
            {type === 'sqlite' && <IconSql className="h-5 w-5 text-muted-foreground" />}
            {type === 'postgres' && <IconDatabase className="h-5 w-5 text-muted-foreground" />}
            <span className="font-medium truncate">{name}</span>
          </div>
          <Badge variant="outline" className="flex-shrink-0 ml-2">
            {label}
          </Badge>
        </div>
      </div>
    </Link>
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
              <DatasourceCard key={table.name} name={table.name} type={table.datasourceType} />
            ))}
          </div>
        )}
      </div>
      <DatabaseConnectionModal open={modalOpen} onOpenChange={setModalOpen} />
    </>
  )
}
