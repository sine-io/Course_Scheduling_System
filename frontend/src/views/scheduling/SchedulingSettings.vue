<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  FileCheck2,
  History,
  LockKeyhole,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Trash2,
} from '@lucide/vue'
import {
  NAlert,
  NButton,
  NDivider,
  NEmpty,
  NInput,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpin,
  NTag,
  useMessage,
} from 'naive-ui'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import {
  activateSchedulingRules,
  createSchedulingRule,
  deleteSchedulingRule,
  getRuleWorkspace,
  listRuleTemplates,
  updateSchedulingRule,
  validateSchedulingRules,
} from '@/api/schedulingRules'
import type {
  RulePriority,
  RuleStrength,
  RuleTarget,
  RuleTemplate,
  SchedulingRule,
  SchedulingRulePayload,
  SchedulingRuleWorkspace,
} from '@/api/schedulingRules'
import { listSemesters } from '@/api/semesters'
import type { SemesterListItem } from '@/api/semesters'
import { useAuthStore } from '@/stores/auth'
import { useSemesterContextStore } from '@/stores/semesterContext'
import './scheduling-workspace.css'

const message = useMessage()
const auth = useAuthStore()
const semesterContext = useSemesterContextStore()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const activating = ref(false)
const validating = ref(false)
const deleting = ref(false)
const loadError = ref<string | null>(null)
const semesters = ref<SemesterListItem[]>([])
const sid = ref<number | null>(null)
const templates = ref<RuleTemplate[]>([])
const workspace = ref<SchedulingRuleWorkspace | null>(null)
const selectedKey = ref<string | null>(null)
const editing = ref(false)
const validation = ref<Awaited<ReturnType<typeof validateSchedulingRules>> | null>(null)

interface RuleForm {
  name: string
  template: string
  entityType: string
  targetIds: number[]
  weekdays: number[]
  periodNos: number[]
  periodTableIds: number[]
  weekPattern: string
  operator: string
  strength: RuleStrength
  priority: RulePriority
  sourceText: string
  enabled: boolean
}

const form = reactive<RuleForm>({
  name: '',
  template: 'global_blackout',
  entityType: 'school',
  targetIds: [],
  weekdays: [1],
  periodNos: [],
  periodTableIds: [],
  weekPattern: '',
  operator: 'forbid',
  strength: 'hard',
  priority: 'high',
  sourceText: '',
  enabled: true,
})

const selectedTemplate = computed(() => templates.value.find((item) => item.key === form.template) ?? null)
const selectedRule = computed(() => workspace.value?.rules.find((item) => item.rule_key === selectedKey.value) ?? null)
const visibleRules = computed(() => workspace.value?.rules ?? [])
const canEdit = computed(() => (
  (auth.hasRole('admin') || auth.hasRole('director'))
  && (!semesterContext.authoritative || semesterContext.isCurrent(sid.value))
))
const semesterOptions = computed(() => semesters.value.map((item) => ({ label: item.label, value: item.id })))
const weekdayOptions = [
  { label: '周一', value: 1 }, { label: '周二', value: 2 }, { label: '周三', value: 3 },
  { label: '周四', value: 4 }, { label: '周五', value: 5 }, { label: '周六', value: 6 },
  { label: '周日', value: 7 },
]
const entityLabels: Record<string, string> = {
  school: '全校', teacher: '教师', teacher_group: '教师组', grade: '年级',
  class: '班级', subject: '科目', assignment: '教学任务',
}
const operatorLabels: Record<string, string> = {
  forbid: '禁止安排', unavailable: '不可用', avoid: '尽量避开', prefer: '优先安排', allow: '限于这些时段',
}
const strengthLabels: Record<RuleStrength, string> = {
  hard: '必须满足', soft: '尽量满足', informational: '仅作记录',
}
const priorityLabels: Record<RulePriority, string> = { high: '高', medium: '中', low: '低' }

const targetOptions = computed(() => {
  const options = workspace.value?.options
  if (!options) return []
  if (form.entityType === 'teacher' || form.entityType === 'teacher_group') return options.teachers.map((item) => ({ label: item.name, value: item.id }))
  if (form.entityType === 'grade') return options.grades.map((item) => ({ label: item.name, value: item.id }))
  if (form.entityType === 'class') return options.classes.map((item) => ({ label: `${item.grade}年级 ${item.name}`, value: item.id }))
  if (form.entityType === 'subject') return options.subjects.map((item) => ({ label: item.name, value: item.id }))
  if (form.entityType === 'assignment') return options.assignments.map((item) => ({ label: `${item.name} · ${item.periods_per_week}节/周`, value: item.id }))
  return []
})
const entityOptions = computed(() => (selectedTemplate.value?.target_types ?? []).map((value) => ({ label: entityLabels[value] ?? value, value })))
const operatorOptions = computed(() => (selectedTemplate.value?.operators ?? []).map((value) => ({ label: operatorLabels[value] ?? value, value })))
const availableStrengths = computed(() => (
  selectedTemplate.value?.operator_strengths[form.operator]
  ?? selectedTemplate.value?.strengths
  ?? []
))
const strengthOptions = computed(() => availableStrengths.value.map((value) => ({ label: strengthLabels[value], value })))
const periodOptions = computed(() => {
  const slots = workspace.value?.options.period_tables[0]?.slots ?? []
  const seen = new Map<number, string>()
  for (const slot of slots) if (!seen.has(slot.period_no)) seen.set(slot.period_no, slot.name)
  return [...seen.entries()].map(([value, name], index) => ({ label: `${name}（第${index + 1}节）`, value }))
})
const periodTableOptions = computed(() => workspace.value?.options.period_tables.map((item) => ({ label: item.name, value: item.id })) ?? [])
const impactText = computed(() => {
  if (!validation.value) return '保存后点击“校验草稿”，查看匹配教学任务和被排除的候选课位。'
  if (!validation.value.valid) return `有 ${validation.value.diagnostics.length} 项问题，规则草稿不能激活。`
  return `匹配 ${validation.value.matched_assignment_count} 项教学任务，影响 ${validation.value.excluded_candidate_count} 个候选课位。`
})

function resetForm(templateKey = templates.value[0]?.key ?? 'global_blackout'): void {
  const template = templates.value.find((item) => item.key === templateKey) ?? templates.value[0]
  const firstStrength = template?.strengths[0] ?? 'hard'
  Object.assign(form, {
    name: '', template: template?.key ?? templateKey, entityType: template?.target_types[0] ?? 'school',
    targetIds: [], weekdays: [1], periodNos: [], periodTableIds: [],
    weekPattern: '',
    operator: template?.operators[0] ?? 'forbid', strength: firstStrength,
    priority: firstStrength === 'hard' ? 'high' : 'medium', sourceText: '', enabled: true,
  })
  editing.value = false
  selectedKey.value = null
  validation.value = null
}

function editRule(rule: SchedulingRule): void {
  Object.assign(form, {
    name: rule.name, template: rule.template, entityType: rule.target.entity_type,
    targetIds: [...rule.target.ids], weekdays: [...rule.timing.weekdays],
    periodNos: [...rule.timing.period_nos], periodTableIds: [...rule.timing.period_table_ids],
    weekPattern: rule.timing.week_pattern ?? '',
    operator: rule.operator, strength: rule.strength, priority: rule.priority,
    sourceText: rule.source_text, enabled: rule.enabled,
  })
  editing.value = true
  selectedKey.value = rule.rule_key
  validation.value = null
}

function chooseTemplate(key: string): void {
  const template = templates.value.find((item) => item.key === key)
  if (!template) return
  form.template = key
  if (key !== 'periodic') form.weekPattern = ''
  if (!template.target_types.includes(form.entityType)) {
    form.entityType = template.target_types[0] ?? 'school'
    form.targetIds = []
  }
  if (!template.operators.includes(form.operator)) form.operator = template.operators[0] ?? 'forbid'
  const strengths = template.operator_strengths[form.operator] ?? template.strengths
  if (!strengths.includes(form.strength)) form.strength = strengths[0] ?? 'hard'
  validation.value = null
}

function payload(): SchedulingRulePayload {
  const target: RuleTarget = {
    entity_type: form.entityType,
    ids: form.entityType === 'school' ? [] : [...form.targetIds],
  }
  const timing: SchedulingRulePayload['timing'] = {
    weekdays: [...form.weekdays], period_nos: [...form.periodNos], period_table_ids: [...form.periodTableIds],
  }
  if (form.weekPattern.trim()) timing.week_pattern = form.weekPattern.trim()
  return {
    name: form.name.trim(), template: form.template, target,
    timing,
    operator: form.operator, strength: form.strength, priority: form.priority,
    source_text: form.sourceText.trim(), enabled: form.enabled,
  }
}

async function loadWorkspace(id: number): Promise<void> {
  workspace.value = await getRuleWorkspace(id)
  if (selectedKey.value) {
    const selected = workspace.value.rules.find((item) => item.rule_key === selectedKey.value)
    if (selected) editRule(selected)
    else resetForm()
  } else if (!workspace.value.rules.length) resetForm()
}

async function loadPage(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    await semesterContext.load()
    const [items, catalog] = await Promise.all([listSemesters(), listRuleTemplates()])
    semesters.value = items
    templates.value = catalog
    const rawSemester = Array.isArray(route.query.semester) ? route.query.semester[0] : route.query.semester
    const requestedSemesterId = Number(rawSemester)
    sid.value = items.find((item) => item.id === requestedSemesterId)?.id
      ?? items.find((item) => item.is_current)?.id
      ?? semesterContext.currentSemesterId ?? items[0]?.id ?? null
    if (sid.value) await loadWorkspace(sid.value)
  } catch (error) {
    loadError.value = apiErrorMessage(error, '暂时无法读取排课规则，请重试。')
  } finally {
    loading.value = false
  }
}

async function changeSemester(id: number): Promise<void> {
  sid.value = id
  selectedKey.value = null
  await loadWorkspace(id)
  await router.replace({ query: { ...route.query, semester: String(id) } })
}

function returnToFlow(): void {
  router.push({
    name: 'scheduling-flow',
    query: { step: 'start', ...(sid.value ? { semester: String(sid.value) } : {}) },
  })
}

async function saveRule(): Promise<void> {
  if (!canEdit.value || saving.value || sid.value === null) return
  if (!form.name.trim()) {
    message.warning('请填写规则名称')
    return
  }
  if (form.entityType !== 'school' && form.targetIds.length === 0) {
    message.warning('请选择规则对象')
    return
  }
  if (!form.weekdays.length || !form.periodNos.length) {
    message.warning('请选择至少一个星期和教学节次')
    return
  }
  saving.value = true
  try {
    const body = payload()
    const wasEditing = editing.value
    const saved = wasEditing && selectedKey.value
      ? await updateSchedulingRule(sid.value, selectedKey.value, body)
      : await createSchedulingRule(sid.value, body)
    selectedKey.value = saved.rule_key
    message.success(wasEditing ? '规则草稿已更新' : '规则草稿已添加')
    await loadWorkspace(sid.value)
    const current = workspace.value?.rules.find((item) => item.rule_key === saved.rule_key)
    if (current) editRule(current)
  } catch (error) {
    message.error(apiErrorMessage(error, '规则保存失败，请重试。'))
  } finally {
    saving.value = false
  }
}

async function removeRule(rule: SchedulingRule): Promise<void> {
  if (!canEdit.value || deleting.value || sid.value === null) return
  deleting.value = true
  try {
    await deleteSchedulingRule(sid.value, rule.rule_key)
    message.success('规则已从当前草稿移除，历史版本不受影响')
    resetForm()
    await loadWorkspace(sid.value)
  } catch (error) {
    message.error(apiErrorMessage(error, '规则移除失败，请重试。'))
  } finally {
    deleting.value = false
  }
}

async function validateDraft(): Promise<void> {
  if (sid.value === null || validating.value) return
  validating.value = true
  try {
    validation.value = await validateSchedulingRules(sid.value)
    if (validation.value.valid) message.success('规则草稿校验通过')
  } catch (error) {
    message.error(apiErrorMessage(error, '规则校验失败，请重试。'))
  } finally {
    validating.value = false
  }
}

async function activateDraft(): Promise<void> {
  if (!canEdit.value || activating.value || sid.value === null || !workspace.value?.draft_revision) return
  activating.value = true
  try {
    await activateSchedulingRules(
      sid.value,
      `方案 B 规则编辑器 v${workspace.value.draft_revision.revision_no}`,
    )
    message.success('规则版本已激活，后续新课表会固定使用该版本')
    validation.value = null
    await loadWorkspace(sid.value)
  } catch (error) {
    message.error(apiErrorMessage(error, '规则版本暂不能激活，请先处理校验问题。'))
  } finally {
    activating.value = false
  }
}

function ruleStatusType(rule: SchedulingRule): 'success' | 'warning' | 'error' | 'default' {
  if (rule.status === 'unsupported') return 'error'
  if (rule.status === 'disabled') return 'default'
  if (rule.status === 'draft') return 'warning'
  return 'success'
}

watch(() => form.entityType, (value) => {
  if (value === 'school') form.targetIds = []
})
watch(() => form.operator, () => {
  if (!availableStrengths.value.includes(form.strength)) {
    form.strength = availableStrengths.value[0] ?? 'hard'
  }
})
onMounted(loadPage)
</script>

<template>
  <div class="scheduling-page rule-editor-page" data-testid="scheduling-settings-page">
    <header class="scheduling-page-header rule-editor-header">
      <div>
        <p class="scheduling-eyebrow">排课配置</p>
        <h1>规则构建器</h1>
        <p>用模板维护可追溯的排课规则；规则发布后会固定到新建课表。</p>
      </div>
      <div class="rule-editor-header-actions">
        <NButton quaternary data-testid="rule-back-flow" @click="returnToFlow">
          <template #icon><ArrowLeft :size="16" aria-hidden="true" /></template>
          返回开始排课
        </NButton>
        <NSelect
          v-if="semesters.length"
          v-model:value="sid"
          :options="semesterOptions"
          :disabled="loading"
          data-testid="rule-semester-select"
          @update:value="changeSemester"
        />
        <ShieldCheck :size="24" aria-hidden="true" />
      </div>
    </header>

    <section v-if="loading" class="scheduling-state" data-testid="scheduling-settings-loading" role="status" aria-live="polite">
      <NSpin size="small" />
      <strong>正在读取规则工作区</strong>
      <span>模板、当前学期对象和版本信息加载完成后可继续编辑。</span>
    </section>
    <section v-else-if="loadError" class="scheduling-state scheduling-state-error" data-testid="scheduling-settings-error" role="alert">
      <AlertTriangle :size="22" aria-hidden="true" />
      <strong>{{ loadError }}</strong>
      <NButton type="primary" data-testid="scheduling-settings-retry" @click="loadPage">
        <template #icon><RefreshCw :size="15" aria-hidden="true" /></template>
        重新读取
      </NButton>
    </section>
    <section v-else-if="!sid || !workspace" class="scheduling-panel rule-editor-empty">
      <NEmpty description="尚未创建学期，规则编辑器暂不可用" />
    </section>

    <main v-else class="rule-editor-layout">
      <aside class="rule-editor-sidebar">
        <section class="scheduling-panel rule-editor-panel rule-catalog-panel">
          <div class="rule-panel-heading">
            <div><p class="scheduling-eyebrow">模板目录</p><h2>从规则类型开始</h2></div>
            <NButton quaternary circle :disabled="!canEdit" aria-label="新建规则" title="新建规则" data-testid="rule-new" @click="resetForm()">
              <template #icon><Plus :size="17" /></template>
            </NButton>
          </div>
          <div class="rule-template-list">
            <button
              v-for="template in templates"
              :key="template.key"
              class="rule-template-item"
              :class="{ 'is-selected': form.template === template.key, 'is-unsupported': !template.supported }"
              type="button"
              :disabled="!canEdit"
              @click="chooseTemplate(template.key)"
            >
              <span class="rule-template-icon" aria-hidden="true">
                <CheckCircle2 v-if="template.supported" :size="15" />
                <LockKeyhole v-else :size="15" />
              </span>
              <span><strong>{{ template.label }}</strong><small>{{ template.description }}</small></span>
              <NTag size="small" :type="template.supported ? 'success' : 'default'">{{ template.supported ? '可激活' : '待支持' }}</NTag>
            </button>
          </div>
        </section>

        <section class="scheduling-panel rule-editor-panel rule-list-panel">
          <div class="rule-panel-heading compact-heading">
            <div><p class="scheduling-eyebrow">当前草稿</p><h2>自定义规则</h2></div>
            <NTag size="small" :type="workspace.draft_revision ? 'warning' : 'default'">{{ workspace.draft_revision ? `v${workspace.draft_revision.revision_no}` : '无草稿' }}</NTag>
          </div>
          <NEmpty v-if="!visibleRules.length" description="还没有自定义规则" />
          <div v-else class="rule-list">
            <button
              v-for="rule in visibleRules"
              :key="rule.rule_key"
              type="button"
              class="rule-list-item"
              :class="{ 'is-selected': selectedKey === rule.rule_key }"
              @click="editRule(rule)"
            >
              <span class="rule-list-item-copy"><strong>{{ rule.name }}</strong><small>{{ rule.summary }}</small></span>
              <NTag size="small" :type="ruleStatusType(rule)">{{ rule.compiler_status }}</NTag>
            </button>
          </div>
        </section>
      </aside>

      <section class="scheduling-panel rule-editor-panel rule-builder-panel">
        <div class="rule-panel-heading">
          <div><p class="scheduling-eyebrow">结构化条件</p><h2>{{ editing ? '编辑规则草稿' : '新建规则' }}</h2></div>
          <NTag v-if="selectedTemplate" :type="selectedTemplate.supported ? 'success' : 'default'">{{ selectedTemplate.supported ? '模板已支持' : '仅记录，不可激活' }}</NTag>
        </div>
        <NAlert v-if="selectedTemplate && !selectedTemplate.supported" type="warning" :show-icon="true">{{ selectedTemplate.unavailable_reason }}</NAlert>
        <div class="scheduling-form rule-form">
          <div class="scheduling-field">
            <label for="rule-name">规则名称</label>
            <NInput id="rule-name" v-model:value="form.name" placeholder="例如：体育课从第三节开始" :disabled="!canEdit || saving" data-testid="rule-name" />
          </div>
          <div class="rule-form-grid">
            <div class="scheduling-field"><label>规则模板</label><NSelect :value="form.template" :options="templates.map((item) => ({ label: item.label, value: item.key }))" :disabled="!canEdit || saving" data-testid="rule-template" @update:value="chooseTemplate" /></div>
            <div class="scheduling-field"><label>规则对象</label><NSelect v-model:value="form.entityType" :options="entityOptions" :disabled="!canEdit || saving" data-testid="rule-entity" /></div>
          </div>
          <div v-if="form.entityType !== 'school'" class="scheduling-field"><label>选择对象</label><NSelect v-model:value="form.targetIds" multiple filterable :options="targetOptions" :disabled="!canEdit || saving" placeholder="选择一个或多个对象" data-testid="rule-targets" /></div>
          <div class="rule-form-grid">
            <div class="scheduling-field"><label>星期</label><NSelect v-model:value="form.weekdays" multiple :options="weekdayOptions" :disabled="!canEdit || saving" data-testid="rule-weekdays" /></div>
            <div class="scheduling-field"><label>教学节次</label><NSelect v-model:value="form.periodNos" multiple filterable :options="periodOptions" :disabled="!canEdit || saving" placeholder="选择规则涉及的课位" data-testid="rule-periods" /></div>
          </div>
          <div v-if="periodTableOptions.length" class="scheduling-field"><label>适用作息表（可选）</label><NSelect v-model:value="form.periodTableIds" multiple :options="periodTableOptions" :disabled="!canEdit || saving" placeholder="留空表示所有作息表" data-testid="rule-period-tables" /></div>
          <div v-if="form.template === 'periodic'" class="scheduling-field"><label for="rule-week-pattern">周次模式（保留原始记录）</label><NInput id="rule-week-pattern" v-model:value="form.weekPattern" :disabled="!canEdit || saving" placeholder="例如：odd、even 或单双周" data-testid="rule-week-pattern" /></div>
          <div class="rule-form-grid">
            <div class="scheduling-field"><label>规则动作</label><NSelect v-model:value="form.operator" :options="operatorOptions" :disabled="!canEdit || saving" data-testid="rule-operator" /></div>
            <div class="scheduling-field"><label>约束强度</label><NRadioGroup v-model:value="form.strength" :disabled="!canEdit || saving" data-testid="rule-strength"><NRadioButton v-for="item in strengthOptions" :key="item.value" :value="item.value" :label="item.label" /></NRadioGroup></div>
          </div>
          <div v-if="form.strength === 'soft'" class="scheduling-field"><label>优先级</label><NRadioGroup v-model:value="form.priority" :disabled="!canEdit || saving" data-testid="rule-priority"><NRadioButton v-for="(label, value) in priorityLabels" :key="value" :value="value" :label="label" /></NRadioGroup></div>
          <div class="scheduling-field"><label for="rule-source">规则原文或说明</label><NInput id="rule-source" v-model:value="form.sourceText" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="保留教务人员看到的原文，便于追溯和交接" :disabled="!canEdit || saving" data-testid="rule-source" /></div>
          <div class="rule-builder-actions">
            <NButton type="primary" :loading="saving" :disabled="!canEdit || saving" data-testid="rule-save" @click="saveRule"><template #icon><Save :size="15" /></template>{{ editing ? '保存修改' : '保存到草稿' }}</NButton>
            <NButton v-if="editing && selectedRule" secondary type="error" :loading="deleting" :disabled="!canEdit || deleting" data-testid="rule-delete" @click="removeRule(selectedRule)"><template #icon><Trash2 :size="15" /></template>从草稿移除</NButton>
            <NButton v-else quaternary :disabled="!canEdit" data-testid="rule-cancel" @click="resetForm()">清空</NButton>
          </div>
        </div>
      </section>

      <aside class="rule-editor-insights">
        <section class="scheduling-panel rule-editor-panel rule-impact-panel">
          <div class="rule-panel-heading compact-heading"><div><p class="scheduling-eyebrow">影响预览</p><h2>发布前检查</h2></div><FileCheck2 :size="19" class="scheduling-heading-icon" aria-hidden="true" /></div>
          <p class="rule-impact-summary">{{ impactText }}</p>
          <div v-if="validation?.diagnostics.length" class="rule-diagnostics" role="alert">
            <div v-for="item in validation.diagnostics" :key="`${item.rule_key}-${item.code}`" class="rule-diagnostic" :class="`is-${item.level}`"><AlertTriangle :size="14" aria-hidden="true" /><span>{{ item.message }}</span></div>
          </div>
          <NButton secondary block :loading="validating" :disabled="!sid || validating" data-testid="rule-validate" @click="validateDraft"><template #icon><FileCheck2 :size="15" /></template>校验当前草稿</NButton>
        </section>
        <section class="scheduling-panel rule-editor-panel rule-version-panel">
          <div class="rule-panel-heading compact-heading"><div><p class="scheduling-eyebrow">规则版本</p><h2>生效范围</h2></div><History :size="19" class="scheduling-heading-icon" aria-hidden="true" /></div>
          <div class="rule-version-row"><span>当前生效</span><strong>{{ workspace.active_revision ? `v${workspace.active_revision.revision_no}` : '尚未激活' }}</strong></div>
          <div class="rule-version-row"><span>编辑草稿</span><strong>{{ workspace.draft_revision ? `v${workspace.draft_revision.revision_no}` : '无' }}</strong></div>
          <NDivider />
          <p class="rule-version-note">激活会生成不可变版本；已经创建的课表继续使用它创建时固定的规则版本。</p>
          <NButton type="primary" block :loading="activating" :disabled="!canEdit || activating || !workspace.draft_revision" data-testid="rule-activate" @click="activateDraft"><template #icon><CheckCircle2 :size="15" /></template>激活规则版本</NButton>
        </section>
        <section class="scheduling-panel rule-editor-panel rule-builtin-panel">
          <div class="rule-panel-heading compact-heading"><div><p class="scheduling-eyebrow">系统内置</p><h2>始终生效</h2></div><LockKeyhole :size="19" class="scheduling-heading-icon" aria-hidden="true" /></div>
          <div class="rule-builtin-list"><div v-for="rule in workspace.builtin_rules" :key="rule.rule_key" class="rule-builtin-row"><span><strong>{{ rule.name }}</strong><small>{{ rule.summary }}</small></span><NTag size="small" :type="rule.strength === 'hard' ? 'error' : 'info'">{{ rule.strength === 'hard' ? '必须' : '尽量' }}</NTag></div></div>
          <div class="rule-support-note"><Clock3 :size="14" aria-hidden="true" /><span>规则来源和版本会随课表保留，单双周等未支持模板不会被当成已生效规则。</span></div>
        </section>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.rule-editor-page { max-width: 1480px; }
.rule-editor-header { align-items: flex-start; }
.rule-editor-header-actions { display: flex; align-items: center; gap: var(--app-space-3); color: var(--app-primary-strong); }
.rule-editor-header-actions .n-select { width: min(290px, 35vw); }
.rule-editor-layout { display: grid; min-width: 0; grid-template-columns: minmax(230px, 290px) minmax(360px, 1fr) minmax(260px, 320px); align-items: start; gap: var(--app-space-4); }
.rule-editor-sidebar, .rule-editor-insights { display: grid; min-width: 0; gap: var(--app-space-4); }
.rule-editor-panel { display: grid; min-width: 0; gap: var(--app-space-4); padding: var(--app-space-4); }
.rule-panel-heading { display: flex; min-width: 0; align-items: flex-start; justify-content: space-between; gap: var(--app-space-3); }
.rule-panel-heading h2 { margin: 3px 0 0; font-size: 17px; }
.rule-panel-heading.compact-heading h2 { font-size: 15px; }
.rule-template-list, .rule-list, .rule-builtin-list { display: grid; min-width: 0; gap: 6px; }
.rule-template-item, .rule-list-item { display: flex; width: 100%; min-width: 0; align-items: center; gap: 9px; padding: 9px; border: 1px solid transparent; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text); cursor: pointer; text-align: left; }
.rule-template-item:hover, .rule-list-item:hover, .rule-template-item.is-selected, .rule-list-item.is-selected { border-color: var(--app-primary-border); background: var(--app-primary-soft); }
.rule-template-item:disabled { cursor: default; opacity: .7; }
.rule-template-item > span:nth-child(2), .rule-list-item-copy, .rule-builtin-row > span { display: grid; min-width: 0; gap: 3px; }
.rule-template-item strong, .rule-list-item strong, .rule-builtin-row strong { font-size: 12px; }
.rule-template-item small, .rule-list-item small, .rule-builtin-row small { overflow-wrap: anywhere; color: var(--app-text-muted); font-size: 11px; line-height: 1.4; }
.rule-template-icon { display: grid; flex: 0 0 auto; width: 26px; height: 26px; place-items: center; border-radius: var(--app-radius-xs); background: var(--app-success-soft); color: var(--app-success-pressed); }
.rule-template-item.is-unsupported .rule-template-icon { background: var(--app-surface-muted); color: var(--app-text-muted); }
.rule-template-item .n-tag, .rule-list-item .n-tag, .rule-builtin-row .n-tag { flex: 0 0 auto; margin-left: auto; }
.rule-list-item { align-items: flex-start; }
.rule-builder-panel { min-height: 650px; }
.rule-form { gap: 16px; }
.rule-form-grid { display: grid; min-width: 0; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.rule-form-grid .n-radio-group { display: flex; max-width: 100%; overflow-x: auto; }
.rule-builder-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 9px; padding-top: 4px; }
.rule-impact-summary { margin: 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.55; }
.rule-diagnostics { display: grid; gap: 6px; }
.rule-diagnostic { display: flex; align-items: flex-start; gap: 7px; padding: 8px; border-radius: var(--app-radius-xs); font-size: 12px; line-height: 1.45; }
.rule-diagnostic.is-error { background: var(--app-danger-soft); color: var(--app-danger-pressed); }
.rule-diagnostic.is-warning { background: var(--app-warning-soft); color: var(--app-warning-pressed); }
.rule-version-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--app-text-muted); font-size: 12px; }
.rule-version-row strong { color: var(--app-text); font-size: 14px; }
.rule-version-note { margin: 0; color: var(--app-text-muted); font-size: 12px; line-height: 1.55; }
.rule-builtin-row { display: flex; align-items: flex-start; gap: 8px; padding: 8px 0; border-top: 1px solid var(--app-border); }
.rule-builtin-row:first-child { border-top: 0; }
.rule-support-note { display: flex; align-items: flex-start; gap: 7px; padding: 9px; border: 1px solid var(--app-border); border-radius: var(--app-radius-xs); color: var(--app-text-muted); font-size: 11px; line-height: 1.5; }
.rule-support-note svg { flex: 0 0 auto; margin-top: 2px; }
.rule-editor-empty { min-height: 280px; display: grid; place-items: center; }
@media (max-width: 1120px) {
  .rule-editor-layout { grid-template-columns: minmax(220px, 280px) minmax(0, 1fr); }
  .rule-editor-insights { grid-column: 1 / -1; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: start; }
}
@media (max-width: 760px) {
  .rule-editor-header, .rule-editor-header-actions { align-items: stretch; flex-direction: column; }
  .rule-editor-header-actions .n-select { width: 100%; }
  .rule-editor-layout, .rule-editor-insights { display: grid; grid-template-columns: minmax(0, 1fr); }
  .rule-editor-insights { grid-column: auto; }
  .rule-form-grid { grid-template-columns: minmax(0, 1fr); }
  .rule-builder-panel { min-height: 0; }
}
</style>
