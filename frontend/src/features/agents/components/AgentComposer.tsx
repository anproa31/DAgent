import type { FormEventHandler } from 'react'
import {
  AIInput,
  AIInputModelSelect,
  AIInputModelSelectContent,
  AIInputModelSelectItem,
  AIInputModelSelectTrigger,
  AIInputModelSelectValue,
  AIInputSubmit,
  AIInputTextarea,
  AIInputToolbar,
  AIInputTools,
  AIInputMultiSelectTable,
} from '@/components/shared/kibo-ui/ai-input'
import type { ModelInfo } from '@/hooks/use-analysis'

export interface AgentComposerProps {
  query: string
  onQueryChange: (value: string) => void
  model: string
  onModelChange: (value: string) => void
  models: ModelInfo[]
  tableOptions: { value: string; label: string }[]
  selectedTables: string[]
  onSelectedTablesChange: (tables: string[]) => void
  isRunning: boolean
  canSubmit: boolean
  onSubmit: FormEventHandler<HTMLFormElement>
  onStop: () => void
}

export function AgentComposer({
  query,
  onQueryChange,
  model,
  onModelChange,
  models,
  tableOptions,
  selectedTables,
  onSelectedTablesChange,
  isRunning,
  canSubmit,
  onSubmit,
  onStop,
}: AgentComposerProps) {
  return (
    <AIInput
      onSubmit={onSubmit}
      className='shadow-lg dark:shadow-accent-foreground/10 border border-border'
    >
      <AIInputTextarea
        onChange={(e) => onQueryChange(e.target.value)}
        value={query}
        placeholder='Describe your analysis task'
        disabled={isRunning}
      />
      <AIInputToolbar>
        <AIInputTools>
          <AIInputModelSelect onValueChange={onModelChange} value={model}>
            <AIInputModelSelectTrigger>
              <AIInputModelSelectValue placeholder='Select a model'>
                {model && models.find((m) => m.id === model)?.name}
              </AIInputModelSelectValue>
            </AIInputModelSelectTrigger>
            <AIInputModelSelectContent className='z-50'>
              {models.map((m) => (
                <AIInputModelSelectItem key={m.id} value={m.id}>
                  {m.name}
                </AIInputModelSelectItem>
              ))}
            </AIInputModelSelectContent>
          </AIInputModelSelect>
          <AIInputMultiSelectTable
            options={tableOptions}
            selected={selectedTables}
            onSelectedChange={onSelectedTablesChange}
            placeholder='Select tables'
          />
        </AIInputTools>
        <AIInputSubmit
          disabled={!isRunning && !canSubmit}
          status={isRunning ? 'streaming' : 'ready'}
          onStop={onStop}
        />
      </AIInputToolbar>
    </AIInput>
  )
}
