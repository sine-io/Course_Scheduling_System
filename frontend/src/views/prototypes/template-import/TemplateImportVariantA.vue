<script setup lang="ts">
import { computed } from 'vue'
import {
  ArrowRight,
  Check,
  CheckCircle2,
  CircleAlert,
  Download,
  FileSpreadsheet,
  RefreshCw,
  ShieldCheck,
  Upload,
} from '@lucide/vue'
import type { ImportMode, PrototypeViewProps } from './types'

const props = defineProps<PrototypeViewProps>()

const emit = defineEmits<{
  'set-mode': [mode: ImportMode]
  download: []
  upload: []
  fix: []
  commit: []
  confirm: []
  reset: []
  'select-issue': [id: string]
}>()

const currentStep = computed(() => {
  if (props.state.readinessConfirmed) return 5
  if (props.state.fileState === 'committed') return 5
  if (props.state.fileState === 'fixed') return 4
  return 3
})

const steps = [
  { number: 1, label: '下载模板' },
  { number: 2, label: '上传文件' },
  { number: 3, label: '校验数据' },
  { number: 4, label: '确认变更' },
  { number: 5, label: '排课就绪' },
]

const visibleIssues = computed(() => props.issues.slice(0, 4))
</script>

<template>
  <div class="variant-a">
    <header class="variant-a__header">
      <div>
        <p class="proto-kicker">模板导入 / 分步向导</p>
        <h1>教师安排模板导入</h1>
        <p class="proto-subtitle">2026—2027 学年第一学期 · 目标学期已选择</p>
      </div>
      <div class="mode-control" aria-label="导入模式">
        <button
          type="button"
          :class="{ active: state.mode === 'standard' }"
          @click="emit('set-mode', 'standard')"
        >
          标准导入
        </button>
        <button
          type="button"
          :class="{ active: state.mode === 'ready' }"
          @click="emit('set-mode', 'ready')"
        >
          排课准备
        </button>
      </div>
    </header>

    <ol class="step-rail" aria-label="导入步骤">
      <li
        v-for="step in steps"
        :key="step.number"
        :class="{
          complete: step.number < currentStep || state.readinessConfirmed,
          current: step.number === currentStep && !state.readinessConfirmed,
        }"
      >
        <span class="step-rail__number">
          <Check v-if="step.number < currentStep || state.readinessConfirmed" :size="15" aria-hidden="true" />
          <template v-else>{{ step.number }}</template>
        </span>
        <span>{{ step.label }}</span>
      </li>
    </ol>

    <div class="variant-a__grid">
      <main class="proto-panel variant-a__main">
        <div v-if="state.fileState === 'issues'" class="stage-block">
          <div class="stage-block__heading">
            <span class="status-icon status-icon--danger"><CircleAlert :size="22" /></span>
            <div>
              <p class="proto-kicker">第 3 步 · 校验数据</p>
              <h2>有 {{ counts.blockers }} 项问题需要处理</h2>
              <p>请回到模板中修正阻断项，再上传同一批次的新版本。</p>
            </div>
          </div>

          <div class="issue-stack">
            <button
              v-for="issue in visibleIssues"
              :key="issue.id"
              class="issue-row"
              type="button"
              @click="emit('select-issue', issue.id)"
            >
              <span :class="['severity-mark', `severity-mark--${issue.severity}`]" aria-hidden="true" />
              <span class="issue-row__location">{{ issue.sheet }} · 第 {{ issue.row }} 行</span>
              <strong>{{ issue.title }}</strong>
              <span class="issue-row__field">{{ issue.field }}：{{ issue.value }}</span>
              <ArrowRight :size="16" aria-hidden="true" />
            </button>
          </div>

          <div class="stage-actions">
            <button class="btn btn--primary" type="button" @click="emit('fix')">
              <Upload :size="17" aria-hidden="true" />
              载入已修正版本
            </button>
            <button class="btn btn--secondary" type="button" @click="emit('download')">
              <Download :size="17" aria-hidden="true" />
              下载错误清单
            </button>
          </div>
        </div>

        <div v-else-if="state.fileState === 'fixed'" class="stage-block">
          <div class="stage-block__heading">
            <span class="status-icon status-icon--success"><CheckCircle2 :size="22" /></span>
            <div>
              <p class="proto-kicker">第 4 步 · 确认变更</p>
              <h2>校验通过，可以提交</h2>
              <p>系统将原子写入本批次；任何一条失败都不会产生部分数据。</p>
            </div>
          </div>

          <div class="change-summary" aria-label="变更统计">
            <div><strong>{{ counts.newRecords }}</strong><span>新增</span></div>
            <div><strong>{{ counts.changedRecords }}</strong><span>变更</span></div>
            <div><strong>{{ counts.unchangedRecords }}</strong><span>未变化</span></div>
            <div><strong>{{ counts.disappearedRecords }}</strong><span>来源中消失</span></div>
          </div>

          <div class="compact-table-wrap">
            <table class="compact-table">
              <thead>
                <tr><th>任务编码</th><th>班级</th><th>科目 / 组成</th><th>周课时</th><th>主讲教师</th><th>状态</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in changes.slice(0, 5)" :key="row.code">
                  <td class="mono-cell">{{ row.code }}</td>
                  <td>{{ row.className }}</td>
                  <td>{{ row.subject }} / {{ row.component }}</td>
                  <td>{{ row.periods }}</td>
                  <td>{{ row.teacher }}</td>
                  <td><span :class="['status-chip', `status-chip--${row.status}`]">{{ row.status === 'new' ? '新增' : row.status === 'changed' ? '变更' : row.status === 'unchanged' ? '未变化' : '待确认' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="stage-actions">
            <button class="btn btn--primary" type="button" @click="emit('commit')">
              <ShieldCheck :size="17" aria-hidden="true" />
              确认并导入
            </button>
            <button class="btn btn--secondary" type="button" @click="emit('reset')">
              <RefreshCw :size="17" aria-hidden="true" />
              重新开始
            </button>
          </div>
        </div>

        <div v-else class="stage-block">
          <div class="stage-block__heading">
            <span class="status-icon status-icon--success"><CheckCircle2 :size="22" /></span>
            <div>
              <p class="proto-kicker">导入批次 TI-20260828-001</p>
              <h2>教师安排已导入</h2>
              <p>导入成功不等于可以自动排课。请完成右侧就绪检查后，由教务主任确认。</p>
            </div>
          </div>

          <div class="readiness-list">
            <div><Check :size="16" /><span>12 个班级均已绑定作息时间表</span><strong>通过</strong></div>
            <div><Check :size="16" /><span>124 条教学任务周课时与班级计划一致</span><strong>通过</strong></div>
            <div><Check :size="16" /><span>专用场地需求均有候选教室</span><strong>通过</strong></div>
            <div><Check :size="16" /><span>教师、班级与教室容量检查</span><strong>通过</strong></div>
          </div>

          <div class="stage-actions">
            <button
              v-if="!state.readinessConfirmed"
              class="btn btn--primary"
              type="button"
              @click="emit('confirm')"
            >
              <ShieldCheck :size="17" aria-hidden="true" />
              {{ state.mode === 'ready' ? '教务主任确认排课就绪' : '进入排课准备检查' }}
            </button>
            <div v-else class="confirmation-banner">
              <CheckCircle2 :size="19" aria-hidden="true" />
              已确认就绪 · 下一步编辑并启用排课规则
            </div>
          </div>
        </div>
      </main>

      <aside class="proto-panel variant-a__side">
        <section class="side-section">
          <div class="side-section__heading">
            <FileSpreadsheet :size="18" aria-hidden="true" />
            <h2>当前文件</h2>
          </div>
          <strong class="file-name">{{ state.fileName }}</strong>
          <dl class="definition-list">
            <div><dt>模板版本</dt><dd>v1.0</dd></div>
            <div><dt>数据起始行</dt><dd>第 4 行</dd></div>
            <div><dt>业务规模</dt><dd>12 班 / 43 教师</dd></div>
            <div><dt>教学任务</dt><dd>124 条</dd></div>
          </dl>
        </section>

        <section class="side-section">
          <h2>本模式要求</h2>
          <ul class="requirement-list">
            <li>任务编码必须唯一</li>
            <li>复合课时必须拆成组成行</li>
            <li v-if="state.mode === 'ready'">每条任务必须指定主讲教师</li>
            <li v-if="state.mode === 'ready'">班级必须绑定完整作息</li>
            <li v-else>教师缺失允许导入，但会给出警告</li>
          </ul>
        </section>

        <button class="template-download" type="button" @click="emit('download')">
          <Download :size="18" aria-hidden="true" />
          <span><strong>下载{{ state.mode === 'ready' ? '自动排课准备' : '教师安排标准' }}模板</strong><small>Excel · v1.0</small></span>
        </button>
      </aside>
    </div>
  </div>
</template>
