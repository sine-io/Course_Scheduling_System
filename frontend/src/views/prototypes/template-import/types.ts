export type ImportMode = 'standard' | 'ready'

export type FileState = 'issues' | 'fixed' | 'committed'

export type IssueSeverity = 'blocker' | 'warning'

export interface PrototypeState {
  mode: ImportMode
  fileName: string
  fileState: FileState
  selectedSheet: string
  selectedIssueId: string
  issueFilter: 'all' | IssueSeverity
  readinessConfirmed: boolean
  lastAction: string
}

export interface IssueRow {
  id: string
  severity: IssueSeverity
  sheet: string
  row: number
  field: string
  value: string
  title: string
  detail: string
  suggestion: string
  readyOnly?: boolean
  standardSeverity?: IssueSeverity
}

export interface ChangeRow {
  code: string
  entity: string
  className: string
  subject: string
  component: string
  periods: number
  teacher: string
  status: 'new' | 'changed' | 'unchanged' | 'disappeared'
}

export interface SheetSummary {
  name: string
  rows: number
  status: 'ok' | 'attention' | 'optional'
  note: string
}

export interface ImportCounts {
  blockers: number
  warnings: number
  newRecords: number
  changedRecords: number
  unchangedRecords: number
  disappearedRecords: number
}

export interface PrototypeViewProps {
  state: PrototypeState
  issues: IssueRow[]
  changes: ChangeRow[]
  sheets: SheetSummary[]
  counts: ImportCounts
}
