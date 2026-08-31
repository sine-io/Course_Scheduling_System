<script setup lang="ts">
import { computed } from 'vue'
import {
  Check,
  CheckCircle2,
  CircleAlert,
  Columns3,
  Download,
  FileSpreadsheet,
  Filter,
  PanelRight,
  RefreshCw,
  Search,
  ShieldCheck,
  Upload,
} from '@lucide/vue'
import type { ImportMode, PrototypeViewProps } from './types'

type CellValue = string | number
interface WorkbenchRow {
  row: number
  issueId?: string
  [key: string]: CellValue | undefined
}

const props = defineProps<PrototypeViewProps>()

const emit = defineEmits<{
  'set-mode': [mode: ImportMode]
  download: []
  upload: []
  fix: []
  commit: []
  confirm: []
  reset: []
  'select-sheet': [sheet: string]
  'select-issue': [id: string]
}>()

const columnsBySheet: Record<string, Array<{ key: string; label: string }>> = {
  学期: [
    { key: 'academicYear', label: '学年' },
    { key: 'term', label: '学期' },
    { key: 'templateVersion', label: '模板版本' },
  ],
  科目: [
    { key: 'code', label: '科目编码' },
    { key: 'name', label: '科目名称' },
    { key: 'roomType', label: '场地类型' },
  ],
  教师: [
    { key: 'code', label: '教师编码' },
    { key: 'name', label: '教师姓名' },
    { key: 'basePeriods', label: '基础课时' },
    { key: 'adminReduction', label: '行政减免' },
    { key: 'flags', label: '状态标记' },
  ],
  班级: [
    { key: 'code', label: '班级编码' },
    { key: 'name', label: '班级名称' },
    { key: 'plannedPeriods', label: '计划周课时' },
    { key: 'timetable', label: '作息时间表' },
  ],
  教学任务: [
    { key: 'code', label: '任务编码' },
    { key: 'className', label: '班级' },
    { key: 'subject', label: '科目' },
    { key: 'component', label: '组成' },
    { key: 'periods', label: '周课时' },
    { key: 'teacher', label: '主讲教师' },
    { key: 'coTeachers', label: '协同教师' },
  ],
  来源记录: [
    { key: 'sourceType', label: '记录类型' },
    { key: 'related', label: '关联对象' },
    { key: 'content', label: '来源原文摘要' },
  ],
  '教室/场地': [
    { key: 'code', label: '场地编码' },
    { key: 'name', label: '场地名称' },
    { key: 'type', label: '场地类型' },
    { key: 'capacity', label: '容量' },
  ],
  作息时间表: [
    { key: 'table', label: '时间表' },
    { key: 'weekday', label: '星期' },
    { key: 'period', label: '节次' },
    { key: 'type', label: '节次类型' },
    { key: 'start', label: '开始时间' },
    { key: 'end', label: '结束时间' },
  ],
}

const sampleRows: Record<string, WorkbenchRow[]> = {
  学期: [{ row: 4, academicYear: '2026—2027', term: '第一学期', templateVersion: '1.0' }],
  科目: [
    { row: 4, code: 'SUB-CHI', name: '语文', roomType: '普通教室' },
    { row: 5, code: 'SUB-PE', name: '体育与健康', roomType: '运动场地' },
    { row: 6, code: 'SUB-LAB', name: '物理实验', roomType: '物理实验室' },
    { row: 7, code: 'SUB-ART', name: '美术', roomType: '美术教室' },
  ],
  教师: [
    { row: 4, code: 'T-001', name: '王老师', basePeriods: 12, adminReduction: 0, flags: '无' },
    { row: 5, code: 'T-006', name: '刘老师', basePeriods: 14, adminReduction: 0, flags: '无' },
    { row: 11, code: 'T-018', name: '陈老师', basePeriods: 10, adminReduction: 2, flags: '年级组长' },
    { row: 19, code: 'T-018', name: '周老师', basePeriods: 12, adminReduction: 0, flags: '无', issueId: 'duplicate-teacher-code' },
    { row: 22, code: 'T-031', name: '许老师', basePeriods: '', adminReduction: 0, flags: '无', issueId: 'teacher-base-periods' },
  ],
  班级: [
    { row: 4, code: 'C-0701', name: '七年级1班', plannedPeriods: 31, timetable: '初中标准作息' },
    { row: 5, code: 'C-0702', name: '七年级2班', plannedPeriods: 31, timetable: '初中标准作息' },
    { row: 6, code: 'C-0705', name: '七年级5班', plannedPeriods: 31, timetable: '初中标准作息' },
    { row: 7, code: 'C-0802', name: '八年级2班', plannedPeriods: 30, timetable: '初中标准作息' },
  ],
  来源记录: [
    { row: 4, sourceType: '人员状态', related: '李老师', content: '本学期外出交流，不创建教学任务' },
    { row: 5, sourceType: '工作量备注', related: '综合实践组', content: '原表中的工作量说明，仅供追溯' },
    { row: 7, sourceType: '人数备注', related: '七年级', content: '年级人数统计不参与排课', issueId: 'source-note' },
  ],
  '教室/场地': [
    { row: 4, code: 'ROOM-GYM', name: '室内体育馆', type: '运动场地', capacity: 80 },
    { row: 5, code: 'ROOM-PHY-1', name: '物理实验室1', type: '物理实验室', capacity: 48 },
    { row: 6, code: 'ROOM-ART-1', name: '美术教室', type: '美术教室', capacity: 48 },
  ],
  作息时间表: [
    { row: 4, table: '初中标准作息', weekday: '星期一', period: 1, type: '常规课', start: '08:00', end: '08:45' },
    { row: 5, table: '初中标准作息', weekday: '星期一', period: 2, type: '常规课', start: '08:55', end: '09:40' },
    { row: 16, table: '初中标准作息', weekday: '星期三', period: 5, type: '常规课', start: '14:00', end: '', issueId: 'missing-end-time' },
    { row: 17, table: '初中标准作息', weekday: '星期三', period: 6, type: '常规课', start: '14:10', end: '14:55' },
  ],
}

const taskRows = computed<WorkbenchRow[]>(() => {
  if (props.state.fileState === 'issues') {
    return [
      { row: 4, code: 'TA-0701-CHI', className: '七年级1班', subject: '语文', component: '基础课', periods: 5, teacher: '王老师', coTeachers: '' },
      { row: 5, code: 'TA-0701-MATH', className: '七年级1班', subject: '数学', component: '基础课', periods: 5, teacher: '赵老师', coTeachers: '' },
      { row: 18, code: 'TA-0705-PE', className: '七年级5班', subject: '体育与健康', component: '合计', periods: '2+3', teacher: '刘老师 / 周老师', coTeachers: '', issueId: 'compound-periods' },
      { row: 27, code: 'TA-0802-PRA', className: '八年级2班', subject: '综合实践', component: '基础+劳动', periods: '4+1', teacher: '张老师', coTeachers: '', issueId: 'compound-periods' },
      { row: 42, code: 'TA-0903-PHY', className: '九年级3班', subject: '物理', component: '实验', periods: 2, teacher: '', coTeachers: '', issueId: 'missing-teacher' },
    ]
  }

  return props.changes.map((row, index) => ({
    row: index + 4,
    code: row.code,
    className: row.className,
    subject: row.subject,
    component: row.component,
    periods: row.periods,
    teacher: row.teacher,
    coTeachers: index === 4 ? '孙老师' : '',
  }))
})

const columns = computed(() => columnsBySheet[props.state.selectedSheet] || columnsBySheet.教学任务)
const rows = computed(() => props.state.selectedSheet === '教学任务' ? taskRows.value : (sampleRows[props.state.selectedSheet] || []))
const selectedIssue = computed(() => props.issues.find((issue) => issue.id === props.state.selectedIssueId) || props.issues[0] || null)

function selectRow(row: WorkbenchRow) {
  if (row.issueId) emit('select-issue', row.issueId)
}

function cellHasIssue(row: WorkbenchRow, key: string) {
  const issueFieldById: Record<string, string> = {
    'compound-periods': 'periods',
    'duplicate-teacher-code': 'code',
    'missing-teacher': 'teacher',
    'missing-end-time': 'end',
    'teacher-base-periods': 'basePeriods',
    'source-note': 'content',
  }
  return row.issueId ? issueFieldById[row.issueId] === key : false
}
</script>

<template>
  <div class="variant-c">
    <header class="workbench-toolbar">
      <div class="workbench-toolbar__brand">
        <Columns3 :size="19" aria-hidden="true" />
        <div><p class="proto-kicker">模板导入 / 数据工作台</p><h1>教师安排数据工作台</h1></div>
      </div>
      <div class="workbench-toolbar__middle">
        <label class="workbench-search"><Search :size="15" /><input value="七年级" aria-label="搜索数据"></label>
        <button type="button" title="筛选" aria-label="筛选"><Filter :size="16" /></button>
        <button type="button" title="重新校验" aria-label="重新校验" @click="emit('fix')"><RefreshCw :size="16" /></button>
      </div>
      <div class="workbench-toolbar__actions">
        <div class="compact-segmented" aria-label="导入模式">
          <button :class="{ active: state.mode === 'standard' }" type="button" @click="emit('set-mode', 'standard')">标准</button>
          <button :class="{ active: state.mode === 'ready' }" type="button" @click="emit('set-mode', 'ready')">排课准备</button>
        </div>
        <button class="btn btn--secondary" type="button" @click="emit('download')"><Download :size="16" />模板</button>
        <button class="btn btn--primary" type="button" @click="emit('upload')"><Upload :size="16" />上传</button>
      </div>
    </header>

    <div class="workbench-statusbar">
      <span><FileSpreadsheet :size="15" />{{ state.fileName }}</span>
      <span class="workbench-statusbar__divider" />
      <span>12 班级</span><span>43 教师</span><span>14 科目</span><span>124 任务</span>
      <span class="workbench-statusbar__spacer" />
      <strong :class="{ danger: counts.blockers > 0 }">{{ counts.blockers }} 阻断</strong>
      <strong class="warning">{{ counts.warnings }} 警告</strong>
    </div>

    <div class="workbench-layout">
      <aside class="sheet-sidebar">
        <div class="sheet-sidebar__heading"><span>工作表</span><small>{{ sheets.length }}</small></div>
        <button
          v-for="sheet in sheets"
          :key="sheet.name"
          :class="{ active: state.selectedSheet === sheet.name }"
          type="button"
          @click="emit('select-sheet', sheet.name)"
        >
          <FileSpreadsheet :size="16" />
          <span><strong>{{ sheet.name }}</strong><small>{{ sheet.rows }} 行 · {{ sheet.note }}</small></span>
          <i :class="['sheet-state', `sheet-state--${sheet.status}`]" />
        </button>
      </aside>

      <main class="data-grid-pane">
        <div class="data-grid-pane__heading">
          <div><h2>{{ state.selectedSheet }}</h2><span>第 4 行起为正式数据 · 示例行已跳过</span></div>
          <span class="table-validity"><Check v-if="!counts.blockers" :size="15" /><CircleAlert v-else :size="15" />{{ counts.blockers ? '需要修正' : '校验通过' }}</span>
        </div>
        <div class="data-grid-scroll">
          <table class="data-grid">
            <thead><tr><th class="row-number">#</th><th v-for="column in columns" :key="column.key">{{ column.label }}</th></tr></thead>
            <tbody>
              <tr v-for="row in rows" :key="row.row" :class="{ 'row-has-issue': row.issueId }" @click="selectRow(row)">
                <td class="row-number">{{ row.row }}</td>
                <td v-for="column in columns" :key="column.key" :class="{ 'cell-error': cellHasIssue(row, column.key) }">
                  <span>{{ row[column.key] === '' ? '（空）' : row[column.key] }}</span>
                  <CircleAlert v-if="cellHasIssue(row, column.key)" :size="14" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="data-grid-footer"><span>显示 {{ rows.length }} / {{ state.selectedSheet === '教学任务' ? 124 : rows.length }} 行</span><span>模板版本 1.0 · 类型检查已启用</span></footer>
      </main>

      <aside class="workbench-inspector">
        <div class="workbench-inspector__heading"><PanelRight :size="16" /><h2>校验与提交</h2></div>

        <div class="validation-meter">
          <div><span>阻断项</span><strong class="danger">{{ counts.blockers }}</strong></div>
          <div><span>警告项</span><strong class="warning">{{ counts.warnings }}</strong></div>
          <div><span>通过字段</span><strong>98.6%</strong></div>
        </div>

        <section v-if="selectedIssue" class="cell-inspector">
          <span :class="['severity-label', `severity-label--${selectedIssue.severity}`]">{{ selectedIssue.severity === 'blocker' ? '阻断' : '警告' }}</span>
          <h3>{{ selectedIssue.title }}</h3>
          <p>{{ selectedIssue.sheet }} · 第 {{ selectedIssue.row }} 行 · {{ selectedIssue.field }}</p>
          <code>{{ selectedIssue.value }}</code>
          <small>{{ selectedIssue.suggestion }}</small>
        </section>

        <div v-if="state.fileState === 'issues'" class="inspector-actions">
          <button class="btn btn--primary btn--full" type="button" @click="emit('fix')"><Upload :size="16" />载入已修正版本</button>
          <button class="btn btn--secondary btn--full" type="button" @click="emit('download')"><Download :size="16" />导出问题明细</button>
        </div>
        <div v-else-if="state.fileState === 'fixed'" class="inspector-actions">
          <div class="ready-to-submit"><CheckCircle2 :size="18" /><span><strong>校验通过</strong><small>{{ counts.newRecords }} 新增 · {{ counts.changedRecords }} 变更</small></span></div>
          <button class="btn btn--primary btn--full" type="button" @click="emit('commit')"><ShieldCheck :size="16" />原子提交本批次</button>
        </div>
        <div v-else class="inspector-actions">
          <div class="ready-to-submit"><CheckCircle2 :size="18" /><span><strong>导入完成</strong><small>TI-20260828-001</small></span></div>
          <button v-if="!state.readinessConfirmed" class="btn btn--primary btn--full" type="button" @click="emit('confirm')"><ShieldCheck :size="16" />{{ state.mode === 'ready' ? '确认排课就绪' : '进入排课准备检查' }}</button>
          <div v-else class="inspector-complete"><Check :size="17" />已确认，可编辑排课规则</div>
        </div>
      </aside>
    </div>
  </div>
</template>
