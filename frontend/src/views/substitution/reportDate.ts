const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

export function toLocalISODate(timestamp: number): string {
  const date = new Date(timestamp)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function formatDateWithWeekday(iso: string, weekday?: number): string {
  const resolvedWeekday = weekday ?? (() => {
    const [year, month, day] = iso.split('-').map(Number)
    return new Date(year, month - 1, day).getDay()
  })()
  const weekdayIndex = ((resolvedWeekday % WEEKDAYS.length) + WEEKDAYS.length) % WEEKDAYS.length
  return `${iso}（${WEEKDAYS[weekdayIndex]}）`
}
