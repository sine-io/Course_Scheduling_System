import {
  Bell,
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  ClipboardClock,
  ClipboardList,
  DatabaseBackup,
  FileQuestion,
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

export type NavigationRole = 'admin' | 'scheduler' | 'director' | 'teacher'
export type NavigationPhase = 'before-first-success' | 'after-first-success'
export type NavigationKey =
  | 'dashboard'
  | 'wizard'
  | 'semesters'
  | 'calendar'
  | 'basedata'
  | 'assignments'
  | 'auto-schedule'
  | 'workbench'
  | 'versions'
  | 'timetable-query'
  | 'timetable-demo'
  | 'leaves'
  | 'substitutions'
  | 'daily-board'
  | 'substitution-log'
  | 'notifications'
  | 'notification-board'
  | 'substitution-stats'
  | 'substitution-stats-mine'
  | 'system'
  | 'backup'
  | 'account-permissions'
  | 'help-guide'
  | 'current-todo'
  | 'daily-operations'

export interface NavigationEntry {
  key: NavigationKey
  label: string
  description: string
  icon: Component
  group: string
  allowedRoles: readonly NavigationRole[]
  route: RouteLocationRaw
  /** Keep phase aliases out of the full directory while exposing them in Common. */
  commonOnly?: boolean
  activeNames?: readonly string[]
  activeSection?: string
  phase?: NavigationPhase
  dynamicNextAction?: boolean
}

export interface NavigationPreference {
  /** Explicitly fixed entries, in the order chosen by the user. */
  fixed: string[]
  /** Recently opened entries, newest first. */
  recent: string[]
}

export const NAVIGATION_STORAGE_PREFIX = 'course-scheduling:navigation:'
export const COMMON_NAV_LIMIT = 5

function entry(
  key: NavigationKey,
  label: string,
  description: string,
  icon: Component,
  group: string,
  allowedRoles: readonly NavigationRole[],
  route: RouteLocationRaw,
  options: Pick<
    NavigationEntry,
    'commonOnly' | 'activeNames' | 'activeSection' | 'phase' | 'dynamicNextAction'
  > = {},
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
 * The catalog is deliberately data-first.  The router remains the final
 * authorization boundary; this list only controls what a signed-in user can
 * discover from the shell.
 */
export const NAVIGATION_CATALOG: readonly NavigationEntry[] = [
  entry('dashboard', '仪表盘', '查看当前学期摘要、首次成功状态和今日运行。', LayoutDashboard, '学期准备', CORE_VIEW_ROLES, { name: 'dashboard' }),
  entry('wizard', '上手指南', '继续设置向导并恢复中断的首次配置。', ListChecks, '学期准备', ['admin', 'scheduler', 'director'], { name: 'wizard' }),
  entry('semesters', '学期与作息时间表', '管理学期、作息时间表和历史学期。', CalendarDays, '学期准备', CORE_VIEW_ROLES, { name: 'semesters' }, { activeNames: ['semesters', 'period-table-editor'] }),
  entry('calendar', '校历与排课准备', '维护校历特殊日期和学期准备状态。', CalendarCheck2, '学期准备', DAILY_OPERATOR_ROLES, { name: 'calendar' }),
  entry('basedata', '基础数据', '维护教师、班级、科目和教室/场地。', Users, '学期准备', CORE_VIEW_ROLES, { name: 'basedata' }),

  entry('assignments', '教学任务', '维护每周课时、教师和班级的教学安排。', ClipboardList, '排课主流程', CORE_VIEW_ROLES, { name: 'assignments' }),
  entry('auto-schedule', '自动排课', '查看前置检查结果，并由排课管理员运行自动排课。', WandSparkles, '排课主流程', CORE_VIEW_ROLES, { name: 'auto-schedule' }),
  entry('workbench', '排课工作台', '查看或编辑课表草稿。', BookOpen, '排课主流程', CORE_VIEW_ROLES, { name: 'workbench' }),
  entry('versions', '版本与发布', '检查课表版本、完整性和发布记录。', History, '排课主流程', CORE_VIEW_ROLES, { name: 'versions' }),
  entry('timetable-query', '课表查询', '查询已发布的班级、教师和教室课表。', Table2, '排课主流程', DAILY_USER_ROLES, { name: 'timetable-query' }),
  entry('timetable-demo', '课表组件（演示）', '查看课表网格组件的交互示例。', Table2, '排课主流程', CORE_VIEW_ROLES, { name: 'timetable-demo' }),

  entry('leaves', '请假登记', '登记本人或全校教师请假并查看受影响节次。', ClipboardClock, '日常运行', DAILY_USER_ROLES, { name: 'leaves' }),
  entry('substitutions', '调课与代课', '处理受影响节次、调课和代课安排。', Shuffle, '日常运行', DAILY_OPERATOR_ROLES, { name: 'substitutions' }),
  entry('daily-board', '今日看板', '查看今日调课与代课变动。', CalendarDays, '日常运行', DAILY_OPERATOR_ROLES, { name: 'daily-board' }),
  entry('substitution-log', '调课与代课记录', '查询已处理的日常运行记录。', History, '日常运行', DAILY_OPERATOR_ROLES, { name: 'substitution-log' }),
  entry('notifications', '通知', '阅读通知并确认本人收到的消息。', Bell, '日常运行', DAILY_USER_ROLES, { name: 'notifications' }),
  entry('notification-board', '通知确认看板', '查看全校通知确认状态并再次提醒。', Bell, '日常运行', DAILY_OPERATOR_ROLES, { name: 'notification-board' }),

  entry('substitution-stats', '代课课时统计', '查看全校代课汇总和明细。', ChartNoAxesColumnIncreasing, '报表', DAILY_OPERATOR_ROLES, { name: 'substitution-stats' }),
  entry('substitution-stats-mine', '我的代课课时', '查看本人代课明细和计费课时。', ChartNoAxesColumnIncreasing, '报表', ['teacher'], { name: 'substitution-stats' }),

  entry('system', '系统管理', '维护学校信息、通知设置和系统参数。', Settings2, '系统管理', ['admin'], { name: 'system' }, { activeSection: '' }),
  // These aliases keep high-risk actions inside the existing confirmed System
  // page. They are never rendered in the top toolbar.
  entry('backup', '备份恢复', '进入系统管理中的数据备份与恢复区域。', DatabaseBackup, '系统管理', ['admin'], { name: 'system', query: { section: 'backup' } }, { activeSection: 'backup' }),
  entry('account-permissions', '账号权限', '查看系统管理中的账号与角色入口。', ShieldCheck, '系统管理', ['admin'], { name: 'system', query: { section: 'accounts' } }, { activeSection: 'accounts' }),
  entry('help-guide', '上手指南', '重新打开设置向导和首次成功路径。', FileQuestion, '系统管理', ['admin'], { name: 'wizard' }),

  // Phase aliases are shown only in the Common section. Keeping them in the
  // same catalog lets preference validation use exactly the same permission
  // and route definitions as the full directory.
  entry('current-todo', '当前待办', '打开首次成功路径中的唯一下一步。', ListChecks, '学期准备', ['admin', 'scheduler'], { name: 'dashboard' }, {
    activeNames: ['dashboard'],
    commonOnly: true,
    dynamicNextAction: true,
    phase: 'before-first-success',
  }),
  entry('daily-operations', '今日运行', '打开今日看板和正在处理的运行工作。', CalendarDays, '日常运行', DAILY_OPERATOR_ROLES, { name: 'daily-board' }, { commonOnly: true }),
]

const byKey = new Map(NAVIGATION_CATALOG.map((item) => [item.key, item]))

const SCHEDULER_BEFORE: readonly NavigationKey[] = [
  'current-todo', 'assignments', 'auto-schedule', 'workbench', 'versions',
]
const SCHEDULER_AFTER: readonly NavigationKey[] = [
  'dashboard', 'timetable-query', 'daily-board', 'substitutions', 'versions',
]
const DIRECTOR_DEFAULT: readonly NavigationKey[] = [
  'dashboard', 'timetable-query', 'daily-board', 'versions', 'substitution-stats',
]
const TEACHER_DEFAULT: readonly NavigationKey[] = [
  'timetable-query', 'leaves', 'notifications', 'substitution-stats-mine',
]
const ADMIN_BEFORE: readonly NavigationKey[] = [
  'dashboard', 'system', 'backup', 'account-permissions', 'help-guide',
]
const ADMIN_AFTER: readonly NavigationKey[] = [
  'dashboard', 'system', 'backup', 'account-permissions', 'timetable-query',
]

export function hasNavigationAccess(
  roles: readonly string[] | null | undefined,
  item: NavigationEntry,
): boolean {
  if (!roles?.length) return false
  return item.allowedRoles.some((role) => roles.includes(role))
}

export function navigationPerspective(
  roles: readonly string[] | null | undefined,
): 'admin' | 'scheduler' | 'director' | 'teacher' | null {
  if (!roles?.length) return null
  if (roles.includes('admin')) return 'admin'
  if (roles.includes('scheduler')) return 'scheduler'
  if (roles.includes('director')) return 'director'
  if (roles.includes('teacher')) return 'teacher'
  return null
}

export function defaultNavigationKeys(
  roles: readonly string[] | null | undefined,
  firstSuccess: boolean,
): NavigationKey[] {
  const perspective = navigationPerspective(roles)
  if (perspective === 'admin') return [...(firstSuccess ? ADMIN_AFTER : ADMIN_BEFORE)]
  if (perspective === 'scheduler') return [...(firstSuccess ? SCHEDULER_AFTER : SCHEDULER_BEFORE)]
  if (perspective === 'director') return [...DIRECTOR_DEFAULT]
  if (perspective === 'teacher') return [...TEACHER_DEFAULT]
  return []
}

export function getNavigationEntry(key: string): NavigationEntry | undefined {
  return byKey.get(key as NavigationKey)
}

export function navigationTarget(
  item: NavigationEntry,
  nextActionHref?: string,
): RouteLocationRaw {
  if (item.dynamicNextAction && nextActionHref) return nextActionHref
  return item.route
}

export function isNavigationEntryActive(
  item: NavigationEntry,
  routeName: string,
  query: Readonly<Record<string, unknown>>,
  firstSuccess: boolean | null,
): boolean {
  if (!isNavigationEntryApplicable(item, firstSuccess)) return false

  const routeObject = typeof item.route === 'object' ? item.route : null
  const configuredName = routeObject && 'name' in routeObject ? String(routeObject.name) : ''
  const activeNames = item.activeNames ?? [configuredName]
  if (!activeNames.includes(routeName)) return false
  if (item.activeSection !== undefined) {
    return String(query.section ?? '') === item.activeSection
  }
  return true
}

export function accessibleCatalog(
  roles: readonly string[] | null | undefined,
): NavigationEntry[] {
  return NAVIGATION_CATALOG.filter((item) => (
    !item.commonOnly && hasNavigationAccess(roles, item)
  ))
}

export function accessibleEntries(
  roles: readonly string[] | null | undefined,
): NavigationEntry[] {
  return NAVIGATION_CATALOG.filter((item) => hasNavigationAccess(roles, item))
}

export function isNavigationEntryApplicable(
  item: NavigationEntry,
  firstSuccess: boolean | null,
): boolean {
  if (item.phase && firstSuccess === null) return false
  if (item.phase === 'before-first-success') return firstSuccess === false
  if (item.phase === 'after-first-success') return firstSuccess === true
  return true
}

export function applicableEntries(
  roles: readonly string[] | null | undefined,
  firstSuccess: boolean | null,
): NavigationEntry[] {
  return accessibleEntries(roles).filter((item) => (
    isNavigationEntryApplicable(item, firstSuccess)
  ))
}

export function commonNavigation(
  roles: readonly string[] | null | undefined,
  firstSuccess: boolean | null,
  preference: NavigationPreference,
): NavigationEntry[] {
  const allowed = new Set<string>(applicableEntries(roles, firstSuccess).map((item) => item.key))
  const defaults = defaultNavigationKeys(roles, firstSuccess === true).filter((key) => allowed.has(key))
  const fixed = preference.fixed.filter((key) => allowed.has(key))
  const recent = preference.recent.filter((key) => allowed.has(key))

  // A fixed list is authoritative, while missing slots are filled by the
  // current phase defaults and only then by recent visits.
  const keys: string[] = []
  for (const key of [...fixed, ...defaults, ...recent]) {
    if (!keys.includes(key)) keys.push(key)
    if (keys.length >= COMMON_NAV_LIMIT) break
  }
  return keys
    .map((key) => getNavigationEntry(key))
    .filter((item): item is NavigationEntry => item !== undefined)
}

export function normalizeNavigationPreference(
  value: unknown,
  roles: readonly string[] | null | undefined,
): NavigationPreference {
  const allowed = new Set<string>(accessibleEntries(roles).map((item) => item.key))
  const candidate = value && typeof value === 'object' ? value as Partial<NavigationPreference> : {}
  const fixed = Array.isArray(candidate.fixed)
    ? candidate.fixed.filter((key): key is string => typeof key === 'string' && allowed.has(key))
    : []
  const recent = Array.isArray(candidate.recent)
    ? candidate.recent.filter((key): key is string => typeof key === 'string' && allowed.has(key))
    : []
  return {
    fixed: [...new Set(fixed)].slice(0, COMMON_NAV_LIMIT),
    recent: [...new Set(recent)].slice(0, 20),
  }
}

export function emptyNavigationPreference(): NavigationPreference {
  return { fixed: [], recent: [] }
}

export function navigationStorageKey(userId: number | string): string {
  return `${NAVIGATION_STORAGE_PREFIX}${userId}`
}

export function loadNavigationPreference(
  userId: number | string,
  roles: readonly string[] | null | undefined,
): NavigationPreference {
  if (typeof window === 'undefined') return emptyNavigationPreference()
  try {
    const raw = window.localStorage.getItem(navigationStorageKey(userId))
    return normalizeNavigationPreference(raw ? JSON.parse(raw) : null, roles)
  } catch {
    return emptyNavigationPreference()
  }
}

export function saveNavigationPreference(
  userId: number | string,
  value: NavigationPreference,
  roles: readonly string[] | null | undefined,
): NavigationPreference {
  const normalized = normalizeNavigationPreference(value, roles)
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(navigationStorageKey(userId), JSON.stringify(normalized))
    } catch {
      // Private browsing and storage quotas should not disable navigation.
    }
  }
  return normalized
}

export function recordNavigationVisit(
  userId: number | string,
  key: NavigationKey,
  roles: readonly string[] | null | undefined,
): NavigationPreference {
  const current = loadNavigationPreference(userId, roles)
  return saveNavigationPreference(userId, {
    ...current,
    recent: [key, ...current.recent.filter((item) => item !== key)],
  }, roles)
}

export function navigationGroupOrder(): readonly string[] {
  return ['学期准备', '排课主流程', '日常运行', '报表', '系统管理']
}

export function navigationGroupEntries(
  roles: readonly string[] | null | undefined,
): { label: string; items: NavigationEntry[] }[] {
  const entries = accessibleCatalog(roles)
  return navigationGroupOrder()
    .map((label) => ({ label, items: entries.filter((item) => item.group === label) }))
    .filter((group) => group.items.length > 0)
}
