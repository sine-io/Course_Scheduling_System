import { expect, test } from '@playwright/test'
import {
  createTestSemester, deleteSemesterByYearTerm, login,
} from './helpers'
import { WED } from './dates'

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 375, height: 812 },
] as const

const SCHEDULER_ROUTES = [
  ['/', '仪表盘'],
  ['/workspace/home', '首页总览'],
  ['/settings/semesters', '学期与作息时间表'],
  ['/settings/calendar', '校历与排课准备'],
  ['/basedata', '基础数据'],
  ['/scheduling/assignments', '教学任务管理'],
  ['/timetable-query', '课表查询'],
  ['/notifications', '通知'],
  ['/scheduling/workbench', '排课工作台'],
  ['/scheduling/auto', '自动排课'],
  ['/leaves', '请假登记'],
  ['/substitutions', '调课与代课处理'],
  ['/notifications?view=board', '通知'],
  ['/daily-board', '今日调课与代课'],
  ['/substitution-log', '调课与代课记录'],
  ['/substitution-stats', '代课课时统计'],
  ['/scheduling/versions', '版本与发布'],
] as const

const TEACHER_ROUTES = [
  ['/', '仪表盘'],
  ['/timetable-query', '课表查询'],
  ['/leaves', '请假登记'],
  ['/notifications', '通知'],
  ['/substitution-stats', '我的代课课时'],
] as const

const RESTRICTED_TEACHER_ROUTES = [
  '/wizard',
  '/workspace/home',
  '/change-password',
  '/settings/semesters',
  '/settings/calendar',
  '/settings/period-tables/1',
  '/settings/system',
  '/basedata',
  '/scheduling/assignments',
  '/scheduling/workbench',
  '/scheduling/auto',
  '/scheduling/versions',
  '/substitutions',
  '/daily-board',
  '/daily-board/print',
  '/substitution-log',
  '/settings/backup',
  '/settings/accounts',
] as const

const ALLOWED_TEACHER_API_PATHS = new Set([
  '/api/app-config',
  '/api/auth/me',
  '/api/semester-context',
  '/api/published/semesters',
  '/api/published/timetable',
  '/api/published/my-teacher',
  '/api/notifications/mine',
  '/api/notifications/mine/unread-count',
])

test('生产发布不暴露原型路由、变体切换器或状态模拟器', async ({ page }) => {
  await login(page)

  await page.goto('/prototype/ui-style?variant=C')

  await expect(page).toHaveURL(/\/prototype\/ui-style\?variant=C$/)
  await expect(page.locator('#app')).toBeEmpty()
  await expect(page.getByText('视觉方向')).toHaveCount(0)
  await expect(page.getByText('状态模拟')).toHaveCount(0)
})

for (const [viewportIndex, viewport] of VIEWPORTS.entries()) {
  test(`排课管理员在 ${viewport.width}x${viewport.height} 可访问全部生产工作面且页面不溢出`, async ({ page }, testInfo) => {
    test.setTimeout(120_000)
    const year = 2071 + viewportIndex
    const pageErrors: string[] = []
    const remoteRequests: string[] = []
    page.on('pageerror', (error) => pageErrors.push(error.message))

    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await login(page)
    const applicationOrigin = new URL(page.url()).origin
    page.on('request', (request) => {
      const url = new URL(request.url())
      if (url.protocol.startsWith('http') && url.origin !== applicationOrigin) {
        remoteRequests.push(request.url())
      }
    })
    await deleteSemesterByYearTerm(page, year, 1)
    const semester = await createTestSemester(page, year)
    const detail = await page.request.get(`/api/semesters/${semester.id}`)
    expect(detail.ok()).toBe(true)
    const periodTableId = ((await detail.json()) as { period_tables: Array<{ id: number }> })
      .period_tables[0]?.id
    expect(periodTableId).toBeTruthy()

    const routes = [
      ...SCHEDULER_ROUTES,
      [`/settings/period-tables/${periodTableId}`, '作息时间表'] as const,
    ]

    try {
      for (const [routeIndex, [path, heading]] of routes.entries()) {
        const separator = path.includes('?') ? '&' : '?'
        await page.goto(`${path}${separator}semester_id=${semester.id}`)
        const title = page.getByRole('heading', { name: heading, level: 1, exact: true })
        await expect(title, `${path} 应渲染生产页面标题`).toBeVisible()
        await expect(page.getByTestId('app-shell'), `${path} 应使用生产应用壳层`).toBeVisible()

        const layout = await page.evaluate(() => {
          const title = document.querySelector('h1')?.getBoundingClientRect()
          const topbar = document.querySelector('.app-topbar')?.getBoundingClientRect()
          const content = document.querySelector<HTMLElement>('.app-content')
          return {
            rootScrollWidth: document.documentElement.scrollWidth,
            rootClientWidth: document.documentElement.clientWidth,
            contentScrollWidth: content?.scrollWidth ?? 0,
            contentClientWidth: content?.clientWidth ?? 0,
            titleTop: title?.top ?? -1,
            titleBottom: title?.bottom ?? -1,
            topbarBottom: topbar?.bottom ?? 0,
            viewportHeight: window.innerHeight,
          }
        })
        expect(layout.rootScrollWidth, `${path} 不应让页面横向滚动`)
          .toBeLessThanOrEqual(layout.rootClientWidth)
        expect(layout.contentScrollWidth, `${path} 的内容区不应横向溢出`)
          .toBeLessThanOrEqual(layout.contentClientWidth)
        expect(layout.titleTop, `${path} 的标题不应被顶栏遮挡`).toBeGreaterThanOrEqual(layout.topbarBottom)
        expect(layout.titleBottom, `${path} 的标题应位于可见视口内`).toBeLessThanOrEqual(layout.viewportHeight)
        await page.screenshot({
          path: testInfo.outputPath(`route-${String(routeIndex + 1).padStart(2, '0')}.png`),
        })
      }
    } finally {
      await deleteSemesterByYearTerm(page, year, 1)
    }

    expect(pageErrors).toEqual([])
    expect(remoteRequests).toEqual([])
  })
}

test('A4 通知单保留独立打印版式且打印时隐藏操作按钮', async ({ page }, testInfo) => {
  test.setTimeout(60_000)
  const year = 2075

  await login(page)
  await deleteSemesterByYearTerm(page, year, 1)
  const semester = await createTestSemester(page, year)

  try {
    await page.goto(`/daily-board/print?semester_id=${semester.id}&date=${WED}`)
    await expect(page.getByRole('heading', { name: '调课与代课通知单', level: 2 })).toBeVisible()
    await expect(page.getByTestId('print-empty')).toHaveText('本日无调课与代课安排。')
    await expect(page.getByTestId('app-shell')).toHaveCount(0)
    await expect(page.getByTestId('print-btn')).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('a4-screen.png') })

    await page.emulateMedia({ media: 'print' })
    await expect(page.getByTestId('print-btn')).toBeHidden()
    const printLayout = await page.locator('.sheet').evaluate((sheet) => {
      const style = getComputedStyle(sheet)
      return { maxWidth: style.maxWidth, padding: style.padding }
    })
    expect(printLayout).toEqual({ maxWidth: 'none', padding: '0px' })
    await page.screenshot({ path: testInfo.outputPath('a4-print.png') })
  } finally {
    await deleteSemesterByYearTerm(page, year, 1)
  }
})

test('教师导航只显示允许页面且受限直达 URL 在加载业务数据前被拒绝', async ({ page }) => {
  test.setTimeout(90_000)
  const unexpectedApiRequests: string[] = []
  await page.setViewportSize({ width: 375, height: 812 })
  await login(page, 'e2e_teacher', 'e2eteacher1234')

  for (const [path, heading] of TEACHER_ROUTES) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: heading, level: 1, exact: true })).toBeVisible()
  }

  await page.getByTestId('shell-menu').click()
  const navigation = page.getByTestId('shell-nav')
  await expect(navigation.getByRole('link', { name: '课表查询' })).toBeVisible()
  await expect(navigation.getByRole('link', { name: '请假登记' })).toBeVisible()
  await expect(navigation.getByRole('link', { name: '通知' })).toBeVisible()
  await expect(navigation.getByRole('link', { name: '我的代课课时' })).toBeVisible()
  await expect(navigation.getByRole('link', { name: '排课工作台' })).toHaveCount(0)
  await expect(navigation.getByRole('link', { name: '系统管理' })).toHaveCount(0)
  await page.keyboard.press('Escape')

  page.on('request', (request) => {
    const url = new URL(request.url())
    const path = url.pathname
    const allowed = ALLOWED_TEACHER_API_PATHS.has(path)
      || /^\/api\/semesters\/\d+\/summary$/.test(path)
    if (path.startsWith('/api/') && !allowed) {
      unexpectedApiRequests.push(`${request.method()} ${path}`)
    }
  })

  for (const path of RESTRICTED_TEACHER_ROUTES) {
    await page.goto(path)
    const fallback = path === '/change-password' ? /\/$/ : /\/timetable-query$/
    const heading = path === '/change-password' ? '仪表盘' : '课表查询'
    await expect(page).toHaveURL(fallback)
    await expect(page.getByRole('heading', { name: heading, level: 1, exact: true })).toBeVisible()
  }

  expect(unexpectedApiRequests).toEqual([])
})

test('教师访问旧通知看板链接时只进入个人通知视图', async ({ page }) => {
  await login(page, 'e2e_teacher', 'e2eteacher1234')
  await page.goto('/notification-board')
  await expect(page).toHaveURL(/\/notifications\?view=board$/)
  await expect(page.getByRole('heading', { name: '通知', level: 1 })).toBeVisible()
  await expect(page.getByTestId('notifications-tab-board')).toHaveCount(0)
})
