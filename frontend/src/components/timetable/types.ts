// TimetableGrid 组件的共用类型。此组件为纯展示+事件组件,不含商业逻辑:
// 拖拽中的内容、冲突判定、放下结果统一由父层决定并以 props/events 沟通。

export interface PeriodCell {
  weekday: number // 1=周一 …
  period_no: number // 当日节次顺序(含休息时段)
  name: string // 显示名称,如「第一节」「午休」
  type: string // 'regular'(可排课)| morning/lunch/homeroom/reserved(反灰)
  start_time?: string | null // 'HH:MM' 或 'HH:MM:SS'
  end_time?: string | null
}

export interface GridEntry {
  id: number | string
  weekday: number
  period_no: number
  subject: string
  teacher?: string
  room?: string
  locked?: boolean
  span?: number // 连堂长度(占用连续节数),默认 1
}

// 拖拽中的内容(对组件不透明,仅用于返回给父层决策)
export interface DragData {
  source: 'tray' | 'grid'
  entryId?: number | string
  [k: string]: unknown
}

export interface DropTarget {
  weekday: number
  period_no: number
}

// 父层在拖拽过程回填的可放/冲突判定,组件据此渲染绿框/红框与原因
export interface DropFeedback extends DropTarget {
  ok: boolean
  reason?: string
}

export interface DragEventPayload extends DropTarget {
  data: DragData | null
}
