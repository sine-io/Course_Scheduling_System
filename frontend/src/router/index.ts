import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWizardStore } from '@/stores/wizard'

const routes = [
  {
    // THROWAWAY PROTOTYPE: deliberately bypasses auth/API so the visual review runs standalone.
    path: '/prototype/ui-style',
    name: 'prototype-ui-style',
    component: () => import('@/views/prototype/UiStylePrototype.vue'),
    meta: { public: true, prototype: true },
  },
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
  },
  {
    // 独立 A4 通知单打印页,不套用侧边栏版面(干净一页供打印)
    path: '/daily-board/print',
    name: 'daily-board-print',
    component: () => import('@/views/substitution/DailyBoardPrint.vue'),
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/Dashboard.vue'),
      },
      {
        path: 'settings/semesters',
        name: 'semesters',
        component: () => import('@/views/settings/Semesters.vue'),
      },
      {
        path: 'settings/calendar',
        name: 'calendar',
        component: () => import('@/views/settings/Calendar.vue'),
      },
      {
        path: 'basedata',
        name: 'basedata',
        component: () => import('@/views/basedata/BaseData.vue'),
      },
      {
        path: 'scheduling/assignments',
        name: 'assignments',
        component: () => import('@/views/scheduling/Assignments.vue'),
      },
      {
        path: 'timetable-query',
        name: 'timetable-query',
        component: () => import('@/views/TimetableQuery.vue'),
      },
      {
        path: 'scheduling/workbench',
        name: 'workbench',
        component: () => import('@/views/scheduling/Workbench.vue'),
      },
      {
        path: 'scheduling/auto',
        name: 'auto-schedule',
        component: () => import('@/views/scheduling/AutoSchedule.vue'),
      },
      {
        path: 'leaves',
        name: 'leaves',
        component: () => import('@/views/leaves/Leaves.vue'),
      },
      {
        path: 'substitutions',
        name: 'substitutions',
        component: () => import('@/views/substitution/Substitutions.vue'),
      },
      {
        path: 'notification-board',
        name: 'notification-board',
        component: () => import('@/views/substitution/NotificationBoard.vue'),
      },
      {
        path: 'daily-board',
        name: 'daily-board',
        component: () => import('@/views/substitution/DailyBoard.vue'),
      },
      {
        path: 'substitution-log',
        name: 'substitution-log',
        component: () => import('@/views/substitution/SubstitutionLog.vue'),
      },
      {
        path: 'substitution-stats',
        name: 'substitution-stats',
        component: () => import('@/views/substitution/SubstitutionStats.vue'),
      },
      {
        path: 'scheduling/versions',
        name: 'versions',
        component: () => import('@/views/scheduling/Versions.vue'),
      },
      {
        path: 'scheduling/timetable-demo',
        name: 'timetable-demo',
        component: () => import('@/views/scheduling/TimetableGridDemo.vue'),
      },
      {
        path: 'settings/period-tables/:id',
        name: 'period-table-editor',
        component: () => import('@/views/settings/PeriodTableEditor.vue'),
      },
      {
        path: 'settings/system',
        name: 'system',
        component: () => import('@/views/settings/System.vue'),
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

const AUTH_PAGES = new Set(['login', 'change-password'])

// 全域守卫:管控登录、强制改密、首次登录引导至设置向导
// 纯教师账号可进入的页面(请假是教师自己要做的事)
const TEACHER_PAGES = new Set(['timetable-query', 'leaves', 'substitution-stats'])

router.beforeEach(async (to) => {
  // The prototype is a static, in-memory review surface and must remain runnable
  // when the backend is not present. All production routes keep the normal guard.
  if (to.meta.prototype) return true

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

  // 纯教师账号:只开放课表查询与请假登记(其余页面的后端 API 均需排课管理员以上权限)
  const canManage = auth.hasRole('admin') || auth.hasRole('scheduler') || auth.hasRole('director')
  if (!canManage && auth.hasRole('teacher') && !TEACHER_PAGES.has(to.name as string)) {
    return { name: 'timetable-query' }
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
