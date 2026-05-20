/** Shared report block shape used by agent runs and legacy analysis UI. */
export type ReportBlock =
  | { type: 'markdown'; content: string }
  | { type: 'image'; base64: string }
  | { type: 'table'; table: string }
  | { type: 'variable'; data: string }

/** Alias used by legacy hooks — same discriminated union as ReportBlock. */
export type ReportContent = ReportBlock

export interface ActionStep {
  type: string
  query?: string
  python?: string
  content?: string
}
