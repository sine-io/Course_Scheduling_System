import type { APIResponse, Page } from '@playwright/test'
import { SEM_END, SEM_START } from './dates'

// 专用于 E2E 的排课管理员账号（由验收前置步骤通过 sudo docker exec 创建，不删除）。
export const E2E_USER = 'e2e_scheduler'
export const E2E_PASS = 'e2etest1234'

export const JUNIOR_HIGH_SLOTS = [
  [1, '早自习', '07:50', '08:20', 'morning'],
  [2, '第一节', '08:20', '09:05', 'regular'],
  [3, '第二节', '09:15', '10:00', 'regular'],
  [4, '第三节', '10:20', '11:05', 'regular'],
  [5, '第四节', '11:15', '12:00', 'regular'],
  [6, '午休', '12:00', '13:10', 'lunch'],
  [7, '第五节', '13:10', '13:55', 'regular'],
  [8, '第六节', '14:05', '14:50', 'regular'],
  [9, '第七节', '15:10', '15:55', 'regular'],
] as const

export const SENIOR_HIGH_SLOTS = [
  [1, '早自习', '07:40', '08:00', 'morning'],
  [2, '第一节', '08:00', '08:50', 'regular'],
  [3, '第二节', '09:00', '09:50', 'regular'],
  [4, '第三节', '10:00', '10:50', 'regular'],
  [5, '第四节', '11:00', '11:50', 'regular'],
  [6, '午休', '11:50', '13:10', 'lunch'],
  [7, '第五节', '13:10', '14:00', 'regular'],
  [8, '第六节', '14:10', '15:00', 'regular'],
  [9, '第七节', '15:10', '16:00', 'regular'],
  [10, '第八节', '16:10', '17:00', 'regular'],
] as const

export const TEST_SUBJECTS = [
  '语文',
  '数学',
  '英语',
  '道德与法治',
  '历史',
  '地理',
  '生物学',
  '体育与健康',
  '音乐',
  '美术',
  '信息科技',
  '劳动',
  '综合实践活动',
] as const

type TestSlot = readonly [number, string, string, string, string]

async function responseJson<T>(response: APIResponse): Promise<T> {
  if (!response.ok()) {
    throw new Error(`${response.url()}：${await response.text()}`)
  }
  return response.json() as Promise<T>
}

export function semesterLabel(year: number, term = 1): string {
  const label = term === 1 ? '第一学期' : '第二学期'
  return `${year}-${year + 1}学年${label}`
}

export async function createTestPeriodTable(
  page: Page,
  semesterId: number,
  name: string,
  slots: readonly TestSlot[] = JUNIOR_HIGH_SLOTS,
  isDefault = false,
): Promise<{ id: number }> {
  const table = await responseJson<{ id: number }>(await page.request.post(
    `/api/semesters/${semesterId}/period-tables`,
    { data: { name, is_default: isDefault } },
  ))
  const periods = Array.from({ length: 5 }, (_, index) => index + 1).flatMap((weekday) =>
    slots.map(([periodNo, periodName, start, end, type]) => ({
      weekday,
      period_no: periodNo,
      name: periodName,
      start_time: start,
      end_time: end,
      type,
    })),
  )
  await responseJson(await page.request.put(
    `/api/period-tables/${table.id}/periods`,
    { data: periods },
  ))
  return table
}

export async function createTestSemester(
  page: Page,
  academicYear: number,
  options: {
    term?: number
    ready?: boolean
    startDate?: string
    endDate?: string
    slots?: readonly TestSlot[]
    subjects?: readonly string[]
  } = {},
): Promise<{ id: number; academic_year: number; term: number }> {
  const term = options.term ?? 1
  const ready = options.ready ?? true
  const semester = await responseJson<{ id: number; academic_year: number; term: number }>(
    await page.request.post('/api/semesters', {
      data: {
        academic_year: academicYear,
        term,
        start_date: options.startDate ?? SEM_START,
        end_date: options.endDate ?? SEM_END,
      },
    }),
  )
  await createTestPeriodTable(
    page,
    semester.id,
    '初中测试作息时间表',
    options.slots ?? JUNIOR_HIGH_SLOTS,
    true,
  )
  for (const name of options.subjects ?? TEST_SUBJECTS) {
    await responseJson(await page.request.post(
      `/api/subjects?semester_id=${semester.id}`,
      { data: { name } },
    ))
  }
  if (ready) {
    await responseJson(await page.request.post(`/api/semesters/${semester.id}/readiness`))
  }
  return semester
}

export async function login(page: Page, user = E2E_USER, pass = E2E_PASS): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('请输入账号').fill(user)
  await page.getByPlaceholder('请输入密码').fill(pass)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'))
}

/** 删除指定学年学期(idempotent),避免测试数据残留或冲突。 */
export async function deleteSemesterByYearTerm(page: Page, year: number, term: number): Promise<void> {
  const resp = await page.request.get('/api/semesters')
  const list = (await resp.json()) as Array<{ id: number; academic_year: number; term: number }>
  for (const s of list) {
    if (s.academic_year === year && s.term === term) {
      await page.request.delete(`/api/semesters/${s.id}`)
    }
  }
}
