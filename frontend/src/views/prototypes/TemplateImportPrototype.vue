<!-- PROTOTYPE ONLY: compares three interaction models for normalized teacher-assignment imports. -->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  BookOpenCheck,
  CalendarClock,
  ChevronDown,
  ClipboardCheck,
  Database,
  FileInput,
  LayoutDashboard,
  ListChecks,
  School,
  Settings2,
  SlidersHorizontal,
  UserRound,
} from '@lucide/vue'
import PrototypeSwitcher from './template-import/PrototypeSwitcher.vue'
import TemplateImportVariantA from './template-import/TemplateImportVariantA.vue'
import TemplateImportVariantB from './template-import/TemplateImportVariantB.vue'
import TemplateImportVariantC from './template-import/TemplateImportVariantC.vue'
import type {
  ChangeRow,
  ImportMode,
  IssueRow,
  PrototypeState,
  SheetSummary,
} from './template-import/types'
import './template-import/template-import-prototype.css'

const route = useRoute()
const router = useRouter()
const showPrototypeTools = import.meta.env.DEV
const uploadInput = ref<HTMLInputElement | null>(null)
const toastMessage = ref('')
let toastTimer: number | undefined

const normalizeMode = (value: unknown): ImportMode => value === 'ready' ? 'ready' : 'standard'

const state = ref<PrototypeState>({
  mode: normalizeMode(route.query.mode),
  fileName: '教师安排标准模板_待修正.xlsx',
  fileState: 'issues',
  selectedSheet: '教学任务',
  selectedIssueId: 'compound-periods',
  issueFilter: 'all',
  readinessConfirmed: false,
  lastAction: '已载入含 4 个典型问题的脱敏样例',
})

const baseIssues: IssueRow[] = [
  {
    id: 'compound-periods',
    severity: 'blocker',
    sheet: '教学任务',
    row: 27,
    field: '周课时',
    value: '4+1',
    title: '复合课时尚未拆分',
    detail: '周课时只接受正整数。不同排课含义必须拆成可独立排课的任务组成。',
    suggestion: '拆成“基础课 4 节”和“劳动 1 节”两条任务，并分别填写唯一任务编码。',
  },
  {
    id: 'duplicate-teacher-code',
    severity: 'blocker',
    sheet: '教师',
    row: 19,
    field: '教师编码',
    value: 'T-018',
    title: '教师编码与第 11 行重复',
    detail: '编码一旦填写即作为稳定身份，不能再回退到姓名匹配。',
    suggestion: '为周老师填写未使用的教师编码，或清空编码后按唯一姓名匹配现有教师。',
  },
  {
    id: 'missing-teacher',
    severity: 'blocker',
    standardSeverity: 'warning',
    sheet: '教学任务',
    row: 42,
    field: '主讲教师',
    value: '（空）',
    title: '教学任务缺少主讲教师',
    detail: '标准导入允许暂缺教师并给出警告；排课准备模式要求每条任务都能占用明确的教师资源。',
    suggestion: '填写主讲教师；如多人同时上课，将其他教师写入协同教师列。',
  },
  {
    id: 'missing-end-time',
    severity: 'blocker',
    readyOnly: true,
    sheet: '作息时间表',
    row: 16,
    field: '结束时间',
    value: '（空）',
    title: '常规节次缺少结束时间',
    detail: '自动排课准备模板要求常规课节次同时填写开始与结束时间。',
    suggestion: '补齐星期三第 5 节的结束时间，并确认没有与第 6 节重叠。',
  },
  {
    id: 'source-note',
    severity: 'warning',
    sheet: '来源记录',
    row: 7,
    field: '来源原文摘要',
    value: '七年级人数统计……',
    title: '此记录仅用于追溯',
    detail: '人数、费用、缺员和自由文本不会创建虚假的教学任务。',
    suggestion: '保留在来源记录中即可，导入后不会参与自动排课。',
  },
  {
    id: 'teacher-base-periods',
    severity: 'warning',
    sheet: '教师',
    row: 22,
    field: '基础课时',
    value: '（空）',
    title: '教师基础课时将按 0 处理',
    detail: '系统不会从来源备注推断基础课时或行政减免。',
    suggestion: '若学校需要做工作量校验，请填写明确数值；否则可保留为空并继续导入。',
  },
]

const changes: ChangeRow[] = [
  { code: 'TA-0705-PE-A', entity: '教学任务', className: '七年级5班', subject: '体育与健康', component: '基础体育', periods: 2, teacher: '刘老师', status: 'changed' },
  { code: 'TA-0705-PE-B', entity: '教学任务', className: '七年级5班', subject: '体育与健康', component: '专项体育', periods: 3, teacher: '周老师', status: 'new' },
  { code: 'TA-0802-PRA-A', entity: '教学任务', className: '八年级2班', subject: '综合实践', component: '基础课', periods: 4, teacher: '张老师', status: 'changed' },
  { code: 'TA-0802-PRA-B', entity: '教学任务', className: '八年级2班', subject: '劳动', component: '劳动实践', periods: 1, teacher: '张老师', status: 'new' },
  { code: 'TA-0903-PHY-LAB', entity: '教学任务', className: '九年级3班', subject: '物理', component: '实验', periods: 2, teacher: '孙老师', status: 'changed' },
  { code: 'TA-0701-CHI', entity: '教学任务', className: '七年级1班', subject: '语文', component: '基础课', periods: 5, teacher: '王老师', status: 'unchanged' },
  { code: 'TA-OLD-0802-ART', entity: '教学任务', className: '八年级2班', subject: '美术', component: '基础课', periods: 1, teacher: '钱老师', status: 'disappeared' },
]

const activeVariant = computed<'A' | 'B' | 'C'>(() => {
  const value = String(route.query.variant || 'A').toUpperCase()
  return value === 'B' || value === 'C' ? value : 'A'
})

const issues = computed<IssueRow[]>(() => {
  const normalized = baseIssues
    .filter((issue) => !issue.readyOnly || state.value.mode === 'ready')
    .map((issue) => ({
      ...issue,
      severity: state.value.mode === 'standard' && issue.standardSeverity
        ? issue.standardSeverity
        : issue.severity,
    }))

  if (state.value.fileState === 'issues') return normalized
  return normalized.filter((issue) => issue.id === 'source-note' || issue.id === 'teacher-base-periods')
})

const counts = computed(() => ({
  blockers: issues.value.filter((issue) => issue.severity === 'blocker').length,
  warnings: issues.value.filter((issue) => issue.severity === 'warning').length,
  newRecords: state.value.mode === 'ready' ? 174 : 162,
  changedRecords: 11,
  unchangedRecords: state.value.mode === 'ready' ? 28 : 18,
  disappearedRecords: 2,
}))

const sheets = computed<SheetSummary[]>(() => {
  const baseSheets: SheetSummary[] = [
    { name: '学期', rows: 1, status: 'ok', note: '身份校验' },
    { name: '科目', rows: 14, status: 'ok', note: '14 科目' },
    { name: '教师', rows: 43, status: 'ok', note: '43 教师' },
    { name: '班级', rows: 12, status: 'ok', note: '12 班级' },
    { name: '教学任务', rows: 124, status: 'ok', note: '124 任务' },
    { name: '来源记录', rows: 6, status: 'optional', note: '仅追溯' },
  ]
  if (state.value.mode === 'ready') {
    baseSheets.push(
      { name: '教室/场地', rows: 5, status: 'ok', note: '5 个专用场地' },
      { name: '作息时间表', rows: 40, status: 'ok', note: '1 套作息' },
    )
  }

  const issueSheets = new Set(issues.value.map((issue) => issue.sheet))
  return baseSheets.map((sheet) => ({
    ...sheet,
    status: issueSheets.has(sheet.name) ? 'attention' : sheet.status,
  }))
})

const stateSnapshot = computed(() => [
  ['variant', activeVariant.value],
  ['mode', state.value.mode],
  ['fileState', state.value.fileState],
  ['fileName', state.value.fileName],
  ['selectedSheet', state.value.selectedSheet],
  ['selectedIssueId', state.value.selectedIssueId || 'none'],
  ['issueFilter', state.value.issueFilter],
  ['blockers', counts.value.blockers],
  ['warnings', counts.value.warnings],
  ['readinessConfirmed', String(state.value.readinessConfirmed)],
  ['lastAction', state.value.lastAction],
])

function showToast(message: string) {
  toastMessage.value = message
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toastMessage.value = ''
  }, 2800)
}

function updateQuery(values: Record<string, string>) {
  void router.replace({ query: { ...route.query, ...values } })
}

function setMode(mode: ImportMode) {
  state.value.mode = mode
  if (mode === 'standard' && (state.value.selectedSheet === '教室/场地' || state.value.selectedSheet === '作息时间表')) {
    state.value.selectedSheet = '教学任务'
  }
  state.value.readinessConfirmed = false
  state.value.lastAction = mode === 'ready' ? '已切换到自动排课准备校验' : '已切换到教师安排标准校验'
  updateQuery({ mode })
}

function downloadTemplate() {
  const ready = state.value.mode === 'ready'
  const header = '任务编码,班级,科目,组成,周课时,主讲教师,协同教师\n'
  const example = 'TA-0701-CHI,七年级1班,语文,基础课,5,王老师,\n'
  const note = ready ? '# 原型示例：正式模板还将包含教室场地与作息时间表工作表\n' : '# 原型示例：正式文件为多工作表 XLSX\n'
  const blob = new Blob([`\ufeff${note}${header}${example}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${ready ? '自动排课准备' : '教师安排标准'}模板_原型.csv`
  anchor.click()
  URL.revokeObjectURL(url)
  state.value.lastAction = '已下载原型示例模板'
  showToast('已下载原型示例 CSV；正式实现将生成多工作表 XLSX')
}

function openUpload() {
  uploadInput.value?.click()
}

function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  state.value.fileName = file.name
  state.value.fileState = 'issues'
  state.value.readinessConfirmed = false
  state.value.selectedIssueId = 'compound-periods'
  state.value.lastAction = `已上传 ${file.name} 并完成首轮校验`
  showToast('文件已读取：发现典型问题，请按定位修正')
  input.value = ''
}

function fixAndRecheck() {
  state.value.fileName = state.value.mode === 'ready' ? '自动排课准备模板_已修正.xlsx' : '教师安排标准模板_已修正.xlsx'
  state.value.fileState = 'fixed'
  state.value.selectedIssueId = 'source-note'
  state.value.issueFilter = 'all'
  state.value.lastAction = '已载入修正版本；阻断项全部清零'
  showToast('重新校验通过：0 个阻断项，保留 2 个提示性警告')
}

function commitBatch() {
  if (counts.value.blockers > 0) {
    showToast('仍有阻断项，当前批次不能提交')
    return
  }
  state.value.fileState = 'committed'
  state.value.lastAction = '批次 TI-20260828-001 已原子提交'
  showToast('导入成功：已保留系统中的手工修改')
}

function confirmReadiness() {
  if (state.value.mode !== 'ready') {
    setMode('ready')
    state.value.lastAction = '已进入自动排课准备检查，尚未确认就绪'
    showToast('已切换到排课准备检查；确认后才能进入规则配置')
    return
  }
  state.value.readinessConfirmed = true
  state.value.lastAction = '教务主任已确认排课就绪'
  showToast('已确认就绪：下一步编辑并启用排课规则')
}

function resetPrototype() {
  state.value.fileName = state.value.mode === 'ready' ? '自动排课准备模板_待修正.xlsx' : '教师安排标准模板_待修正.xlsx'
  state.value.fileState = 'issues'
  state.value.selectedSheet = '教学任务'
  state.value.selectedIssueId = 'compound-periods'
  state.value.issueFilter = 'all'
  state.value.readinessConfirmed = false
  state.value.lastAction = '原型状态已重置'
  showToast('已恢复待修正样例')
}

function selectIssue(id: string) {
  state.value.selectedIssueId = id
  const issue = issues.value.find((item) => item.id === id)
  if (issue) state.value.selectedSheet = issue.sheet
  state.value.lastAction = `已定位问题 ${id}`
}

function selectSheet(sheet: string) {
  state.value.selectedSheet = sheet
  const issue = issues.value.find((item) => item.sheet === sheet)
  if (issue) state.value.selectedIssueId = issue.id
  state.value.lastAction = `已打开工作表 ${sheet}`
}

function setFilter(filter: 'all' | 'blocker' | 'warning') {
  state.value.issueFilter = filter
  const first = issues.value.find((issue) => filter === 'all' || issue.severity === filter)
  if (first) state.value.selectedIssueId = first.id
  state.value.lastAction = `问题筛选已切换为 ${filter}`
}

watch(
  () => route.query.mode,
  (mode) => {
    const normalized = normalizeMode(mode)
    if (normalized !== state.value.mode) state.value.mode = normalized
  },
)

watch(issues, (currentIssues) => {
  if (!currentIssues.some((issue) => issue.id === state.value.selectedIssueId)) {
    state.value.selectedIssueId = currentIssues[0]?.id || ''
  }
})

onBeforeUnmount(() => {
  if (toastTimer) window.clearTimeout(toastTimer)
})
</script>

<template>
  <div class="template-import-prototype">
    <input ref="uploadInput" class="visually-hidden" type="file" accept=".xlsx,.xls" @change="handleUpload">

    <header class="prototype-appbar">
      <div class="prototype-brand">
        <span class="prototype-brand__mark"><BookOpenCheck :size="21" aria-hidden="true" /></span>
        <span><strong>课表编排中心</strong><small>COURSE SCHEDULING</small></span>
      </div>
      <nav class="prototype-appbar__nav" aria-label="全局导航">
        <a href="#"><LayoutDashboard :size="16" />工作台</a>
        <a class="active" href="#"><Database :size="16" />基础数据</a>
        <a href="#"><CalendarClock :size="16" />排课管理</a>
      </nav>
      <div class="prototype-appbar__account">
        <span class="prototype-badge">PROTOTYPE ONLY</span>
        <span class="prototype-avatar"><UserRound :size="16" /></span>
        <span class="prototype-account-name">教务主任</span>
        <ChevronDown :size="15" aria-hidden="true" />
      </div>
    </header>

    <div class="prototype-shell">
      <aside class="prototype-sidebar">
        <p>基础数据</p>
        <a href="#"><School :size="17" /><span>学校与学期</span></a>
        <a href="#"><Database :size="17" /><span>教师、班级、科目</span></a>
        <a href="#"><ListChecks :size="17" /><span>教学任务</span></a>
        <a class="active" href="#"><FileInput :size="17" /><span>模板导入</span></a>
        <p>排课准备</p>
        <a href="#"><ClipboardCheck :size="17" /><span>就绪检查</span></a>
        <a href="#"><SlidersHorizontal :size="17" /><span>排课规则</span></a>
        <a href="#"><Settings2 :size="17" /><span>系统设置</span></a>
        <div class="prototype-sidebar__term">
          <small>当前学期</small>
          <strong>2026—2027 第一学期</strong>
          <span>准备中</span>
        </div>
      </aside>

      <div class="prototype-workspace">
        <TemplateImportVariantA
          v-if="activeVariant === 'A'"
          :state="state"
          :issues="issues"
          :changes="changes"
          :sheets="sheets"
          :counts="counts"
          @set-mode="setMode"
          @download="downloadTemplate"
          @upload="openUpload"
          @fix="fixAndRecheck"
          @commit="commitBatch"
          @confirm="confirmReadiness"
          @reset="resetPrototype"
          @select-issue="selectIssue"
        />
        <TemplateImportVariantB
          v-else-if="activeVariant === 'B'"
          :state="state"
          :issues="issues"
          :changes="changes"
          :sheets="sheets"
          :counts="counts"
          @set-mode="setMode"
          @set-filter="setFilter"
          @download="downloadTemplate"
          @upload="openUpload"
          @fix="fixAndRecheck"
          @commit="commitBatch"
          @confirm="confirmReadiness"
          @reset="resetPrototype"
          @select-issue="selectIssue"
        />
        <TemplateImportVariantC
          v-else
          :state="state"
          :issues="issues"
          :changes="changes"
          :sheets="sheets"
          :counts="counts"
          @set-mode="setMode"
          @download="downloadTemplate"
          @upload="openUpload"
          @fix="fixAndRecheck"
          @commit="commitBatch"
          @confirm="confirmReadiness"
          @reset="resetPrototype"
          @select-sheet="selectSheet"
          @select-issue="selectIssue"
        />

        <section v-if="showPrototypeTools" class="prototype-state-readout" aria-label="原型状态">
          <strong>STATE</strong>
          <span v-for="entry in stateSnapshot" :key="entry[0]"><b>{{ entry[0] }}</b> {{ entry[1] }}</span>
        </section>
      </div>
    </div>

    <Transition name="toast">
      <div v-if="toastMessage" class="prototype-toast" role="status">{{ toastMessage }}</div>
    </Transition>
    <PrototypeSwitcher v-if="showPrototypeTools" />
  </div>
</template>
