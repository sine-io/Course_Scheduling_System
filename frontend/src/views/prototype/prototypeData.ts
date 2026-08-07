import type { Component } from 'vue'
import {
  BookOpen,
  CalendarDays,
  ClipboardList,
  DoorOpen,
  LayoutDashboard,
  Settings2,
  Shuffle,
  Users,
} from '@lucide/vue'

// THROWAWAY PROTOTYPE: representative shapes only; no API or persistence.

export type ViewKey = 'dashboard' | 'workbench'
export type StatusMode = 'normal' | 'loading' | 'empty' | 'restricted' | 'error'
export type Tone = 'blue' | 'teal' | 'purple' | 'orange' | 'green' | 'red'

export interface NavItem {
  key: string
  label: string
  icon: Component
  view?: ViewKey
  badge?: string
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export interface Metric {
  label: string
  value: number
  detail: string
  icon: Component
  tone: Tone
}

export interface SubstitutionChange {
  id: number
  time: string
  className: string
  subject: string
  from: string
  to: string
  state: '待确认' | '已安排' | '已通知'
}

export interface CourseCell {
  id: string
  subject: string
  teacher: string
  room: string
  tone: Tone
  locked?: boolean
  conflict?: boolean
}

export interface ScheduleRow {
  period: string
  time: string
  cells: Array<CourseCell | null>
}

export interface VariantProps {
  activeView: ViewKey
  drawerOpen: boolean
  collapsed: boolean
  statusMode: StatusMode
  selectedCourseKey: string | null
}

export const variantNames = {
  A: '工作台主导',
  B: '上下文分栏',
  C: '聚焦画布',
} as const

export const navGroups: NavGroup[] = [
  {
    label: '概览',
    items: [
      { key: 'dashboard', label: '仪表盘', icon: LayoutDashboard, view: 'dashboard' },
    ],
  },
  {
    label: '基础数据',
    items: [
      { key: 'semester', label: '学期与作息', icon: CalendarDays },
      { key: 'basedata', label: '教师、班级与科目', icon: Users },
      { key: 'rooms', label: '教室与场地', icon: DoorOpen },
    ],
  },
  {
    label: '排课作业',
    items: [
      { key: 'assignments', label: '教学任务', icon: ClipboardList },
      { key: 'workbench', label: '排课工作台', icon: BookOpen, view: 'workbench', badge: '3' },
      { key: 'substitutions', label: '调课与代课', icon: Shuffle, badge: '2' },
    ],
  },
  {
    label: '系统管理',
    items: [
      { key: 'settings', label: '系统设置', icon: Settings2 },
    ],
  },
]

export const metrics: Metric[] = [
  { label: '科目', value: 42, detail: '本学期已配置', icon: BookOpen, tone: 'blue' },
  { label: '教师', value: 68, detail: '授课教师', icon: Users, tone: 'teal' },
  { label: '班级', value: 24, detail: '行政班与教学班', icon: ClipboardList, tone: 'purple' },
  { label: '教室 / 场地', value: 18, detail: '可排资源', icon: DoorOpen, tone: 'orange' },
]

export const substitutionChanges: SubstitutionChange[] = [
  { id: 1, time: '第 2 节', className: '八年级 2 班', subject: '数学', from: '张老师', to: '周老师', state: '已安排' },
  { id: 2, time: '第 3 节', className: '七年级 4 班', subject: '英语', from: '王老师', to: '陈老师', state: '待确认' },
  { id: 3, time: '第 5 节', className: '九年级 1 班', subject: '物理', from: '刘老师', to: '赵老师', state: '已通知' },
  { id: 4, time: '第 6 节', className: '八年级 5 班', subject: '语文', from: '李老师', to: '—', state: '待确认' },
]

export const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六']

export const scheduleRows: ScheduleRow[] = [
  {
    period: '第 1 节', time: '08:00–08:45',
    cells: [
      { id: 'a-1', subject: '语文', teacher: '李老师', room: 'A201', tone: 'blue', locked: true },
      { id: 'a-2', subject: '数学', teacher: '张老师', room: 'A201', tone: 'teal' },
      { id: 'a-3', subject: '英语', teacher: '王老师', room: 'A201', tone: 'purple' },
      { id: 'a-4', subject: '数学', teacher: '张老师', room: 'A201', tone: 'teal', locked: true },
      { id: 'a-5', subject: '语文', teacher: '李老师', room: 'A201', tone: 'blue' },
      { id: 'a-6', subject: '物理', teacher: '刘老师', room: 'B203', tone: 'orange' },
    ],
  },
  {
    period: '第 2 节', time: '08:55–09:40',
    cells: [
      { id: 'b-1', subject: '数学', teacher: '张老师', room: 'A201', tone: 'teal' },
      { id: 'b-2', subject: '英语', teacher: '王老师', room: 'A201', tone: 'purple' },
      { id: 'b-3', subject: '语文', teacher: '李老师', room: 'A201', tone: 'blue' },
      { id: 'b-4', subject: '道德与法治', teacher: '陈老师', room: 'A201', tone: 'orange' },
      { id: 'b-5', subject: '英语', teacher: '王老师', room: 'A201', tone: 'purple' },
      { id: 'b-6', subject: '体育', teacher: '赵老师', room: '操场', tone: 'green' },
    ],
  },
  {
    period: '第 3 节', time: '10:00–10:45',
    cells: [
      { id: 'c-1', subject: '物理', teacher: '刘老师', room: 'B203', tone: 'orange' },
      { id: 'c-2', subject: '历史', teacher: '周老师', room: 'A201', tone: 'purple' },
      { id: 'c-3', subject: '数学', teacher: '张老师', room: 'A201', tone: 'red', conflict: true },
      { id: 'c-4', subject: '生物', teacher: '孙老师', room: 'B204', tone: 'teal' },
      { id: 'c-5', subject: '化学', teacher: '赵老师', room: 'B205', tone: 'orange' },
      { id: 'c-6', subject: '信息技术', teacher: '吴老师', room: '机房 1', tone: 'blue' },
    ],
  },
  {
    period: '第 4 节', time: '10:55–11:40',
    cells: [
      { id: 'd-1', subject: '英语', teacher: '王老师', room: 'A201', tone: 'purple' },
      { id: 'd-2', subject: '地理', teacher: '林老师', room: 'B202', tone: 'blue' },
      { id: 'd-3', subject: '物理', teacher: '刘老师', room: 'B203', tone: 'orange' },
      { id: 'd-4', subject: '语文', teacher: '李老师', room: 'A201', tone: 'blue' },
      { id: 'd-5', subject: '生物', teacher: '孙老师', room: 'B204', tone: 'teal' },
      { id: 'd-6', subject: '音乐', teacher: '何老师', room: '音乐室', tone: 'purple' },
    ],
  },
  {
    period: '第 5 节', time: '14:00–14:45',
    cells: [
      { id: 'e-1', subject: '体育', teacher: '赵老师', room: '操场', tone: 'green' },
      { id: 'e-2', subject: '美术', teacher: '张老师', room: '美术室', tone: 'orange' },
      { id: 'e-3', subject: '信息技术', teacher: '吴老师', room: '机房 1', tone: 'blue' },
      { id: 'e-4', subject: '体育', teacher: '赵老师', room: '操场', tone: 'green' },
      { id: 'e-5', subject: '历史', teacher: '周老师', room: 'A201', tone: 'purple' },
      null,
    ],
  },
  {
    period: '第 6 节', time: '14:55–15:40',
    cells: [
      { id: 'f-1', subject: '班会', teacher: '李老师', room: 'A201', tone: 'blue' },
      { id: 'f-2', subject: '物理实验', teacher: '刘老师', room: '实验室 1', tone: 'orange' },
      { id: 'f-3', subject: '化学实验', teacher: '赵老师', room: '实验室 2', tone: 'orange' },
      { id: 'f-4', subject: '阅读', teacher: '王老师', room: '图书馆', tone: 'teal' },
      { id: 'f-5', subject: '自习', teacher: '张老师', room: 'A201', tone: 'purple' },
      null,
    ],
  },
]

export const unscheduledCourses = [
  { id: 'pool-1', subject: '八年级数学', teacher: '张老师', remaining: 2, tone: 'teal' as Tone },
  { id: 'pool-2', subject: '九年级化学', teacher: '赵老师', remaining: 1, tone: 'orange' as Tone },
  { id: 'pool-3', subject: '七年级音乐', teacher: '何老师', remaining: 2, tone: 'purple' as Tone },
]

export const shortcutItems = [
  { label: '进入排课工作台', detail: '处理未排课程与冲突', view: 'workbench' as ViewKey, tone: 'blue' as Tone },
  { label: '查看今日看板', detail: '确认调课与代课变动', view: 'dashboard' as ViewKey, tone: 'orange' as Tone },
  { label: '管理教学任务', detail: '检查教师与班级分配', view: 'dashboard' as ViewKey, tone: 'purple' as Tone },
]

export const stateOptions: Array<{ key: StatusMode; label: string }> = [
  { key: 'normal', label: '正常' },
  { key: 'loading', label: '加载' },
  { key: 'empty', label: '空状态' },
  { key: 'restricted', label: '权限受限' },
  { key: 'error', label: '请求失败' },
]
