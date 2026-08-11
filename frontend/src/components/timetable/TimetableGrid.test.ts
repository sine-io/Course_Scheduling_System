import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TimetableGrid from './TimetableGrid.vue'
import type { GridEntry, PeriodCell } from './types'

// 3 天 × 3 节:第2节为午休(反灰),周三第3节为固定用途(反灰),其余一般课
const periods: PeriodCell[] = []
for (let w = 1; w <= 3; w++) {
  periods.push({ weekday: w, period_no: 1, name: '第一节', type: 'regular', start_time: '08:00:00', end_time: '08:40:00' })
  periods.push({ weekday: w, period_no: 2, name: '午休', type: 'lunch' })
  periods.push({ weekday: w, period_no: 3, name: w === 3 ? '周三不排' : '第三节', type: w === 3 ? 'reserved' : 'regular' })
}
const entries: GridEntry[] = [
  { id: 1, weekday: 1, period_no: 1, subject: '语文', teacher: '王师', locked: true },
  { id: 2, weekday: 2, period_no: 1, subject: '数学', teacher: '李师' },
]

const DT = { getData: () => '', setData: () => {}, effectAllowed: '' }

function cell(wrapper: ReturnType<typeof mount>, w: number, p: number) {
  return wrapper.find(`[data-weekday="${w}"][data-period="${p}"]`)
}

describe('TimetableGrid', () => {
  it('渲染星期表头、节次名称与反灰不排课时段', () => {
    const w = mount(TimetableGrid, { props: { periods, entries } })
    expect(w.text()).toContain('星期一')
    expect(w.text()).toContain('星期三')
    expect(w.text()).toContain('第一节')
    // 午休与周三不排为反灰
    expect(cell(w, 1, 2).classes()).toContain('is-blocked')
    expect(cell(w, 3, 3).classes()).toContain('is-blocked')
    expect(cell(w, 1, 2).text()).toContain('午休')
  })

  it('将高密度课表约束在带可访问名称的滚动工作面内', () => {
    const w = mount(TimetableGrid, { props: { periods, entries } })
    const scroll = w.get('[data-testid="timetable-scroll"]')
    const grid = w.get('[role="grid"]')

    expect(scroll.attributes('tabindex')).toBe('0')
    expect(scroll.attributes('aria-label')).toContain('横向滚动')
    expect(grid.attributes('aria-label')).toBe('课表')
    expect(grid.findAll('[role="row"]')).toHaveLength(4)
    expect(cell(w, 1, 1).attributes('role')).toBe('gridcell')
    expect(cell(w, 1, 1).attributes('aria-label')).toContain('星期一，第一节，语文')
    expect(cell(w, 1, 1).attributes('aria-label')).toContain('已锁定')
    expect(cell(w, 1, 2).attributes('aria-label')).toContain('星期一，午休，不可排课')
  })

  it('渲染单元格卡片;锁定卡显示锁图示且不可拖拽', () => {
    const w = mount(TimetableGrid, { props: { periods, entries } })
    const locked = cell(w, 1, 1)
    expect(locked.text()).toContain('语文')
    expect(locked.text()).toContain('王师')
    expect(locked.find('.tg-lock').exists()).toBe(true)
    expect(locked.find('.tg-card').attributes('draggable')).toBe('false')
    // 未锁定卡可拖拽
    expect(cell(w, 2, 1).find('.tg-card').attributes('draggable')).toBe('true')
  })

  it('点击卡片触发 select', async () => {
    const w = mount(TimetableGrid, { props: { periods, entries } })
    await cell(w, 2, 1).find('.tg-card').trigger('click')
    expect(w.emitted('select')?.[0]?.[0]).toMatchObject({ id: 2 })
  })

  it('拖拽未锁定卡片触发 dragstart', async () => {
    const w = mount(TimetableGrid, { props: { periods, entries } })
    await cell(w, 2, 1).find('.tg-card').trigger('dragstart', { dataTransfer: { ...DT } })
    expect(w.emitted('dragstart')?.[0]?.[0]).toMatchObject({ source: 'grid', entryId: 2 })
  })

  it('拖入空的一般课格触发 check,放下触发 drop(带目标与 dragging 内容)', async () => {
    const dragging = { source: 'tray' as const, assignmentId: 9 }
    const w = mount(TimetableGrid, { props: { periods, entries, dragging } })
    await cell(w, 1, 3).trigger('dragenter', { dataTransfer: { ...DT } })
    expect(w.emitted('check')?.[0]?.[0]).toMatchObject({ weekday: 1, period_no: 3 })
    await cell(w, 1, 3).trigger('drop', { dataTransfer: { ...DT } })
    expect(w.emitted('drop')?.[0]?.[0]).toMatchObject({
      weekday: 1, period_no: 3, data: { source: 'tray', assignmentId: 9 },
    })
  })

  it('反灰时段不接受放下(不触发 drop)', async () => {
    const w = mount(TimetableGrid, { props: { periods, entries, dragging: { source: 'tray', assignmentId: 9 } } })
    await cell(w, 1, 2).trigger('drop', { dataTransfer: { ...DT } }) // 午休
    expect(w.emitted('drop')).toBeUndefined()
  })

  it('feedback 冲突时套用红框样式并显示原因', () => {
    const w = mount(TimetableGrid, {
      props: { periods, entries, feedback: { weekday: 1, period_no: 3, ok: false, reason: '王师此时段已有课' } },
    })
    const c = cell(w, 1, 3)
    expect(c.classes()).toContain('is-conflict')
    expect(c.text()).toContain('王师此时段已有课')
  })

  it('所选未排课程可通过键盘可达按钮排入空的一般课格', async () => {
    const dragging = { source: 'tray' as const, assignmentId: 9 }
    const w = mount(TimetableGrid, {
      props: { periods, entries, dragging, placementLabel: '语文' },
    })
    const action = cell(w, 1, 3).get('button')

    expect(action.attributes('aria-label')).toBe('将语文排入星期一第三节')
    await action.trigger('click')
    expect(w.emitted('activate')?.[0]?.[0]).toMatchObject({
      weekday: 1, period_no: 3, data: dragging,
    })
    expect(cell(w, 1, 2).find('button').exists()).toBe(false)
  })

  it('已排课程提供键盘可达的移动和移除操作', async () => {
    const moving = { source: 'grid' as const, entryId: 2 }
    const w = mount(TimetableGrid, {
      props: { periods, entries, dragging: moving, placementLabel: '数学' },
    })
    const source = cell(w, 2, 1)

    await source.get('[aria-label="移动数学"]').trigger('click')
    expect(w.emitted('move')?.[0]?.[0]).toMatchObject({ id: 2 })

    await source.get('[aria-label="移除数学"]').trigger('click')
    expect(w.emitted('remove')?.[0]?.[0]).toMatchObject({ id: 2 })

    const target = cell(w, 1, 3).get('button')
    expect(target.attributes('aria-label')).toBe('将数学移到星期一第三节')
    await target.trigger('click')
    expect(w.emitted('activate')?.[0]?.[0]).toMatchObject({
      weekday: 1, period_no: 3, data: moving,
    })
  })

  it('readonly 模式下单元格不可放下', async () => {
    const w = mount(TimetableGrid, {
      props: {
        periods,
        entries,
        readonly: true,
        dragging: { source: 'tray', assignmentId: 9 },
        placementLabel: '语文',
      },
    })
    await cell(w, 1, 3).trigger('drop', { dataTransfer: { ...DT } })
    expect(w.emitted('drop')).toBeUndefined()
    expect(cell(w, 1, 3).find('button').exists()).toBe(false)
    expect(cell(w, 2, 1).attributes('aria-label')).toContain('只读')
    expect(cell(w, 2, 1).attributes('aria-label')).not.toContain('可编辑')
    expect(cell(w, 2, 1).find('[aria-label="移动数学"]').exists()).toBe(false)
    expect(cell(w, 2, 1).find('[aria-label="移除数学"]').exists()).toBe(false)
  })
})
