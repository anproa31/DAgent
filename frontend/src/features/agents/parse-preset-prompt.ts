const PRESET_SECTION = '## Preset prompt'

/** Extract the agent prompt from a sample_dataset `prompt.md` file. */
export function parsePresetPrompt(markdown: string): string {
  const idx = markdown.indexOf(PRESET_SECTION)
  if (idx === -1) return markdown.trim()

  let body = markdown.slice(idx + PRESET_SECTION.length).trim()
  const nextSection = body.search(/\n## /)
  if (nextSection !== -1) {
    body = body.slice(0, nextSection).trim()
  }
  return body
}
