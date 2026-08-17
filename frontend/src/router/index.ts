import { createRouter, createWebHistory } from 'vue-router'
import {
  canUseDaily,
  canViewCore,
  CORE_VIEW_ROLES,
  DAILY_OPERATOR_ROLES,
  DAILY_USER_ROLES,
  hasAnyRole,
} from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useWizardStore } from '@/stores/wizard'

const ALL_DAILY_ROLES = [...DAILY_USER_ROLES]
const CORE_VIEW_ROLE_LIST = [...CORE_VIEW_ROLES]
const DAILY_OPERATOR_ROLE_LIST = [...DAILY_OPERATOR_ROLES]

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/change-password',
    name: 'change-password',
    component: () => import('@/views/ChangePassword.vue'),
  },
  {
    path: '/wizard',
    name: 'wizard',
    component: () => import('@/views/wizard/Wizard.vue'),
    meta: { allowedRoles: ['admin', 'scheduler', 'director'] },
  },
  {
    // 独立 A4 通知单打印页,不套用侧边栏版面(干净一页供打印)
    path: '/daily-board/print',
    name: 'daily-board-print',
    component: () => import('@/views/substitution/DailyBoardPrint.vue'),
    meta: { allowedRoles: DAILY_OPERATOR_ROLE_LIST },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { allowedRoles: ALL_DAILY_ROLES },
      },
      {
        path: 'settings/semesters',
        name: 'semesters',
        component: () => import('@/views/settings/Semesters.vue'),
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'settings/calendar',
        name: 'calendar',
        component: () => import('@/views/settings/Calendar.vue'),
        meta: { allowedRoles: DAILY_OPERATOR_ROLE_LIST },
      },
      {
        path: 'basedata',
        name: 'basedata',
        component: () => import('@/views/basedata/BaseData.vue'),
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'scheduling/assignments',
        name: 'assignments',
        component: () => import('@/views/scheduling/Assignments.vue'),
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'timetable-query',
        name: 'timetable-query',
        component: () => import('@/views/TimetableQuery.vue'),
        meta: { allowedRoles: ALL_DAILY_ROLES },
      },
      {
        path: 'notifications',
        name: 'notifications',
        component: () => import('@/views/Notifications.vue'),
        meta: { allowedRoles: ALL_DAILY_ROLES },
      },
      {
        path: 'scheduling/workbench',
        name: 'workbench',
        component: () => import('@/views/scheduling/Workbench.vue'),
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'scheduling/auto',
        name: 'auto-schedule',
        component: () => import('@/views/scheduling/AutoSchedule.vue'),
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'leaves',
        name: 'leaves',
        component: () => import('@/views/leaves/Leaves.vue'),
        meta: { allowedRoles: ALL_DAILY_ROLES },
      },
      {
        path: 'substitutions',
        name: 'substitutions',
        component: () => import('@/views/substitution/Substitutions.vue'),
        meta: { allowedRoles: DAILY_OPERATOR_ROLE_LIST },
      },
      {
        path: 'notification-board',
        name: 'notification-board-legacy',
        redirect: { name: 'notifications', query: { view: 'board' } },
        meta: { allowedRoles: DAILY_OPERATOR_ROLE_LIST },
      },
      {
        path: 'daily-board',
        name: 'daily-board',
        component: () => import('@/views/substitution/DailyBoard.vue'),
        meta: { allowedRoles: DAILY_OPERATOR_ROLE_LIST },
      },
      {
        path: 'substitution-log',
        name: 'substitution-log',
        component: () => import('@/views/substitution/SubstitutionLog.vue'),
        meta: { allowedRoles: DAILY_OPERATOR_ROLE_LIST },
      },
      {
        path: 'substitution-stats',
        name: 'substitution-stats',
        component: () => import('@/views/substitution/SubstitutionStats.vue'),
        meta: { allowedRoles: ALL_DAILY_ROLES },
      },
      {
        path: 'scheduling/versions',
        name: 'versions',
        component: () => import('@/views/scheduling/Versions.vue'),
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'scheduling/timetable-demo',
        name: 'timetable-demo-legacy',
        redirect: { name: 'workbench' },
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'settings/period-tables/:id',
        name: 'period-table-editor',
        component: () => import('@/views/settings/PeriodTableEditor.vue'),
        meta: { allowedRoles: CORE_VIEW_ROLE_LIST },
      },
      {
        path: 'settings/system',
        name: 'system',
        component: () => import('@/views/settings/System.vue'),
        meta: { allowedRoles: ['admin'] },
      },
      {
        path: 'settings/backup',
        name: 'backup',
        component: () => import('@/views/settings/System.vue'),
        meta: { allowedRoles: ['admin'], settingsSection: 'backup' },
      },
      {
        path: 'settings/accounts',
        name: 'account-permissions',
        component: () => import('@/views/settings/System.vue'),
        meta: { allowedRoles: ['admin'], settingsSection: 'accounts' },
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

const AUTH_PAGES = new Set(['login', 'change-password'])

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.loaded) {
    await auth.fetchMe()
  }

  if (to.meta.public) {
    if (auth.isAuthenticated && to.name === 'login') {
      return { name: auth.mustChangePassword ? 'change-password' : 'dashboard' }
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return { name: 'login' }
  }
  if (auth.mustChangePassword && to.name !== 'change-password') {
    return { name: 'change-password' }
  }
  if (!auth.mustChangePassword && to.name === 'change-password') {
    return { name: 'dashboard' }
  }

  if (to.name === 'system' && (to.query.section === 'backup' || to.query.section === 'accounts')) {
    return {
      name: to.query.section === 'backup' ? 'backup' : 'account-permissions',
    }
  }

  const allowedRoles = to.meta.allowedRoles as string[] | undefined
  const canManage = canViewCore(auth.user?.roles)
  // 未声明教师角色的页面不对纯教师账号开放；页面权限只维护在路由元数据中。
  if (!canManage && auth.hasRole('teacher') && !allowedRoles?.includes('teacher')) {
    return { name: 'timetable-query' }
  }

  if (allowedRoles && !hasAnyRole(auth.user?.roles, allowedRoles)) {
    const fallback = canManage
      ? 'dashboard'
      : canUseDaily(auth.user?.roles) ? 'timetable-query' : 'dashboard'
    return { name: fallback }
  }

  // 首次登录引导:排课管理员/管理员在尚未完成初始设置时,自动进入向导(向导内可跳过)
  const canSetup = auth.hasRole('scheduler') || auth.hasRole('admin')
  if (canSetup && to.name !== 'wizard' && !AUTH_PAGES.has(to.name as string)) {
    const wizard = useWizardStore()
    if (!wizard.loaded) await wizard.fetch()
    if (wizard.state && !wizard.state.completed) {
      return { name: 'wizard' }
    }
  }
  return true
})
