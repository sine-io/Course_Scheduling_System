// 教学任务(排课单位 / 教学任务 / 课时统计)API 类型与调用封装。

import { apiGet, apiPost, apiPut, request } from '@/api/client'
import type { RoomType } from '@/api/basedata'

export interface ClassBrief {
  id: number
  name: string
  grade: number
}
export interface SchedulingUnit {
  id: number
  semester_id: number
  unit_type: 'single' | 'group'
  name: string
  classes: ClassBrief[]
}
export interface AssignmentTeacher {
  teacher_id: number
  is_lead: boolean
  name: string
}
export interface BlockRule {
  id?: number
  block_size: number
  count_per_week: number
}
export interface Assignment {
  id: number
  semester_id: number
  scheduling_unit: SchedulingUnit
  subject: { id: number; name: string }
  periods_per_week: number
  required_room_type: RoomType | null
  room_id: number | null
  lock_room: boolean
  teachers: AssignmentTeacher[]
  block_rules: BlockRule[]
}
export interface TeacherLoad {
  teacher_id: number
  name: string
  base_periods: number
  admin_reduction: number
  target: number
  assigned: number
  delta: number
  max_overtime: number // 超课时上限；0 表示学校未设限
  over_limit: boolean  // delta 已超过上限
}
export interface ClassLoad {
  class_id: number
  name: string
  grade: number
  assigned: number
  capacity: number
  over_capacity: boolean
}

export interface AssignmentPayload {
  class_id?: number | null
  scheduling_unit_id?: number | null
  subject_id: number
  periods_per_week: number
  teachers: { teacher_id: number; is_lead: boolean }[]
  block_rules: { block_size: number; count_per_week: number }[]
  required_room_type?: RoomType | null
  room_id?: number | null
  lock_room?: boolean
}

// ── 走班群组 ──
export const listGroups = (semesterId: number) =>
  apiGet<SchedulingUnit[]>(`/scheduling-units?semester_id=${semesterId}`)
export const createGroup = (semesterId: number, body: { name: string; class_ids: number[] }) =>
  apiPost<SchedulingUnit>(`/scheduling-units?semester_id=${semesterId}`, body)
export const deleteGroup = (id: number) => request<void>('DELETE', `/scheduling-units/${id}`)

// ── 教学任务 ──
export const listAssignments = (semesterId: number) =>
  apiGet<Assignment[]>(`/assignments?semester_id=${semesterId}`)
export const createAssignment = (semesterId: number, body: AssignmentPayload) =>
  apiPost<Assignment>(`/assignments?semester_id=${semesterId}`, body)
export const updateAssignment = (id: number, body: AssignmentPayload) =>
  request<Assignment>('PATCH', `/assignments/${id}`, body)
export const deleteAssignment = (id: number) => request<void>('DELETE', `/assignments/${id}`)

// ── 统计 ──
export const teacherLoad = (semesterId: number) =>
  apiGet<TeacherLoad[]>(`/assignments/teacher-load?semester_id=${semesterId}`)
export const classLoad = (semesterId: number) =>
  apiGet<ClassLoad[]>(`/assignments/class-load?semester_id=${semesterId}`)

// ── 排课设置（管理员）──
export interface SchedulingSettings {
  /** 教师教学任务最多可超过应授课时的数量，0 表示不限制。 */
  max_overtime: number
}
export const getSchedulingSettings = () =>
  apiGet<SchedulingSettings>('/settings/scheduling')
export const saveSchedulingSettings = (body: SchedulingSettings) =>
  apiPut<SchedulingSettings>('/settings/scheduling', body)

// ── 示例数据（管理员，仅限全新系统）──
export interface DemoDataStatus {
  available: boolean
  reason: string
  school_name: string
}
export interface DemoDataResult {
  semester_id: number
  school_name: string
  classes: number
  teachers: number
  subjects: number
  rooms: number
  assignments: number
  total_periods: number
  max_overtime_used: number
  under_target: number
}
export const demoDataStatus = () => apiGet<DemoDataStatus>('/demo-data')
export const loadDemoData = () => apiPost<DemoDataResult>('/demo-data')

// ── 学校信息（管理员）──
export interface SchoolSettings {
  /** 学校名称，显示在系统界面、导出课表、通知邮件和打印公告中。 */
  school_name: string
}
export const getSchoolSettings = () => apiGet<SchoolSettings>('/settings/school')
export const saveSchoolSettings = (body: SchoolSettings) =>
  apiPut<SchoolSettings>('/settings/school', body)
