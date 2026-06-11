import { useState, type FormEventHandler } from 'react'
import { AtSign, Slash } from 'lucide-react'
import {
  AIInput,
  AIInputModelSelect,
  AIInputModelSelectContent,
  AIInputModelSelectItem,
  AIInputModelSelectTrigger,
  AIInputModelSelectValue,
  AIInputMultiSelect,
  AIInputSubmit,
  AIInputTextarea,
  AIInputToolbar,
  AIInputTools,
  AIInputMultiSelectTable,
} from '@/components/shared/kibo-ui/ai-input'
import type { ModelInfo } from '@/hooks/use-analysis'
import { useTranslation } from '@/context/locale-context'

export interface SelectOption {
  value: string
  label: string
}

export interface AgentComposerProps {
  query: string
  onQueryChange: (value: string) => void
  model: string
  onModelChange: (value: string) => void
  models: ModelInfo[]
  tableOptions: { value: string; label: string }[]
  selectedTables: string[]
  onSelectedTablesChange: (tables: string[]) => void
  // Memory pickers (@ knowledge base, / skills)
  kbOptions: SelectOption[]
  selectedKb: string[]
  onSelectedKbChange: (v: string[]) => void
  skillOptions: SelectOption[]
  selectedSkills: string[]
  onSelectedSkillsChange: (v: string[]) => void
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
  kbOptions,
  selectedKb,
  onSelectedKbChange,
  skillOptions,
  selectedSkills,
  onSelectedSkillsChange,
  isRunning,
  canSubmit,
  onSubmit,
  onStop,
}: AgentComposerProps) {
  const { t } = useTranslation()
  const [kbOpen, setKbOpen] = useState(false)
  const [skillsOpen, setSkillsOpen] = useState(false)

  // Typing `@` opens the knowledge-base picker, `/` opens the skill picker.
  const handleQueryChange = (next: string) => {
    const added = next.length === query.length + 1 ? next[next.length - 1] : ''
    if (added === '@') setKbOpen(true)
    else if (added === '/') setSkillsOpen(true)
    onQueryChange(next)
  }

  return (
    <AIInput
      onSubmit={onSubmit}
      className='shadow-lg dark:shadow-accent-foreground/10 border border-border'
    >
      <AIInputTextarea
        onChange={(e) => handleQueryChange(e.target.value)}
        value={query}
        placeholder={t('composer.placeholder')}
        disabled={isRunning}
      />
      <AIInputToolbar>
        <AIInputTools>
          <AIInputModelSelect onValueChange={onModelChange} value={model}>
            <AIInputModelSelectTrigger>
              <AIInputModelSelectValue placeholder={t('composer.selectModel')}>
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
            placeholder={t('composer.selectTables')}
          />
          <AIInputMultiSelect
            options={kbOptions}
            selected={selectedKb}
            onSelectedChange={onSelectedKbChange}
            icon={<AtSign className='h-4 w-4' />}
            noun={t('composer.knowledgeBase')}
            searchPlaceholder={t('composer.searchDocuments')}
            open={kbOpen}
            onOpenChange={setKbOpen}
          />
          <AIInputMultiSelect
            options={skillOptions}
            selected={selectedSkills}
            onSelectedChange={onSelectedSkillsChange}
            icon={<Slash className='h-4 w-4' />}
            noun={t('composer.skill')}
            searchPlaceholder={t('composer.searchSkills')}
            open={skillsOpen}
            onOpenChange={setSkillsOpen}
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
