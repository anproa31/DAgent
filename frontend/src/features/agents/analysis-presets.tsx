import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  CSV_LITE_TESTS,
  loadLiteTestPrompt,
  type CsvLiteTestId,
} from '@/features/agents/csv-analysis-tests'
import {
  SAMPLE_DATASET_PRESETS,
  loadPresetPrompt,
  resolvePresetTables,
  type SampleDatasetPreset,
  type SampleDatasetPresetId,
} from '@/features/agents/sample-dataset-presets'
import { toast } from 'sonner'

type AnalysisPresetsProps = {
  availableTableNames: string[]
  onApply: (preset: { prompt: string; tables: string[] }) => void
  disabled?: boolean
}

const CSV_PRESET = SAMPLE_DATASET_PRESETS.find((p) => p.id === 'csv')!

function PresetButtonLabel({ label }: { label: string }) {
  const [format, domain] = label.split(' · ')
  if (!domain) {
    return <span>{label}</span>
  }

  return (
    <>
      <span className='font-semibold text-foreground'>{domain}</span>
      <span className='text-muted-foreground'> · {format}</span>
    </>
  )
}

export function AnalysisPresets({
  availableTableNames,
  onApply,
  disabled,
}: AnalysisPresetsProps) {
  const [selectedDatasetId, setSelectedDatasetId] =
    useState<SampleDatasetPresetId | null>(null)
  const [selectedLiteTestId, setSelectedLiteTestId] =
    useState<CsvLiteTestId | null>(null)

  const applyCsvTables = () => {
    const tables = resolvePresetTables(
      availableTableNames,
      CSV_PRESET.tableMatchers
    )

    if (tables.length === 0) {
      toast.error(
        `No tables found for "${CSV_PRESET.label}". Register sample data from sample_dataset first.`,
        { description: `Expected: ${CSV_PRESET.description}` }
      )
    }

    return tables
  }

  const handlePreset = async (preset: SampleDatasetPreset) => {
    let prompt: string
    try {
      prompt = await loadPresetPrompt(preset.id)
    } catch {
      toast.error(`Failed to load preset prompt for "${preset.label}".`)
      return
    }

    const tables = resolvePresetTables(availableTableNames, preset.tableMatchers)
    setSelectedLiteTestId(null)
    setSelectedDatasetId(preset.id)
    onApply({ prompt, tables })

    if (tables.length === 0) {
      toast.error(
        `No tables found for "${preset.label}". Register sample data from sample_dataset first.`,
        { description: `Expected: ${preset.description}` }
      )
    }
  }

  const handleLiteTest = async (id: CsvLiteTestId) => {
    let prompt: string
    try {
      prompt = await loadLiteTestPrompt(id)
    } catch {
      toast.error('Failed to load lite test prompt.')
      return
    }

    const tables = applyCsvTables()
    setSelectedDatasetId(null)
    setSelectedLiteTestId(id)
    onApply({ prompt, tables })
  }

  return (
    <div className='mb-4 space-y-3'>
      <div className='flex flex-wrap justify-center gap-2'>
        {SAMPLE_DATASET_PRESETS.map((preset) => (
          <Button
            key={preset.id}
            type='button'
            variant='outline'
            size='sm'
            className={cn(
              'h-8 rounded-full px-3 text-xs font-normal',
              selectedDatasetId === preset.id &&
                'border-primary/50 bg-primary/10 hover:bg-primary/15'
            )}
            disabled={disabled}
            onClick={() => handlePreset(preset)}
          >
            <PresetButtonLabel label={preset.label} />
          </Button>
        ))}
      </div>

      <div className='flex flex-wrap justify-center gap-2'>
        {CSV_LITE_TESTS.map((test) => (
          <Button
            key={test.id}
            type='button'
            variant='outline'
            size='sm'
            className={cn(
              'h-8 max-w-[220px] truncate rounded-full px-3 text-xs font-normal',
              selectedLiteTestId === test.id &&
                'border-primary/50 bg-primary/10 hover:bg-primary/15'
            )}
            disabled={disabled}
            title={test.label}
            onClick={() => handleLiteTest(test.id)}
          >
            {test.label}
          </Button>
        ))}
      </div>
    </div>
  )
}
