<script setup lang="ts">
import { computed } from 'vue'
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Download,
  FileCheck2,
  FileSpreadsheet,
  Filter,
  Inbox,
  RefreshCw,
  ShieldCheck,
  Upload,
} from '@lucide/vue'
import type { ImportMode, PrototypeViewProps } from './types'

const props = defineProps<PrototypeViewProps>()

const emit = defineEmits<{
  'set-mode': [mode: ImportMode]
  'set-filter': [filter: 'all' | 'blocker' | 'warning']
  download: []
  upload: []
  fix: []
  commit: []
  confirm: []
  reset: []
  'select-issue': [id: string]
}>()

const filteredIssues = computed(() => {
  if (props.state.issueFilter === 'all') return props.issues
  return props.issues.filter((issue) => issue.severity === props.state.issueFilter)
})

const selectedIssue = computed(() => {
  return props.issues.find((issue) => issue.id === props.state.selectedIssueId) || filteredIssues.value[0] || null
})

const blockerCount = computed(() => props.issues.filter((issue) => issue.severity === 'blocker').length)
const warningCount = computed(() => props.issues.filter((issue) => issue.severity === 'warning').length)
</script>

<template>
  <div class="variant-b">
    <header class="variant-b__header">
      <div class="variant-b__title">
        <span class="variant-b__icon"><Inbox :size="20" aria-hidden="true" /></span>
        <div>
          <p class="proto-kicker">模板导入 / 问题收件箱</p>
          <h1>导入审查台</h1>
        </div>
      </div>
      <div class="variant-b__commands">
        <label class="mode-select">
          <span>校验模式</span>
          <select :value="state.mode" @change="emit('set-mode', ($event.target as HTMLSelectElement).value as ImportMode)">
            <option value="standard">教师安排标准导入</option>
            <option value="ready">自动排课准备导入</option>
          </select>
        </label>
        <button class="btn btn--secondary" type="button" @click="emit('download')">
          <Download :size="16" aria-hidden="true" />模板
        </button>
        <button class="btn btn--primary" type="button" @click="emit('upload')">
          <Upload :size="16" aria-hidden="true" />上传新版本
        </button>
      </div>
    </header>

    <div class="batch-strip">
      <div class="batch-strip__file">
        <FileSpreadsheet :size="18" aria-hidden="true" />
        <span><strong>{{ state.fileName }}</strong><small>模板 v1.0 · TI-20260828-001</small></span>
      </div>
      <div class="batch-strip__metric batch-strip__metric--danger"><strong>{{ counts.blockers }}</strong><span>阻断</span></div>
      <div class="batch-strip__metric batch-strip__metric--warning"><strong>{{ counts.warnings }}</strong><span>警告</span></div>
      <div class="batch-strip__metric"><strong>193</strong><span>业务记录</span></div>
      <div class="batch-strip__metric"><strong>124</strong><span>教学任务</span></div>
      <div class="batch-strip__status">
        <span :class="['status-dot', state.fileState === 'issues' ? 'status-dot--danger' : 'status-dot--success']" />
        {{ state.fileState === 'issues' ? '等待修正' : state.fileState === 'fixed' ? '可以导入' : '已导入' }}
      </div>
    </div>

    <div v-if="state.fileState === 'committed'" class="variant-b__success">
      <div><FileCheck2 :size="20" /><span><strong>批次已成功导入</strong> · 手工修改的数据未被覆盖</span></div>
      <button v-if="!state.readinessConfirmed" class="btn btn--primary" type="button" @click="emit('confirm')">
        <ShieldCheck :size="16" />{{ state.mode === 'ready' ? '确认排课就绪' : '进入排课准备检查' }}
      </button>
      <span v-else class="ready-mark"><CheckCircle2 :size="17" />已确认就绪</span>
    </div>

    <div class="inbox-layout">
      <aside class="inbox-folders">
        <div class="inbox-folders__heading"><Filter :size="15" /><span>审查队列</span></div>
        <button :class="{ active: state.issueFilter === 'all' }" type="button" @click="emit('set-filter', 'all')">
          <Inbox :size="17" /><span>全部问题</span><strong>{{ issues.length }}</strong>
        </button>
        <button :class="{ active: state.issueFilter === 'blocker' }" type="button" @click="emit('set-filter', 'blocker')">
          <CircleAlert :size="17" /><span>阻断项</span><strong>{{ blockerCount }}</strong>
        </button>
        <button :class="{ active: state.issueFilter === 'warning' }" type="button" @click="emit('set-filter', 'warning')">
          <AlertTriangle :size="17" /><span>警告项</span><strong>{{ warningCount }}</strong>
        </button>

        <div class="inbox-folders__divider" />
        <p class="proto-kicker">工作表</p>
        <button
          v-for="sheet in sheets.filter((item) => item.status === 'attention')"
          :key="sheet.name"
          type="button"
        >
          <FileSpreadsheet :size="16" /><span>{{ sheet.name }}</span><strong>{{ sheet.rows }}</strong>
        </button>
      </aside>

      <main class="inbox-list" aria-label="问题列表">
        <div class="inbox-list__toolbar">
          <div>
            <h2>{{ state.issueFilter === 'all' ? '全部问题' : state.issueFilter === 'blocker' ? '阻断项' : '警告项' }}</h2>
            <span>按模板位置排序</span>
          </div>
          <button type="button" title="重新校验" aria-label="重新校验" @click="emit('fix')"><RefreshCw :size="16" /></button>
        </div>

        <div v-if="filteredIssues.length" class="inbox-list__rows">
          <button
            v-for="issue in filteredIssues"
            :key="issue.id"
            :class="['inbox-item', { active: selectedIssue?.id === issue.id }]"
            type="button"
            @click="emit('select-issue', issue.id)"
          >
            <span :class="['severity-icon', `severity-icon--${issue.severity}`]">
              <CircleAlert v-if="issue.severity === 'blocker'" :size="17" />
              <AlertTriangle v-else :size="17" />
            </span>
            <span class="inbox-item__body">
              <span><strong>{{ issue.title }}</strong><small>{{ issue.sheet }} · 第 {{ issue.row }} 行 · {{ issue.field }}</small></span>
              <span class="inbox-item__value">{{ issue.value }}</span>
            </span>
            <ChevronRight :size="16" aria-hidden="true" />
          </button>
        </div>
        <div v-else class="empty-queue">
          <CheckCircle2 :size="32" />
          <h2>这个队列已清空</h2>
          <p>切换筛选条件查看其余记录。</p>
        </div>
      </main>

      <aside class="issue-inspector">
        <template v-if="selectedIssue">
          <div class="issue-inspector__heading">
            <span :class="['severity-label', `severity-label--${selectedIssue.severity}`]">
              {{ selectedIssue.severity === 'blocker' ? '阻断' : '警告' }}
            </span>
            <span>{{ selectedIssue.id }}</span>
          </div>
          <h2>{{ selectedIssue.title }}</h2>
          <p>{{ selectedIssue.detail }}</p>

          <dl class="issue-detail-list">
            <div><dt>位置</dt><dd>{{ selectedIssue.sheet }} / 第 {{ selectedIssue.row }} 行</dd></div>
            <div><dt>字段</dt><dd>{{ selectedIssue.field }}</dd></div>
            <div><dt>当前值</dt><dd class="mono-cell">{{ selectedIssue.value }}</dd></div>
          </dl>

          <div class="suggestion-box">
            <strong>建议处理</strong>
            <p>{{ selectedIssue.suggestion }}</p>
          </div>

          <button v-if="state.fileState === 'issues'" class="btn btn--primary btn--full" type="button" @click="emit('fix')">
            <Upload :size="16" />载入修正后的文件
          </button>
          <button v-else-if="state.fileState === 'fixed'" class="btn btn--primary btn--full" type="button" @click="emit('commit')">
            <ShieldCheck :size="16" />确认并导入全部变更
          </button>
          <div v-else class="inspector-complete"><Check :size="17" />此批次已归档</div>
        </template>
        <div v-else class="empty-queue">
          <CheckCircle2 :size="32" />
          <h2>没有待审查问题</h2>
          <button v-if="state.fileState === 'fixed'" class="btn btn--primary" type="button" @click="emit('commit')">确认并导入</button>
        </div>
      </aside>
    </div>
  </div>
</template>
