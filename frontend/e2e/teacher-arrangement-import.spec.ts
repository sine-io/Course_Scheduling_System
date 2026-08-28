import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import ExcelJS from 'exceljs'
import type { CellValue, Worksheet } from 'exceljs'
import {
  createTestSemester,
  deleteSemesterByYearTerm,
  login,
} from './helpers'

const VIEWPORTS = [
  { width: 1280, height: 800, year: 2082 },
  { width: 375, height: 812, year: 2083 },
] as const

function worksheet(workbook: ExcelJS.Workbook, name: string): Worksheet {
  const sheet = workbook.getWorksheet(name)
  if (!sheet) throw new Error(`模板缺少工作表：${name}`)
  return sheet
}

function setRow(
  workbook: ExcelJS.Workbook,
  sheetName: string,
  values: Record<string, CellValue>,
  rowNumber = 4,
): void {
  const sheet = worksheet(workbook, sheetName)
  const columns = new Map<string, number>()
  sheet.getRow(1).eachCell((cell, column) => {
    columns.set(String(cell.value), column)
  })
  for (const [header, value] of Object.entries(values)) {
    const column = columns.get(header)
    if (!column) throw new Error(`${sheetName} 缺少列：${header}`)
    sheet.getCell(rowNumber, column).value = value
  }
}

async function prepareWorkbooks(templatePath: string, directory: string) {
  const workbook = new ExcelJS.Workbook()
  await workbook.xlsx.readFile(templatePath)
  setRow(workbook, '科目', {
    学校科目编码: 'SUB-MATH',
    科目名称: '数学',
    '领域/类别': '数学',
    '所需教室/场地类型': '专用教室',
  })
  setRow(workbook, '教师', {
    学校教师编码: 'T-001',
    教师姓名: '王老师',
    基础周课时: null,
    行政职务: '年级负责人',
    行政减课时: 0,
    教师状态: '在岗',
    外聘: '否',
  })
  setRow(workbook, '班级', {
    学校班级编码: 'C-701',
    班级名称: '七年级1班',
    年级: 7,
    学制: '初中',
    '专业/班级类别': '普通班',
    班主任: 'T-001',
    班级计划周课时: 5,
    作息表编码: 'PT-JUNIOR',
  })
  setRow(workbook, '教学任务', {
    任务编码: 'TASK-701-MATH',
    班级: 'C-701',
    科目: 'SUB-MATH',
    组成: '基础课',
    周课时: 5,
    主讲教师: null,
    协同教师: null,
  })
  setRow(workbook, '来源记录', {
    记录编码: 'SRC-001',
    记录类型: '备注',
    关联任务编码: 'TASK-701-MATH',
    原始内容: '人数与费用由年级另行维护',
    备注: '来自教师安排表备注栏',
  })
  setRow(workbook, '教室及户外场地', {
    '学校教室/场地编码': 'ROOM-MATH',
    '教室/场地名称': '数学专用教室',
    '教室/场地类型': '专用教室',
    容量: 48,
    适用科目: 'SUB-MATH',
  })
  for (const [index, weekday] of ['星期一', '星期二', '星期三', '星期四', '星期五'].entries()) {
    setRow(workbook, '作息时间表', {
      作息表编码: 'PT-JUNIOR',
      作息表名称: '初中部作息',
      星期: weekday,
      节次: 1,
      课时类型: '常规课时',
      开始时间: '08:00',
      结束时间: '08:45',
    }, 4 + index)
  }

  const blockedPath = join(directory, '教师安排-待修正.xlsx')
  await workbook.xlsx.writeFile(blockedPath)
  setRow(workbook, '教学任务', { 主讲教师: 'T-001' })
  const correctedPath = join(directory, '教师安排-已修正.xlsx')
  await workbook.xlsx.writeFile(correctedPath)
  return { blockedPath, correctedPath }
}

async function expectNoRootOverflow(page: import('@playwright/test').Page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
}

for (const viewport of VIEWPORTS) {
  test(`教师安排模板在 ${viewport.width}px 完成修正、导入与就绪确认`, async ({ page }, testInfo) => {
    test.setTimeout(120_000)
    const directory = await mkdtemp(join(tmpdir(), 'teacher-arrangement-e2e-'))
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await login(page)
    await deleteSemesterByYearTerm(page, viewport.year, 1)
    const semester = await createTestSemester(page, viewport.year, {
      ready: false,
      subjects: [],
    })

    try {
      await page.goto('/basedata')
      await expect(page.getByTestId('basedata-template-import')).toBeVisible()
      await expect(page.getByText('参考文件', { exact: true })).toHaveCount(0)
      await page.getByTestId('basedata-template-import').click()
      await expect(page).toHaveURL(/tab=template/)
      await expect(page.getByRole('heading', { name: '教师安排模板' })).toBeVisible()

      await page.getByTestId('template-mode-ready').click()
      const templateDownload = page.waitForEvent('download')
      await page.getByTestId('template-download').click()
      const downloadedTemplate = await templateDownload
      expect(downloadedTemplate.suggestedFilename()).toContain('自动排课准备模板')
      const templatePath = join(directory, '自动排课准备模板.xlsx')
      await downloadedTemplate.saveAs(templatePath)
      const { blockedPath, correctedPath } = await prepareWorkbooks(templatePath, directory)

      const fileInput = page.getByLabel('选择已填写的 XLSX 模板')
      await fileInput.focus()
      await expect(fileInput).toBeFocused()
      await fileInput.setInputFiles(blockedPath)
      await page.getByTestId('template-preview').click()
      await expect(page.getByTestId('review-filter-blocker')).toHaveAttribute('aria-pressed', 'true')
      await expect(page.getByTestId('review-detail')).toContainText('主讲教师')
      await expect(page.getByTestId('template-commit')).toBeDisabled()

      const issueDownload = page.waitForEvent('download')
      await page.getByTestId('export-issues').click()
      expect((await issueDownload).suggestedFilename()).toBe('教师安排模板问题.csv')
      await expectNoRootOverflow(page)
      await page.screenshot({ path: testInfo.outputPath('blocked-review.png'), fullPage: true })

      await page.getByTestId('template-file').setInputFiles(correctedPath)
      await expect(page.getByText('教师安排-已修正.xlsx')).toBeVisible()
      await expect(page.getByTestId('template-commit')).toHaveCount(0)
      await page.getByTestId('template-preview').click()
      await expect(page.getByTestId('review-filter-blocker')).toContainText('0')
      await expect(page.getByTestId('confirm-warnings')).toBeVisible()
      await page.getByTestId('confirm-warnings').check()
      await expect(page.getByTestId('template-commit')).toBeEnabled()
      await page.getByTestId('template-commit').click()

      await expect(page.getByTestId('template-import-success')).toContainText('排课就绪状态已回到待确认')
      await expect(page.getByTestId('template-readiness')).toContainText('数据完整性')
      await expect(page.getByTestId('template-readiness')).toContainText('求解预检')
      await expect(page.getByTestId('readiness-confirm')).toBeEnabled()
      await page.getByTestId('readiness-confirm').click()
      await expect(page.getByTestId('readiness-next')).toBeVisible()

      const timetables = await page.request.get(`/api/timetables?semester_id=${semester.id}`)
      expect(timetables.ok()).toBe(true)
      expect(await timetables.json()).toEqual([])
      await expectNoRootOverflow(page)
      await page.screenshot({ path: testInfo.outputPath('ready.png'), fullPage: true })

      await page.getByTestId('readiness-next').click()
      await expect(page).toHaveURL(/\/scheduling\/settings$/)
      await expect(page.getByRole('heading', { name: '规则构建器' })).toBeVisible()
    } finally {
      await deleteSemesterByYearTerm(page, viewport.year, 1)
      await rm(directory, { recursive: true, force: true })
    }
  })
}
