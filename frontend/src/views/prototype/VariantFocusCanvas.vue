<script setup lang="ts">
import {
  AlertTriangle,
  Bell,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  FileCheck2,
  Filter,
  Inbox,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  MoreHorizontal,
  PanelBottom,
  PanelTop,
  Plus,
  Search,
  ShieldAlert,
  Users,
  X,
} from '@lucide/vue'
import { ref } from 'vue'
import PrototypeIconButton from './PrototypeIconButton.vue'
import PrototypeStateControl from './PrototypeStateControl.vue'
import PrototypeTimetable from './PrototypeTimetable.vue'
import type { CourseCell, NavItem, StatusMode, VariantProps, ViewKey } from './prototypeData'
import { metrics, navGroups, substitutionChanges, unscheduledCourses } from './prototypeData'

// THROWAWAY PROTOTYPE — Variant C: horizontal chrome and a focus canvas.

const props = defineProps<VariantProps>()

const emit = defineEmits<{
  navigate: [view: ViewKey]
  'toggle-drawer': []
  'close-drawer': []
  'toggle-collapse': []
  'set-status': [mode: StatusMode]
  'select-course': [course: CourseCell]
  toast: [message: string]
  'open-confirm': []
}>()

const poolOpen = ref(true)
const filterOpen = ref(false)
const workbenchView = ref<'class' | 'teacher' | 'room'>('class')

function chooseNav(item: NavItem) {
  if (item.view) emit('navigate', item.view)
  else emit('toast', `“${item.label}”在生产页面中保持原有路由（本原型未展开）`)
}

function selectCourse(course: CourseCell) {
  emit('select-course', course)
}

function active(item: NavItem) {
  return item.view === props.activeView
}
</script>

<template>
  <div class="variant-c-shell" :class="{ 'is-compact': collapsed, 'is-drawer-open': drawerOpen }">
    <header class="variant-c-header">
      <div class="variant-c-brand"><span class="variant-c-brand-mark"><CalendarDays :size="19" aria-hidden="true" /></span><span><strong>教务排课</strong><small>学校排课、调课与代课管理系统</small></span></div>
      <nav class="variant-c-nav" aria-label="主导航"><button type="button" :class="{ 'is-active': active({ key: 'dashboard', label: '仪表盘', icon: LayoutDashboard, view: 'dashboard' }) }" @click="emit('navigate', 'dashboard')">仪表盘</button><button type="button" :class="{ 'is-active': active({ key: 'workbench', label: '排课工作台', icon: LayoutDashboard, view: 'workbench' }) }" @click="emit('navigate', 'workbench')">排课作业</button><button type="button" @click="emit('toast', '调课与代课入口已打开')">调课与代课</button><button type="button" @click="emit('toast', '基础数据入口已打开')">基础数据</button></nav>
      <div class="variant-c-header-actions"><PrototypeStateControl :model-value="statusMode" @update:model-value="emit('set-status', $event)" /><PrototypeIconButton :icon="Bell" label="通知" @click="emit('toast', '有 2 条待确认的调课通知')" /><span class="variant-c-user"><span>张</span><strong>张教务</strong><ChevronDown :size="13" aria-hidden="true" /></span><PrototypeIconButton :icon="Menu" label="打开导航" class="variant-c-menu" @click="emit('toggle-drawer')" /></div>
    </header>

    <div v-if="drawerOpen" class="variant-c-scrim" aria-hidden="true" @click="emit('close-drawer')" />
    <aside class="variant-c-drawer" :class="{ 'is-open': drawerOpen }" aria-label="移动端导航">
      <div class="variant-c-drawer-head"><div><strong>教务排课</strong><small>排课 · 调课 · 代课</small></div><PrototypeIconButton :icon="X" label="关闭导航" compact @click="emit('close-drawer')" /></div>
      <div class="variant-c-drawer-links"><section v-for="group in navGroups" :key="group.label"><p>{{ group.label }}</p><button v-for="item in group.items" :key="item.key" type="button" :class="{ 'is-active': active(item) }" @click="chooseNav(item)"><component :is="item.icon" :size="16" /><span>{{ item.label }}</span></button></section></div>
      <button class="variant-c-drawer-compact" type="button" @click="emit('toggle-collapse')"><PanelTop :size="15" />{{ collapsed ? '恢复完整导航' : '收起到图标' }}</button>
    </aside>

    <main class="variant-c-main">
      <div class="variant-c-contextbar"><div><span>当前模块</span><strong>{{ activeView === 'dashboard' ? '运行概览' : '排课工作台' }}</strong></div><span class="context-separator">/</span><div><span>学期</span><strong>2026—2027 秋季学期</strong></div><div class="context-spacer" /><span class="proto-chip orange">草稿 · 未发布</span><button class="proto-button ghost small" type="button" @click="emit('toast', '版本详情已打开')">版本 v3.2 <ChevronRight :size="13" /></button></div>

      <section v-if="activeView === 'dashboard'" class="variant-c-dashboard" aria-labelledby="variant-c-dashboard-title">
        <header class="variant-c-heading"><div><span class="eyebrow">运行概览 · 2026.09.14 星期一</span><h1 id="variant-c-dashboard-title">仪表盘</h1><p>保持信息连续、动作靠近数据。</p></div><div class="variant-c-heading-actions"><button class="proto-button" type="button" @click="emit('toast', '已刷新代表性数据')"><Search :size="14" />刷新摘要</button><button class="proto-button primary" type="button" @click="emit('navigate', 'workbench')"><LayoutDashboard :size="14" />处理排课</button></div></header>
        <div v-if="statusMode === 'normal'" class="variant-c-metric-strip"><div v-for="metric in metrics" :key="metric.label" class="c-metric-line"><span class="c-metric-icon" :class="`tone-${metric.tone}`"><component :is="metric.icon" :size="15" /></span><span class="c-metric-copy"><small>{{ metric.label }}</small><strong>{{ metric.value }}</strong><em>{{ metric.detail }}</em></span></div><div class="c-metric-health"><CheckCircle2 :size="16" /><span><strong>系统状态正常</strong><small>最近同步 2 分钟前</small></span></div></div>
        <div v-else class="variant-c-wide-state" :class="`is-${statusMode}`" :role="statusMode === 'error' ? 'alert' : 'status'"><Search v-if="statusMode === 'loading'" class="state-spin" :size="23" /><FileCheck2 v-else-if="statusMode === 'empty'" :size="23" /><ShieldAlert v-else-if="statusMode === 'restricted'" :size="23" /><CircleAlert v-else :size="23" /><strong>{{ statusMode === 'loading' ? '摘要读取中' : statusMode === 'empty' ? '尚未创建学期数据' : statusMode === 'restricted' ? '学校级摘要访问受限' : '摘要请求失败' }}</strong><span>{{ statusMode === 'error' ? '请确认服务连接后重试。' : statusMode === 'restricted' ? '当前角色可查看已发布课表，但不能访问排课摘要。' : '四项真实摘要会在这里连续呈现。' }}</span><button v-if="statusMode !== 'loading' && statusMode !== 'restricted'" class="proto-button small" type="button" @click="emit('set-status', 'normal')">重试</button></div>

        <div class="variant-c-dashboard-grid">
          <article class="variant-c-work-queue"><header class="c-section-header"><div><span class="panel-kicker">TODAY · WORK QUEUE</span><h2>今日变动</h2></div><button class="proto-button ghost small" type="button" @click="emit('toast', '已打开今日看板')">完整看板 <ChevronRight :size="13" /></button></header><div v-if="statusMode === 'normal'" class="c-change-table"><div class="c-change-head"><span>时间</span><span>班级 / 科目</span><span>教师变更</span><span>状态</span><span /></div><button v-for="change in substitutionChanges" :key="change.id" class="c-change-row" type="button" @click="emit('toast', `${change.className}的处理详情已打开`)"><span>{{ change.time }}</span><strong>{{ change.className }} · {{ change.subject }}</strong><span>{{ change.from }} <span aria-hidden="true">→</span> {{ change.to }}</span><span class="substitution-state" :class="change.state === '待确认' ? 'is-pending' : 'is-done'">{{ change.state }}</span><ChevronRight :size="14" /></button></div><div v-else class="c-queue-state" :class="`is-${statusMode}`" :role="statusMode === 'error' ? 'alert' : 'status'"><LoaderCircle v-if="statusMode === 'loading'" class="state-spin" :size="20" /><Inbox v-else-if="statusMode === 'empty'" :size="22" /><ShieldAlert v-else-if="statusMode === 'restricted'" :size="22" /><AlertTriangle v-else :size="22" /><strong>{{ statusMode === 'loading' ? '正在读取变动' : statusMode === 'empty' ? '今日无调课与代课' : statusMode === 'restricted' ? '队列仅限排课管理员' : '看板请求失败' }}</strong><span>{{ statusMode === 'restricted' ? '可在课表查询中查看已发布课表。' : '这里保留真实看板的空、加载和失败状态。' }}</span></div></article>
          <aside class="variant-c-readiness"><header class="c-section-header"><div><span class="panel-kicker">RELEASE CHECK</span><h2>发布前检查</h2></div><MoreHorizontal :size="17" aria-hidden="true" /></header><div class="c-readiness-total"><strong>3 / 4</strong><span>检查项已通过</span></div><div class="c-check-list"><div><CheckCircle2 :size="15" /><span>教师与班级不冲突</span></div><div><CheckCircle2 :size="15" /><span>场地资源可用</span></div><div><CheckCircle2 :size="15" /><span>作息时间表完整</span></div><div class="is-warning"><ShieldAlert :size="15" /><span>1 条教师时间规则冲突</span></div></div><button class="proto-button secondary small" type="button" :disabled="statusMode === 'restricted'" @click="emit('open-confirm')"><FileCheck2 :size="14" />查看发布确认</button></aside>
        </div>
        <section class="variant-c-action-row"><div class="c-action-label"><span class="panel-kicker">QUICK ACTIONS</span><strong>常用入口</strong></div><button type="button" @click="emit('navigate', 'workbench')"><LayoutDashboard :size="16" /><span><strong>排课工作台</strong><small>处理未排课程</small></span><ChevronRight :size="14" /></button><button type="button" @click="emit('toast', '教学任务入口已打开')"><Users :size="16" /><span><strong>教学任务</strong><small>教师与班级分配</small></span><ChevronRight :size="14" /></button><button type="button" @click="emit('toast', '调课看板入口已打开')"><Bell :size="16" /><span><strong>今日看板</strong><small>确认代课变动</small></span><ChevronRight :size="14" /></button></section>
      </section>

      <section v-else class="variant-c-workbench" aria-labelledby="variant-c-workbench-title">
        <header class="variant-c-heading"><div><span class="eyebrow">排课作业 · CLASS VIEW</span><h1 id="variant-c-workbench-title">排课工作台</h1><p>八年级 2 班 · 草稿 v3.2 · 实时校验。</p></div><div class="variant-c-heading-actions"><button class="proto-button" type="button" @click="filterOpen = !filterOpen"><Filter :size="14" />筛选 <span v-if="filterOpen" class="filter-dot" /></button><button class="proto-button" type="button" :disabled="statusMode === 'restricted'" @click="emit('toast', '撤销栈为空')">撤销</button><button class="proto-button primary" type="button" :disabled="statusMode === 'restricted'" @click="emit('open-confirm')">发布草稿</button></div></header>
        <div v-if="filterOpen" class="variant-c-filterbar"><label>班级<select class="proto-select"><option>八年级 2 班</option><option>八年级 3 班</option></select></label><label>学期<select class="proto-select"><option>2026—2027 秋季学期</option></select></label><div class="view-switch" role="tablist"><button v-for="item in ['class', 'teacher', 'room']" :key="item" type="button" role="tab" :aria-selected="workbenchView === item" :class="{ 'is-active': workbenchView === item }" @click="workbenchView = item as 'class' | 'teacher' | 'room'">{{ item === 'class' ? '班级' : item === 'teacher' ? '教师' : '教室' }}</button></div><span class="proto-chip red"><AlertTriangle :size="12" />1 条冲突</span></div>
        <article class="variant-c-canvas"><header class="c-canvas-header"><div><span class="panel-kicker">八年级 2 班 · 课表</span><h2>正式课表草稿 v3.2</h2></div><div class="c-canvas-actions"><span class="proto-chip blue">6 节已锁定</span><span class="proto-chip green">实时校验</span><PrototypeIconButton :icon="PanelBottom" label="切换未排课程池" compact :active="poolOpen" @click="poolOpen = !poolOpen" /></div></header><div class="c-canvas-body"><PrototypeTimetable :status-mode="statusMode" :selected-course-key="selectedCourseKey" @select="selectCourse" /><div v-if="selectedCourseKey" class="c-selection-note"><span><strong>已选择 {{ selectedCourseKey }}</strong><small>右侧动作仅影响当前草稿</small></span><button class="proto-button secondary small" type="button" @click="emit('toast', '可用节次列表已打开')">查看可用节次 <ChevronRight :size="13" /></button></div></div></article>
        <section v-if="poolOpen" class="variant-c-pool-drawer"><header class="c-pool-header"><div><span class="panel-kicker">UNSCHEDULED COURSES</span><h2>未排课程池</h2></div><div><span class="proto-chip blue">剩余 5 节</span><PrototypeIconButton :icon="PanelBottom" label="收起课程池" compact @click="poolOpen = false" /></div></header><div class="c-pool-list"><button v-for="course in unscheduledCourses" :key="course.id" type="button" class="c-pool-item" :disabled="statusMode === 'restricted'" @click="emit('toast', `${course.subject}已加入拖拽选择`)"><span class="c-pool-color" :class="`tone-${course.tone}`" /><span><strong>{{ course.subject }}</strong><small>{{ course.teacher }}</small></span><span class="c-pool-count">{{ course.remaining }} 节</span><ChevronRight :size="14" /></button><button class="c-pool-add" type="button" :disabled="statusMode === 'restricted'" @click="emit('toast', '课程筛选器已打开')"><Plus :size="15" />添加课程筛选</button></div></section><button v-else class="c-pool-reopen" type="button" @click="poolOpen = true"><PanelTop :size="15" />展开未排课程池 <span>5 节</span></button>
      </section>
    </main>
  </div>
</template>

<style scoped>
.variant-c-shell { min-height: 100vh; background: var(--proto-bg); }
.variant-c-header { position: relative; z-index: 20; display: flex; min-height: 74px; align-items: center; gap: 24px; padding: 0 clamp(15px, 3vw, 38px); border-bottom: 1px solid var(--proto-line); background: var(--proto-surface); }
.variant-c-brand { display: flex; min-width: 235px; align-items: center; gap: 9px; }
.variant-c-brand-mark { display: grid; width: 35px; height: 35px; flex: 0 0 auto; place-items: center; border-radius: 7px; background: var(--proto-primary); color: #fff; }
.variant-c-brand > span:last-child { display: grid; gap: 2px; min-width: 0; }
.variant-c-brand strong { font-size: 14px; }
.variant-c-brand small { overflow: hidden; color: var(--proto-text-muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.variant-c-nav { display: flex; align-self: stretch; gap: 20px; }
.variant-c-nav button { position: relative; padding: 0 1px; border: 0; background: transparent; color: var(--proto-text-muted); cursor: pointer; font-size: 12px; }
.variant-c-nav button:hover, .variant-c-nav button.is-active { color: var(--proto-primary); }
.variant-c-nav button.is-active { font-weight: 700; }
.variant-c-nav button.is-active::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; background: var(--proto-primary); content: ''; }
.variant-c-header-actions { display: flex; min-width: 0; align-items: center; gap: 7px; margin-left: auto; }
.variant-c-user { display: flex; align-items: center; gap: 6px; padding-left: 4px; }
.variant-c-user > span { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 6px; background: #dce7fb; color: var(--proto-primary); font-size: 11px; font-weight: 800; }
.variant-c-user strong { font-size: 10px; }
.variant-c-menu { display: none; }
.variant-c-main { min-width: 0; padding-bottom: 86px; }
.variant-c-contextbar { display: flex; min-height: 47px; align-items: center; gap: 10px; padding: 0 clamp(15px, 3vw, 38px); border-bottom: 1px solid var(--proto-line); background: #fbfcfe; }
.variant-c-contextbar > div:not(.context-spacer) { display: flex; align-items: baseline; gap: 7px; }
.variant-c-contextbar span:not(.proto-chip):not(.context-separator) { color: var(--proto-text-faint); font-size: 9px; }
.variant-c-contextbar strong { font-size: 10px; }
.context-separator { color: var(--proto-line-strong); font-size: 14px; }
.context-spacer { flex: 1; }
.variant-c-dashboard, .variant-c-workbench { min-width: 0; padding: 28px clamp(15px, 3vw, 38px) 0; }
.variant-c-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 19px; }
.variant-c-heading h1 { margin: 5px 0 0; font-size: clamp(22px, 2.1vw, 28px); }
.variant-c-heading p { margin: 6px 0 0; color: var(--proto-text-muted); font-size: 12px; }
.variant-c-heading-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }
.variant-c-metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)) minmax(180px, .85fr); border: 1px solid var(--proto-line); border-radius: var(--proto-radius); background: var(--proto-surface); box-shadow: var(--proto-shadow); }
.c-metric-line { display: flex; min-width: 0; align-items: center; gap: 9px; padding: 15px 14px; border-right: 1px solid var(--proto-line); }
.c-metric-icon { display: grid; width: 30px; height: 30px; flex: 0 0 auto; place-items: center; border-radius: 6px; }
.c-metric-icon.tone-blue { background: var(--proto-blue-soft); color: var(--proto-primary); }
.c-metric-icon.tone-teal { background: var(--proto-teal-soft); color: #087d79; }
.c-metric-icon.tone-purple { background: var(--proto-purple-soft); color: #5d47b8; }
.c-metric-icon.tone-orange { background: var(--proto-orange-soft); color: var(--proto-warning); }
.c-metric-copy { display: grid; min-width: 0; gap: 2px; }
.c-metric-copy small { color: var(--proto-text-muted); font-size: 9px; }
.c-metric-copy strong { font-size: 21px; line-height: 1; }
.c-metric-copy em { overflow: hidden; color: var(--proto-text-faint); font-size: 8px; font-style: normal; text-overflow: ellipsis; white-space: nowrap; }
.c-metric-health { display: flex; align-items: center; gap: 8px; padding: 15px 14px; color: var(--proto-success); }
.c-metric-health span { display: grid; gap: 3px; }
.c-metric-health strong { color: var(--proto-text); font-size: 10px; }
.c-metric-health small { color: var(--proto-text-muted); font-size: 9px; }
.variant-c-wide-state { display: grid; min-height: 111px; place-items: center; align-content: center; gap: 6px; margin-top: 12px; border: 1px dashed var(--proto-line-strong); border-radius: var(--proto-radius); background: var(--proto-surface); color: var(--proto-text-muted); text-align: center; }
.variant-c-wide-state strong { color: var(--proto-text); font-size: 12px; }
.variant-c-wide-state span { font-size: 10px; }
.variant-c-wide-state.is-error { border-color: #efc5c8; color: var(--proto-danger); }
.variant-c-wide-state.is-error strong { color: var(--proto-danger); }
.variant-c-wide-state.is-restricted, .c-queue-state.is-restricted { color: var(--proto-warning); }
.variant-c-wide-state.is-restricted { border-color: #f0d2ad; }
.variant-c-dashboard-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(225px, .55fr); gap: 12px; margin-top: 12px; }
.variant-c-work-queue, .variant-c-readiness, .variant-c-canvas, .variant-c-pool-drawer { min-width: 0; border: 1px solid var(--proto-line); border-radius: var(--proto-radius); background: var(--proto-surface); box-shadow: var(--proto-shadow); }
.c-section-header, .c-canvas-header, .c-pool-header { display: flex; min-height: 62px; align-items: center; justify-content: space-between; gap: 10px; padding: 14px 15px; border-bottom: 1px solid var(--proto-line); }
.c-section-header h2, .c-canvas-header h2, .c-pool-header h2 { margin: 4px 0 0; font-size: 13px; }
.c-section-header > div:first-child, .c-canvas-header > div:first-child, .c-pool-header > div:first-child { display: grid; min-width: 0; }
.c-change-table { padding: 0 15px 11px; }
.c-change-head, .c-change-row { display: grid; grid-template-columns: 62px minmax(130px, 1.2fr) minmax(120px, 1fr) 57px 18px; align-items: center; gap: 7px; }
.c-change-head { min-height: 32px; color: var(--proto-text-faint); font-size: 9px; }
.c-change-row { width: 100%; min-height: 47px; border: 0; border-top: 1px solid #edf0f4; background: transparent; color: var(--proto-text); cursor: pointer; font-size: 10px; text-align: left; }
.c-change-row:hover { background: #fbfcfe; }
.c-change-row > strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.c-change-row > span:nth-child(3) { overflow: hidden; color: var(--proto-text-muted); text-overflow: ellipsis; white-space: nowrap; }
.c-change-row .substitution-state { font-size: 9px; }
.c-change-row > svg { color: var(--proto-text-faint); }
.c-queue-state { display: grid; min-height: 245px; place-items: center; align-content: center; gap: 7px; color: var(--proto-text-muted); text-align: center; }
.c-queue-state strong { color: var(--proto-text); font-size: 12px; }
.c-queue-state span { font-size: 10px; }
.variant-c-readiness { min-height: 300px; }
.c-readiness-total { display: flex; align-items: baseline; gap: 8px; padding: 17px 15px 10px; }
.c-readiness-total strong { color: var(--proto-primary); font-size: 27px; }
.c-readiness-total span { color: var(--proto-text-muted); font-size: 10px; }
.c-check-list { display: grid; gap: 11px; padding: 4px 15px 16px; }
.c-check-list div { display: flex; align-items: center; gap: 7px; color: var(--proto-success); font-size: 10px; }
.c-check-list div.is-warning { color: var(--proto-warning); }
.variant-c-readiness > .proto-button { margin: 0 15px 15px; }
.variant-c-action-row { display: grid; grid-template-columns: 170px repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.c-action-label { display: grid; align-content: center; gap: 4px; padding: 0 3px; }
.c-action-label strong { font-size: 13px; }
.variant-c-action-row > button { display: flex; min-width: 0; align-items: center; gap: 9px; padding: 12px; border: 1px solid var(--proto-line); border-radius: 6px; background: var(--proto-surface); color: var(--proto-text); cursor: pointer; text-align: left; }
.variant-c-action-row > button:hover { border-color: #cbdcff; }
.variant-c-action-row > button > span { display: grid; min-width: 0; flex: 1; gap: 3px; }
.variant-c-action-row > button strong, .variant-c-action-row > button small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.variant-c-action-row > button strong { font-size: 11px; }
.variant-c-action-row > button small { color: var(--proto-text-muted); font-size: 9px; }
.variant-c-action-row > button > svg:first-child { color: var(--proto-primary); }
.variant-c-action-row > button > svg:last-child { color: var(--proto-text-faint); }
.variant-c-filterbar { display: flex; align-items: flex-end; gap: 9px; margin: -5px 0 12px; padding: 10px 12px; border: 1px solid var(--proto-line); border-radius: var(--proto-radius); background: var(--proto-surface); }
.variant-c-filterbar label { display: grid; gap: 4px; color: var(--proto-text-muted); font-size: 10px; }
.filter-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--proto-danger); }
.variant-c-canvas { overflow: hidden; }
.c-canvas-header { align-items: center; }
.c-canvas-actions { display: flex; align-items: center; gap: 5px; }
.c-canvas-body { padding: 0 15px 15px; }
.c-selection-note { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 12px; padding: 9px 10px; border: 1px solid #cbdcff; border-radius: 6px; background: var(--proto-blue-soft); }
.c-selection-note > span { display: grid; gap: 3px; }
.c-selection-note strong { font-size: 11px; }
.c-selection-note small { color: var(--proto-text-muted); font-size: 9px; }
.variant-c-pool-drawer { margin-top: 12px; }
.c-pool-header > div:last-child { display: flex; align-items: center; gap: 6px; }
.c-pool-list { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; padding: 12px 15px 15px; }
.c-pool-item { display: flex; min-width: 0; align-items: center; gap: 8px; padding: 10px; border: 1px solid var(--proto-line); border-radius: 6px; background: var(--proto-surface); color: var(--proto-text); cursor: pointer; text-align: left; }
.c-pool-item:hover { border-color: #cbdcff; }
.c-pool-color { width: 4px; height: 32px; flex: 0 0 auto; border-radius: 2px; background: var(--proto-primary); }
.c-pool-color.tone-teal { background: #12a8a0; }
.c-pool-color.tone-orange { background: #e17c12; }
.c-pool-color.tone-purple { background: #7a5af8; }
.c-pool-item > span:nth-child(2) { display: grid; min-width: 0; flex: 1; gap: 3px; }
.c-pool-item strong, .c-pool-item small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.c-pool-item strong { font-size: 10px; }
.c-pool-item small { color: var(--proto-text-muted); font-size: 9px; }
.c-pool-count { color: var(--proto-primary); font-size: 9px; white-space: nowrap; }
.c-pool-item > svg { color: var(--proto-text-faint); }
.c-pool-add { display: flex; min-height: 51px; align-items: center; justify-content: center; gap: 6px; border: 1px dashed var(--proto-line-strong); border-radius: 6px; background: var(--proto-surface-muted); color: var(--proto-primary); cursor: pointer; font-size: 10px; }
.c-pool-reopen { display: flex; min-height: 38px; align-items: center; gap: 7px; margin-top: 12px; padding: 0 13px; border: 1px dashed var(--proto-line-strong); border-radius: 6px; background: var(--proto-surface); color: var(--proto-primary); cursor: pointer; font-size: 10px; }
.c-pool-reopen span { margin-left: auto; color: var(--proto-text-muted); }
.variant-c-drawer, .variant-c-scrim { display: none; }

@media (max-width: 1050px) {
  .variant-c-header { gap: 16px; }
  .variant-c-brand { min-width: 200px; }
  .variant-c-nav { gap: 13px; }
  .variant-c-metric-strip { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .c-metric-health { grid-column: 1 / -1; border-top: 1px solid var(--proto-line); }
  .variant-c-action-row { grid-template-columns: 130px repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 780px) {
  .variant-c-brand { min-width: 170px; }
  .variant-c-nav { gap: 10px; }
  .variant-c-nav button:nth-child(n+3) { display: none; }
  .variant-c-user strong, .variant-c-user > svg { display: none; }
  .variant-c-dashboard-grid { grid-template-columns: 1fr; }
  .variant-c-action-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .c-action-label { grid-column: 1 / -1; min-height: 32px; }
  .c-pool-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 560px) {
  .variant-c-header { min-height: 62px; gap: 7px; padding: 0 12px; }
  .variant-c-brand { min-width: 0; flex: 1; }
  .variant-c-brand-mark { width: 31px; height: 31px; }
  .variant-c-brand strong { font-size: 12px; }
  .variant-c-brand small { display: none; }
  .variant-c-nav { display: none; }
  .variant-c-header-actions { margin-left: 0; }
  .variant-c-header-actions .prototype-state-control, .variant-c-user { display: none; }
  .variant-c-menu { display: inline-grid; }
  .variant-c-drawer { position: fixed; z-index: 30; top: 0; right: 0; bottom: 0; left: 0; display: flex; flex-direction: column; pointer-events: none; transform: translateX(-102%); background: var(--proto-surface); transition: transform 150ms ease; }
  .variant-c-drawer.is-open { pointer-events: auto; transform: translateX(0); }
  .variant-c-scrim { position: fixed; z-index: 29; inset: 0; display: block; background: rgba(18, 31, 50, .36); }
  .variant-c-drawer-head { display: flex; align-items: center; justify-content: space-between; padding: 17px 15px; border-bottom: 1px solid var(--proto-line); }
  .variant-c-drawer-head div { display: grid; gap: 3px; }
  .variant-c-drawer-head strong { font-size: 14px; }
  .variant-c-drawer-head small { color: var(--proto-text-muted); font-size: 10px; }
  .variant-c-drawer-links { flex: 1; overflow-y: auto; padding: 14px 12px; }
  .variant-c-drawer-links section + section { margin-top: 14px; }
  .variant-c-drawer-links p { margin: 0 8px 6px; color: var(--proto-text-faint); font-size: 10px; }
  .variant-c-drawer-links button { display: flex; width: 100%; min-height: 38px; align-items: center; gap: 9px; padding: 0 9px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--proto-text-muted); cursor: pointer; font-size: 11px; text-align: left; }
  .variant-c-drawer-links button.is-active, .variant-c-drawer-links button:hover { border-color: #cbdcff; background: var(--proto-blue-soft); color: var(--proto-primary); }
  .variant-c-drawer-compact { display: flex; align-items: center; gap: 7px; margin: 12px; padding: 10px; border: 1px solid var(--proto-line); border-radius: 6px; background: var(--proto-surface-muted); color: var(--proto-text-muted); cursor: pointer; font-size: 10px; }
  .variant-c-contextbar { min-height: 43px; gap: 7px; padding: 0 12px; overflow: hidden; }
  .variant-c-contextbar > div:not(.context-spacer) { gap: 4px; }
  .variant-c-contextbar > div:nth-of-type(2), .variant-c-contextbar .context-separator { display: none; }
  .variant-c-contextbar > .proto-button { display: none; }
  .variant-c-dashboard, .variant-c-workbench { padding: 19px 12px 0; }
  .variant-c-heading { align-items: flex-start; flex-direction: column; }
  .variant-c-heading h1 { font-size: 23px; }
  .variant-c-heading-actions { width: 100%; justify-content: flex-start; }
  .variant-c-heading-actions .proto-button { flex: 1; }
  .variant-c-metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .c-metric-line { border-bottom: 1px solid var(--proto-line); }
  .c-metric-line:nth-child(2n) { border-right: 0; }
  .c-metric-health { grid-column: 1 / -1; border-top: 0; }
  .c-change-table { overflow-x: auto; }
  .c-change-head, .c-change-row { min-width: 540px; }
  .variant-c-action-row { grid-template-columns: 1fr; }
  .c-action-label { min-height: 28px; }
  .variant-c-filterbar { flex-wrap: wrap; }
  .variant-c-filterbar label { min-width: calc(50% - 5px); flex: 1; }
  .variant-c-filterbar .proto-select { width: 100%; min-width: 0; }
  .c-canvas-header { align-items: flex-start; }
  .c-canvas-actions { flex-wrap: wrap; justify-content: flex-end; }
  .c-canvas-body { padding: 0 10px 12px; }
  .c-selection-note { align-items: flex-start; flex-direction: column; }
  .c-pool-list { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .variant-c-drawer { transition: none; }
}
</style>
