export type CsvLiteTestId =
  | 'task_1'
  | 'task_2'
  | 'task_3'
  | 'task_4'
  | 'task_5'
  | 'task_6'

export type CsvLiteTest = {
  id: CsvLiteTestId
  label: string
}

const LITE_TEST_LOADERS: Record<
  CsvLiteTestId,
  () => Promise<{ default: string }>
> = {
  task_1: () => import('@sample-dataset/csv/task_1.md?raw'),
  task_2: () => import('@sample-dataset/csv/task_2.md?raw'),
  task_3: () => import('@sample-dataset/csv/task_3.md?raw'),
  task_4: () => import('@sample-dataset/csv/task_4.md?raw'),
  task_5: () => import('@sample-dataset/csv/task_5.md?raw'),
  task_6: () => import('@sample-dataset/csv/task_6.md?raw'),
}

export const CSV_LITE_TESTS: CsvLiteTest[] = [
  { id: 'task_1', label: 'Lite 1 · Scatter plot' },
  { id: 'task_2', label: 'Lite 2 · Chi-square' },
  { id: 'task_3', label: 'Lite 3 · Performance vs training' },
  { id: 'task_4', label: 'Lite 4 · Attrition boxplot' },
  { id: 'task_5', label: 'Lite 5 · Manager satisfaction' },
  { id: 'task_6', label: 'Lite 6 · Job satisfaction t-test' },
]

/** Load a one-line lite test prompt from sample_dataset/csv/task_*.md */
export async function loadLiteTestPrompt(id: CsvLiteTestId): Promise<string> {
  const mod = await LITE_TEST_LOADERS[id]()
  return mod.default.trim()
}
