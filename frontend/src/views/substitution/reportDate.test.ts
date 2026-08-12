import { describe, expect, it } from 'vitest'

import { formatDateWithWeekday, toLocalISODate } from './reportDate'

describe('报表日期格式', () => {
  it('按本地时区生成 ISO 日期，避免 UTC 换日', () => {
    const localTime = new Date(2026, 7, 12, 23, 59).getTime()

    expect(toLocalISODate(localTime)).toBe('2026-08-12')
  })

  it('从 ISO 日期计算星期标签', () => {
    expect(formatDateWithWeekday('2026-08-12')).toBe('2026-08-12（星期三）')
  })

  it('可使用接口返回的星期序号', () => {
    expect(formatDateWithWeekday('2026-08-12', 0)).toBe('2026-08-12（星期日）')
  })
})
