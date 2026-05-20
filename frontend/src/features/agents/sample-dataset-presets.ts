import { parsePresetPrompt } from '@/features/agents/parse-preset-prompt'

export type SampleDatasetPresetId = 'csv' | 'db_test' | 'parquet' | 'sqlite'

export type SampleDatasetPreset = {
  id: SampleDatasetPresetId
  label: string
  description: string
  /** View names or substrings matched against registered tables. */
  tableMatchers: string[]
}

const PROMPT_LOADERS: Record<
  SampleDatasetPresetId,
  () => Promise<{ default: string }>
> = {
  csv: () => import('@sample-dataset/csv/prompt.md?raw'),
  db_test: () => import('@sample-dataset/db_test/prompt.md?raw'),
  parquet: () => import('@sample-dataset/parquet/prompt.md?raw'),
  sqlite: () => import('@sample-dataset/sqlite/prompt.md?raw'),
}

/** Load the latest preset prompt from sample_dataset on each click (avoids stale dev bundles). */
export async function loadPresetPrompt(id: SampleDatasetPresetId): Promise<string> {
  const mod = await PROMPT_LOADERS[id]()
  return parsePresetPrompt(mod.default)
}

export const SAMPLE_DATASET_PRESETS: SampleDatasetPreset[] = [
  {
    id: 'csv',
    label: 'CSV · HR',
    description: '4 CSV files in sample_dataset/csv/',
    tableMatchers: [
      'hr_employee_data',
      'employee_office_survey',
      'job_position_structure',
      'office_codes',
    ],
  },
  {
    id: 'db_test',
    label: 'PostgreSQL · HR',
    description: 'db_test demo Postgres (sample_dataset/db_test/)',
    tableMatchers: [
      'hr_employee_data',
      'employee_office_survey',
      'job_position_structure',
      'office_codes',
    ],
  },
  {
    id: 'parquet',
    label: 'Parquet · Retail',
    description: '4 parquet files in sample_dataset/parquet/',
    tableMatchers: [
      'customers',
      'products',
      'sales_transactions',
      'support_tickets',
    ],
  },
  {
    id: 'sqlite',
    label: 'SQLite · Inventory',
    description: 'inventory.db in sample_dataset/sqlite/',
    tableMatchers: ['inventory_inventory'],
  },
]

/** Resolve preset table matchers to registered view names (exact, then fuzzy). */
export function resolvePresetTables(
  availableTableNames: string[],
  matchers: string[]
): string[] {
  const resolved: string[] = []

  for (const matcher of matchers) {
    const exact = availableTableNames.find((name) => name === matcher)
    if (exact) {
      if (!resolved.includes(exact)) resolved.push(exact)
      continue
    }

    const fuzzy = availableTableNames.find(
      (name) =>
        name.includes(matcher) ||
        name.endsWith(`_${matcher}`) ||
        name === matcher
    )
    if (fuzzy && !resolved.includes(fuzzy)) resolved.push(fuzzy)
  }

  return resolved
}
