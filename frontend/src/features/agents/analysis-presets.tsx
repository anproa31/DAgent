import { Button } from '@/components/ui/button'
import {
  SAMPLE_DATASET_PRESETS,
  loadPresetPrompt,
  resolvePresetTables,
  type SampleDatasetPreset,
} from '@/features/agents/sample-dataset-presets'
import { toast } from 'sonner'

type AnalysisPresetsProps = {
  availableTableNames: string[]
  onApply: (preset: { prompt: string; tables: string[] }) => void
  disabled?: boolean
}

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
  const handlePreset = async (preset: SampleDatasetPreset) => {
    let prompt: string
    try {
      prompt = await loadPresetPrompt(preset.id)
    } catch {
      toast.error(`Failed to load preset prompt for "${preset.label}".`)
      return
    }

    const tables = resolvePresetTables(availableTableNames, preset.tableMatchers)
    onApply({ prompt, tables })

    if (tables.length === 0) {
      toast.error(
        `No tables found for "${preset.label}". Register sample data from sample_dataset first.`,
        { description: `Expected: ${preset.description}` }
      )
    }
  }

  return (
    <div className='mb-4 flex flex-wrap justify-center gap-2'>
      {SAMPLE_DATASET_PRESETS.map((preset) => (
        <Button
          key={preset.id}
          type='button'
          variant='outline'
          size='sm'
          className='h-8 rounded-full px-3 text-xs font-normal'
          disabled={disabled}
          onClick={() => handlePreset(preset)}
        >
          <PresetButtonLabel label={preset.label} />
        </Button>
      ))}
    </div>
  )
}
