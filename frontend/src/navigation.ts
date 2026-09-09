import {
  Bell,
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  ClipboardClock,
  ClipboardList,
  DatabaseBackup,
  History,
  LayoutDashboard,
  ListChecks,
  Settings2,
  ShieldCheck,
  Shuffle,
  Table2,
  Users,
  WandSparkles,
} from '@lucide/vue'
import type { Component } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import {
  CORE_VIEW_ROLES,
  DAILY_OPERATOR_ROLES,
  DAILY_USER_ROLES,
} from '@/permissions'

export type NavigationRole = 'admin' | 'director' | 'teacher'
export type NavigationKey =
  | 'dashboard'
  | 'semesters'
  | 'calendar'
  | 'basedata'
  | 'scheduling-flow'
  | 'assignments'
  | 'scheduling-settings'
  | 'auto-schedule'
  | 'workbench'
  | 'versions'
  | 'timetable-query'
  | 'leaves'
  | 'substitutions'
  | 'daily-board'
  | 'substitution-log'
  | 'notifications'
  | 'substitution-stats'
  | 'substitution-stats-mine'
  | 'system'
  | 'backup'
  | 'account-permissions'

export interface NavigationEntry {
  key: NavigationKey
  label: string
  description: string
  icon: Component
  group: string
  allowedRoles: readonly NavigationRole[]
  route: RouteLocationRaw
  activeNames?: readonly string[]
  discoverable?: boolean
}

function entry(
  key: NavigationKey,
  label: string,
  description: string,
  icon: Component,
  group: string,
  allowedRoles: readonly NavigationRole[],
  route: RouteLocationRaw,
  options: Pick<NavigationEntry, 'activeNames' | 'discoverable'> = {},
): NavigationEntry {
  return {
    key,
    label,
    description,
    icon,
    group,
    allowedRoles,
    route,
    ...options,
  }
}

/**
 * The catalog describes real pages only. The router remains the final
 * authorization boundary; this list controls what a signed-in user can
 * discover from the shell.
 */
export const NAVIGATION_CATALOG: readonly NavigationEntry[] = [
  entry('dashboard', '仪表盘', '查看当前学期摘要、角色快捷入口和可访问的今日运行。', LayoutDashboard, '工作空间', DAILY_USER_ROLES, { name: 'dashboard' }),
  entry('semesters', '学期与作息时间表', '管理学期、作息时间表和历史学期。', CalendarDays, '学期准备', CORE_VIEW_ROLES, { name: 'semesters' }, { activeNames: ['semesters', 'period-table-editor'] }),
  entry('calendar', '校历与排课准备', '维护校历特殊日期和学期准备状态。', CalendarCheck2, '学期准备', DAILY_OPERATOR_ROLES, { name: 'calendar' }),
  entry('basedata', '基础数据', '维护教师、科目和教室/场地；班级在开始排课中设置。', Users, '学期准备', CORE_VIEW_ROLES, { name: 'basedata' }),

  entry('scheduling-flow', '开始排课', '在一个工作台内完成班级、课时、科目节数、教师任课和排课。', ListChecks, '排课主流程', CORE_VIEW_ROLES, { name: 'scheduling-flow' }),
  entry('assignments', '科目与任课', '先录入每周课时，再补齐教师任课。', ClipboardList, '排课主流程', CORE_VIEW_ROLES, { name: 'assignments' }, { discoverable: false }),
  entry('auto-schedule', '自动排课', '查看前置检查结果并运行自动排课。', WandSparkles, '排课主流程', CORE_VIEW_ROLES, { name: 'auto-schedule' }, { discoverable: false }),
  entry('workbench', '课程表调整', '检查或调整课表草稿。', BookOpen, '排课主流程', CORE_VIEW_ROLES, { name: 'workbench' }),
  entry('versions', '版本与发布', '检查课表版本、完整性和发布记录。', History, '排课主流程', CORE_VIEW_ROLES, { name: 'versions' }),
  entry('scheduling-settings', '排课规则', '维护排课所需的课时和约束参数。', Settings2, '排课主流程', CORE_VIEW_ROLES, { name: 'scheduling-settings' }, { discoverable: false }),
  entry('timetable-query', '课表查询', '查询已发布的班级、教师和教室课表。', Table2, '排课主流程', DAILY_USER_ROLES, { name: 'timetable-query' }),

  entry('leaves', '请假登记', '登记本人或全校教师请假并查看受影响节次。', ClipboardClock, '日常运行', DAILY_USER_ROLES, { name: 'leaves' }),
  entry('substitutions', '调课与代课', '处理受影响节次、调课和代课安排。', Shuffle, '日常运行', DAILY_OPERATOR_ROLES, { name: 'substitutions' }),
  entry('daily-board', '今日看板', '查看今日调课与代课变动。', CalendarDays, '日常运行', DAILY_OPERATOR_ROLES, { name: 'daily-board' }),
  entry('substitution-log', '调课与代课记录', '查询已处理的日常运行记录。', History, '日常运行', DAILY_OPERATOR_ROLES, { name: 'substitution-log' }),
  entry('notifications', '通知', '阅读通知并确认本人收到的消息。', Bell, '日常运行', DAILY_USER_ROLES, { name: 'notifications' }),

  entry('substitution-stats', '代课课时统计', '查看全校代课汇总和明细。', ChartNoAxesColumnIncreasing, '报表', DAILY_OPERATOR_ROLES, { name: 'substitution-stats' }),
  entry('substitution-stats-mine', '我的代课课时', '查看本人代课明细和计费课时。', ChartNoAxesColumnIncreasing, '报表', ['teacher'], { name: 'substitution-stats' }),

  entry('system', '系统管理', '维护学校信息、通知设置和系统参数。', Settings2, '系统管理', ['admin'], { name: 'system' }),
  entry('backup', '备份恢复', '管理系统数据备份、下载与恢复。', DatabaseBackup, '系统管理', ['admin'], { name: 'backup' }),
  entry('account-permissions', '账号权限', '维护系统账号、角色和访问状态。', ShieldCheck, '系统管理', ['admin'], { name: 'account-permissions' }),
]

const byKey = new Map(NAVIGATION_CATALOG.map((item) => [item.key, item]))

export function hasNavigationAccess(
  roles: readonly string[] | null | undefined,
  item: NavigationEntry,
): boolean {
  if (!roles?.length) return false
  return item.allowedRoles.some((role) => roles.includes(role))
}

export function getNavigationEntry(key: string): NavigationEntry | undefined {
  return byKey.get(key as NavigationKey)
}

export function isNavigationEntryActive(
  item: NavigationEntry,
  routeName: string,
  query: Readonly<Record<string, unknown>> = {},
  firstSuccess: boolean | null = null,
): boolean {
  // Keep the former arguments source-compatible while phase/query state no longer affects navigation.
  void query
  void firstSuccess
  const routeObject = typeof item.route === 'object' ? item.route : null
  const configuredName = routeObject && 'name' in routeObject ? String(routeObject.name) : ''
  const activeNames = item.activeNames ?? [configuredName]
  return activeNames.includes(routeName)
}

export function accessibleCatalog(
  roles: readonly string[] | null | undefined,
): NavigationEntry[] {
  return NAVIGATION_CATALOG.filter((item) => hasNavigationAccess(roles, item))
}

export function navigationGroupOrder(): readonly string[] {
  return ['工作空间', '学期准备', '排课主流程', '日常运行', '报表', '系统管理']
}

export function navigationGroupEntries(
  roles: readonly string[] | null | undefined,
): { label: string; items: NavigationEntry[] }[] {
  const entries = accessibleCatalog(roles).filter((item) => item.discoverable !== false)
  return navigationGroupOrder()
    .map((label) => ({ label, items: entries.filter((item) => item.group === label) }))
    .filter((group) => group.items.length > 0)
}
