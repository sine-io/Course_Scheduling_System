<script setup lang="ts">
import {
  AlertTriangle,
  ArrowUpRight,
  Bell,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  ClipboardList,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
} from '@lucide/vue'
import { ref } from 'vue'
import PrototypeIconButton from './PrototypeIconButton.vue'
import PrototypeStateControl from './PrototypeStateControl.vue'
import PrototypeTimetable from './PrototypeTimetable.vue'
import type { CourseCell, NavItem, StatusMode, VariantProps, ViewKey } from './prototypeData'
import {
  metrics,
  navGroups,
  shortcutItems,
  substitutionChanges,
  unscheduledCourses,
} from './prototypeData'

// THROWAWAY PROTOTYPE — Variant A: full rail with a direct workbench emphasis.

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

const workbenchView = ref<'class' | 'teacher' | 'room'>('class')
const trayFilter = ref<'all' | 'urgent'>('all')
function isActive(item: NavItem): boolean {
  return item.view === props.activeView
}

function chooseNav(item: NavItem) {
  if (item.view) emit('navigate', item.view)
  else emit('toast', `“${item.label}”在生产页面中保持原有路由（本原型未展开）`)
}

function selectCourse(course: CourseCell) {
  emit('select-course', course)
}

function clickShortcut(view: ViewKey) {
  emit('navigate', view)
}
</script>

<template>
  <div class="variant-a-shell" :class="{ 'is-collapsed': collapsed, 'is-drawer-open': drawerOpen }">
    <div v-if="drawerOpen" class="variant-a-scrim" aria-hidden="true" @click="emit('close-drawer')" />

    <aside class="variant-a-sidebar" :class="{ 'is-mobile-open': drawerOpen }" aria-label="主导航">
      <div class="variant-a-brand">
        <span class="variant-a-brand-mark" aria-hidden="true"><CalendarDays :size="20" :stroke-width="2" /></span>
        <span class="variant-a-brand-copy">
          <strong>教务排课</strong>
          <small>排课 · 调课 · 代课</small>
        </span>
        <PrototypeIconButton
          class="variant-a-mobile-close"
          :icon="PanelLeftClose"
          label="关闭导航"
          compact
          @click="emit('close-drawer')"
        />
      </div>

      <nav class="variant-a-nav">
        <section v-for="group in navGroups" :key="group.label" class="variant-a-nav-group">
          <p class="variant-a-nav-label">{{ group.label }}</p>
          <button
            v-for="item in group.items"
            :key="item.key"
            class="variant-a-nav-item"
            :class="{ 'is-active': isActive(item) }"
            type="button"
            :aria-current="isActive(item) ? 'page' : undefined"
            :title="collapsed ? item.label : undefined"
            @click="chooseNav(item)"
          >
            <span class="variant-a-nav-icon"><component :is="item.icon" :size="17" :stroke-width="1.8" /></span>
            <span class="variant-a-nav-text">{{ item.label }}</span>
            <span v-if="item.badge" class="variant-a-nav-badge">{{ item.badge }}</span>
          </button>
        </section>
      </nav>

      <div class="variant-a-sidebar-footer">
        <div class="variant-a-school-status">
          <span class="status-dot" aria-hidden="true" />
          <div><strong>青禾实验学校</strong><small>2026—2027 学年 · 秋季学期</small></div>
        </div>
        <button class="variant-a-collapse-button" type="button" :title="collapsed ? '展开导航' : '收起导航'" @click="emit('toggle-collapse')">
          <PanelLeftOpen v-if="collapsed" :size="16" aria-hidden="true" />
          <PanelLeftClose v-else :size="16" aria-hidden="true" />
          <span>{{ collapsed ? '展开导航' : '收起导航' }}</span>
        </button>
      </div>
    </aside>

    <div class="variant-a-main">
      <header class="variant-a-topbar">
        <PrototypeIconButton :icon="Menu" label="打开导航" class="variant-a-menu-button" @click="emit('toggle-drawer')" />
        <div class="variant-a-breadcrumb">
          <span>教务排课</span><span aria-hidden="true">/</span>
          <strong>{{ activeView === 'dashboard' ? '仪表盘' : '排课工作台' }}</strong>
        </div>
        <div class="variant-a-topbar-spacer" />
        <PrototypeStateControl :model-value="statusMode" @update:model-value="emit('set-status', $event)" />
        <PrototypeIconButton :icon="Bell" label="通知" @click="emit('toast', '有 2 条待确认的调课通知')" />
        <div class="variant-a-profile">
          <span class="variant-a-avatar">张</span>
          <span class="variant-a-profile-copy"><strong>张教务</strong><small>排课管理员</small></span>
          <ChevronDown :size="14" aria-hidden="true" />
        </div>
      </header>

      <main class="variant-a-content">
        <section v-if="activeView === 'dashboard'" class="variant-a-dashboard" aria-labelledby="variant-a-dashboard-title">
          <div class="variant-a-page-heading">
            <div>
              <p class="eyebrow">学期运行总览</p>
              <h1 id="variant-a-dashboard-title">仪表盘</h1>
              <p class="page-description">把今天需要确认的排课、调课和代课事项集中在一个工作面上。</p>
            </div>
            <div class="variant-a-heading-actions">
              <button class="proto-button" type="button" @click="emit('toast', '已刷新代表性数据')"><RefreshCw :size="15" aria-hidden="true" />刷新</button>
              <button class="proto-button primary" type="button" @click="emit('navigate', 'workbench')"><BookOpen :size="15" aria-hidden="true" />进入排课工作台</button>
            </div>
          </div>

          <div class="variant-a-semester-banner">
            <div class="semester-banner-icon"><CheckCircle2 :size="19" aria-hidden="true" /></div>
            <div class="semester-banner-copy"><strong>2026—2027 学年 · 秋季学期</strong><span>当前编辑版本：草稿 v3.2 · 最后保存 2 分钟前</span></div>
            <span class="proto-chip orange">草稿 · 未发布</span>
            <button class="proto-button secondary small" type="button" @click="emit('open-confirm')">检查发布</button>
          </div>

          <template v-if="statusMode === 'normal'">
            <div class="variant-a-metric-grid">
              <article v-for="metric in metrics" :key="metric.label" class="variant-a-metric">
                <span class="metric-icon" :class="`tone-${metric.tone}`"><component :is="metric.icon" :size="17" /></span>
                <span class="metric-label">{{ metric.label }}</span>
                <strong>{{ metric.value }}</strong>
                <small>{{ metric.detail }}</small>
              </article>
            </div>

            <div class="variant-a-dashboard-grid">
              <article class="variant-a-surface substitution-surface">
                <header class="surface-header"><div><h2>今日调课与代课</h2><p>2026 年 9 月 14 日 · 星期一</p></div><span class="proto-chip orange">4 项变动</span></header>
                <div class="substitution-list">
                  <button v-for="change in substitutionChanges" :key="change.id" class="substitution-row" type="button" @click="emit('toast', `${change.className}${change.subject}的处理详情已打开`)">
                    <span class="substitution-time">{{ change.time }}</span>
                    <span class="substitution-main"><strong>{{ change.className }} · {{ change.subject }}</strong><small>{{ change.from }} <span aria-hidden="true">→</span> {{ change.to }}</small></span>
                    <span class="substitution-state" :class="change.state === '待确认' ? 'is-pending' : 'is-done'">{{ change.state }}</span>
                  </button>
                </div>
                <button class="proto-button ghost small surface-link" type="button" @click="emit('toast', '已打开今日调课与代课看板')">查看今日看板 <ArrowUpRight :size="13" aria-hidden="true" /></button>
              </article>

              <article class="variant-a-surface progress-surface">
                <header class="surface-header"><div><h2>排课进度</h2><p>八年级 2 班 · 当前草稿</p></div><span class="proto-chip blue">进行中</span></header>
                <div class="progress-summary"><strong>86%</strong><span>已完成 118 / 138 节</span></div>
                <div class="progress-track" aria-label="排课进度 86%"><span /></div>
                <div class="progress-rows"><div><span>已锁定</span><strong>6 节</strong></div><div><span>待排课程</span><strong class="warning-text">3 节</strong></div><div><span>冲突提醒</span><strong class="danger-text">1 条</strong></div></div>
                <button class="proto-button primary small" type="button" @click="emit('navigate', 'workbench')">继续处理</button>
              </article>
            </div>

            <article class="variant-a-surface shortcut-surface">
              <header class="surface-header"><div><h2>快捷入口</h2><p>从常用工作开始</p></div><Plus :size="17" class="surface-header-icon" aria-hidden="true" /></header>
              <div class="shortcut-grid">
                <button v-for="shortcut in shortcutItems" :key="shortcut.label" class="shortcut-row" type="button" @click="clickShortcut(shortcut.view)">
                  <span class="shortcut-icon" :class="`tone-${shortcut.tone}`"><ArrowUpRight :size="15" /></span>
                  <span><strong>{{ shortcut.label }}</strong><small>{{ shortcut.detail }}</small></span>
                  <ChevronDown :size="14" class="shortcut-arrow" aria-hidden="true" />
                </button>
              </div>
            </article>
          </template>

          <div v-else-if="statusMode === 'loading'" class="variant-a-state-panel is-loading" aria-live="polite"><RefreshCw class="state-spin" :size="22" aria-hidden="true" /><strong>正在读取学期摘要</strong><span>代表性数据很快会出现在当前工作面。</span></div>
          <div v-else-if="statusMode === 'empty'" class="variant-a-state-panel" aria-live="polite"><ClipboardList :size="25" aria-hidden="true" /><strong>尚未创建任何学期数据</strong><span>完成设置向导后，仪表盘会显示真实的学期摘要。</span><button class="proto-button primary small" type="button" @click="emit('toast', '设置向导入口已打开')">前往设置向导</button></div>
          <div v-else-if="statusMode === 'restricted'" class="variant-a-state-panel is-restricted" role="status"><ShieldAlert :size="25" aria-hidden="true" /><strong>当前角色没有排课管理权限</strong><span>可在课表查询中查看已发布课表，但不能访问学校级摘要或发布草稿。</span><button class="proto-button small" type="button" @click="emit('toast', '权限说明已打开')">查看权限说明</button></div>
          <div v-else class="variant-a-state-panel is-error" role="alert"><AlertTriangle :size="25" aria-hidden="true" /><strong>摘要请求失败</strong><span>暂时无法读取学期和今日变动，请稍后重试。</span><button class="proto-button small" type="button" @click="emit('set-status', 'normal')">重试</button></div>
        </section>

        <section v-else class="variant-a-workbench" aria-labelledby="variant-a-workbench-title">
          <div class="variant-a-page-heading workbench-heading">
            <div><p class="eyebrow">排课作业 / 草稿 v3.2</p><h1 id="variant-a-workbench-title">排课工作台</h1><p class="page-description">八年级 2 班 · 6 个工作日 · 实时冲突校验。</p></div>
            <div class="variant-a-heading-actions"><button class="proto-button" type="button" :disabled="statusMode === 'restricted'" @click="emit('toast', '撤销栈为空')">撤销</button><button class="proto-button" type="button" :disabled="statusMode === 'restricted'" @click="emit('toast', '重做栈为空')">重做</button><button class="proto-button primary" type="button" :disabled="statusMode === 'restricted'" @click="emit('open-confirm')">发布草稿</button></div>
          </div>
          <div class="variant-a-workbench-toolbar">
            <label>学期<select class="proto-select"><option>2026—2027 秋季学期</option></select></label>
            <label>班级<select class="proto-select"><option>八年级 2 班</option><option>八年级 3 班</option></select></label>
            <div class="view-switch" role="tablist" aria-label="课表视角"><button v-for="item in ['class', 'teacher', 'room']" :key="item" :class="{ 'is-active': workbenchView === item }" type="button" role="tab" :aria-selected="workbenchView === item" @click="workbenchView = item as 'class' | 'teacher' | 'room'">{{ item === 'class' ? '班级视图' : item === 'teacher' ? '教师视图' : '教室视图' }}</button></div>
            <span class="proto-chip red"><AlertTriangle :size="12" aria-hidden="true" />1 条冲突</span>
            <button class="prototype-icon-button" type="button" aria-label="筛选" title="筛选" @click="emit('toast', '筛选条件已展开')"><SlidersHorizontal :size="17" aria-hidden="true" /></button>
          </div>
          <div class="variant-a-workbench-layout">
            <article class="variant-a-surface timetable-surface">
              <header class="surface-header timetable-surface-header"><div><h2>八年级 2 班课表</h2><p>6 个工作日 · 6 节课时 · 当前班级视角</p></div><div class="surface-header-tags"><span class="proto-chip blue">6 节已锁定</span><span class="proto-chip green">实时校验</span></div></header>
              <PrototypeTimetable :status-mode="statusMode" :selected-course-key="selectedCourseKey" @select="selectCourse" />
              <div v-if="selectedCourseKey" class="course-inspector"><div><span class="eyebrow">已选择课程</span><strong>点击右侧池或其他课位继续调整</strong></div><span class="proto-chip blue">已选 {{ selectedCourseKey }}</span></div>
            </article>
            <aside class="variant-a-surface tray-surface" :class="{ 'is-filtered': trayFilter === 'urgent' }">
              <header class="surface-header"><div><h2>未排课程</h2><p>拖入左侧空课位</p></div><span class="proto-chip blue">剩余 5 节</span></header>
              <div class="tray-tabs" role="tablist"><button :class="{ 'is-active': trayFilter === 'all' }" type="button" role="tab" @click="trayFilter = 'all'">全部 <span>3</span></button><button :class="{ 'is-active': trayFilter === 'urgent' }" type="button" role="tab" @click="trayFilter = 'urgent'">优先 <span>1</span></button></div>
              <div v-if="statusMode === 'empty'" class="tray-empty"><CheckCircle2 :size="22" aria-hidden="true" /><strong>本班课程已全部排入</strong><span>没有待处理项目。</span></div>
              <div v-else class="tray-list">
                <button v-for="course in unscheduledCourses" :key="course.id" class="tray-course" type="button" :disabled="statusMode === 'restricted'" @click="emit('toast', `${course.subject}已加入拖拽选择`)">
                  <span class="tray-course-mark" :class="`tone-${course.tone}`" />
                  <span><strong>{{ course.subject }}</strong><small>{{ course.teacher }} · 剩余 {{ course.remaining }} 节</small></span>
                  <span class="tray-grip" aria-hidden="true">⋮⋮</span>
                </button>
              </div>
              <div class="tray-footer"><Clock3 :size="14" aria-hidden="true" /><span>最近保存 2 分钟前</span></div>
            </aside>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.variant-a-shell { display: grid; grid-template-columns: 228px minmax(0, 1fr); min-height: 100vh; }
.variant-a-sidebar { position: relative; z-index: 20; display: flex; min-height: 100vh; flex-direction: column; border-right: 1px solid var(--proto-line); background: var(--proto-surface); transition: width 150ms ease, transform 150ms ease; }
.variant-a-shell.is-collapsed { grid-template-columns: 64px minmax(0, 1fr); }
.variant-a-shell.is-collapsed .variant-a-sidebar { width: 64px; }
.variant-a-shell.is-collapsed .variant-a-brand { justify-content: center; padding: 14px 8px; }
.variant-a-shell.is-collapsed .variant-a-brand-copy, .variant-a-shell.is-collapsed .variant-a-nav-label, .variant-a-shell.is-collapsed .variant-a-nav-text, .variant-a-shell.is-collapsed .variant-a-nav-badge, .variant-a-shell.is-collapsed .variant-a-school-status div, .variant-a-shell.is-collapsed .variant-a-collapse-button span { display: none; }
.variant-a-shell.is-collapsed .variant-a-nav-item { justify-content: center; padding: 0; }
.variant-a-shell.is-collapsed .variant-a-sidebar-footer { padding: 9px 8px; }
.variant-a-brand { display: flex; min-height: 74px; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--proto-line); }
.variant-a-brand-mark { display: grid; width: 36px; height: 36px; flex: 0 0 auto; place-items: center; border-radius: 7px; background: var(--proto-primary); color: #fff; }
.variant-a-brand-copy { display: grid; min-width: 0; gap: 2px; }
.variant-a-brand-copy strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.variant-a-brand-copy small { color: var(--proto-text-muted); font-size: 10px; white-space: nowrap; }
.variant-a-mobile-close { display: none; margin-left: auto; }
.variant-a-nav { flex: 1; overflow-y: auto; padding: 13px 10px; }
.variant-a-nav-group + .variant-a-nav-group { margin-top: 12px; }
.variant-a-nav-label { margin: 0 8px 6px; color: var(--proto-text-faint); font-size: 10px; letter-spacing: .06em; }
.variant-a-nav-item { display: flex; width: 100%; min-height: 38px; align-items: center; gap: 9px; margin: 2px 0; padding: 0 9px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--proto-text-muted); cursor: pointer; text-align: left; }
.variant-a-nav-item:hover { background: var(--proto-surface-muted); color: var(--proto-primary); }
.variant-a-nav-item.is-active { border-color: #cbdcff; background: var(--proto-blue-soft); color: var(--proto-primary); font-weight: 700; }
.variant-a-nav-icon { display: grid; width: 25px; height: 25px; flex: 0 0 auto; place-items: center; border-radius: 5px; background: var(--proto-surface-muted); }
.variant-a-nav-item.is-active .variant-a-nav-icon { background: var(--proto-primary); color: #fff; }
.variant-a-nav-text { overflow: hidden; flex: 1; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.variant-a-nav-badge { display: inline-grid; min-width: 18px; height: 18px; place-items: center; border-radius: 9px; background: var(--proto-red-soft); color: var(--proto-danger); font-size: 9px; }
.variant-a-sidebar-footer { padding: 12px; border-top: 1px solid var(--proto-line); }
.variant-a-school-status { display: flex; align-items: flex-start; gap: 8px; padding: 10px; border: 1px solid #d9e5f7; border-radius: 6px; background: #f5f8fe; }
.status-dot { width: 7px; height: 7px; margin-top: 4px; flex: 0 0 auto; border-radius: 50%; background: var(--proto-success); box-shadow: 0 0 0 3px #d9f0e3; }
.variant-a-school-status div { display: grid; gap: 3px; min-width: 0; }
.variant-a-school-status strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.variant-a-school-status small { color: var(--proto-text-muted); font-size: 9px; line-height: 1.35; }
.variant-a-collapse-button { display: flex; width: 100%; min-height: 31px; align-items: center; justify-content: center; gap: 7px; margin-top: 8px; border: 0; background: transparent; color: var(--proto-text-muted); cursor: pointer; font-size: 10px; }
.variant-a-collapse-button:hover { color: var(--proto-primary); }
.variant-a-main { display: grid; min-width: 0; min-height: 100vh; grid-template-rows: 68px minmax(0, 1fr); }
.variant-a-topbar { display: flex; min-width: 0; align-items: center; gap: 13px; padding: 0 22px; border-bottom: 1px solid var(--proto-line); background: rgba(255,255,255,.96); }
.variant-a-menu-button { display: none; }
.variant-a-breadcrumb { display: flex; align-items: center; gap: 8px; color: var(--proto-text-muted); font-size: 12px; }
.variant-a-breadcrumb strong { color: var(--proto-text); }
.variant-a-topbar-spacer { flex: 1; }
.variant-a-profile { display: flex; align-items: center; gap: 8px; color: var(--proto-text-muted); }
.variant-a-avatar { display: grid; width: 31px; height: 31px; place-items: center; border-radius: 6px; background: #dce7fb; color: var(--proto-primary); font-size: 12px; font-weight: 800; }
.variant-a-profile-copy { display: grid; gap: 1px; }
.variant-a-profile-copy strong { color: var(--proto-text); font-size: 11px; }
.variant-a-profile-copy small { font-size: 9px; }
.variant-a-content { min-width: 0; overflow: auto; padding: 25px clamp(18px, 3vw, 34px) 86px; }
.variant-a-page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 19px; }
.variant-a-page-heading h1 { margin: 4px 0 0; font-size: clamp(22px, 2.1vw, 28px); letter-spacing: -.01em; }
.eyebrow { margin: 0; color: var(--proto-primary); font-size: 10px; font-weight: 800; letter-spacing: .07em; }
.page-description { max-width: 620px; margin: 7px 0 0; color: var(--proto-text-muted); font-size: 12px; line-height: 1.55; }
.variant-a-heading-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }
.variant-a-semester-banner { display: flex; min-height: 62px; align-items: center; gap: 11px; margin-bottom: 13px; padding: 11px 14px; border: 1px solid #cbdcff; border-radius: var(--proto-radius); background: var(--proto-surface-blue); }
.semester-banner-icon { display: grid; width: 31px; height: 31px; flex: 0 0 auto; place-items: center; border-radius: 6px; background: #d9e6ff; color: var(--proto-primary); }
.semester-banner-copy { display: grid; min-width: 0; flex: 1; gap: 3px; }
.semester-banner-copy strong { font-size: 12px; }
.semester-banner-copy span { overflow: hidden; color: var(--proto-text-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.variant-a-metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 11px; margin-bottom: 13px; }
.variant-a-metric { display: grid; grid-template-columns: auto 1fr; column-gap: 9px; align-items: center; padding: 13px 14px; border: 1px solid var(--proto-line); border-radius: var(--proto-radius); background: var(--proto-surface); box-shadow: var(--proto-shadow); }
.metric-icon { display: grid; width: 31px; height: 31px; grid-row: span 3; place-items: center; border-radius: 6px; }
.metric-icon.tone-blue, .shortcut-icon.tone-blue { background: var(--proto-blue-soft); color: var(--proto-primary); }
.metric-icon.tone-teal, .shortcut-icon.tone-teal { background: var(--proto-teal-soft); color: #087d79; }
.metric-icon.tone-purple, .shortcut-icon.tone-purple { background: var(--proto-purple-soft); color: #5d47b8; }
.metric-icon.tone-orange, .shortcut-icon.tone-orange { background: var(--proto-orange-soft); color: var(--proto-warning); }
.metric-label { color: var(--proto-text-muted); font-size: 10px; }
.variant-a-metric strong { font-size: 22px; line-height: 1; }
.variant-a-metric small { color: var(--proto-text-faint); font-size: 9px; }
.variant-a-dashboard-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(250px, .65fr); gap: 13px; margin-bottom: 13px; }
.variant-a-surface { min-width: 0; border: 1px solid var(--proto-line); border-radius: var(--proto-radius); background: var(--proto-surface); box-shadow: var(--proto-shadow); }
.surface-header { display: flex; min-height: 61px; align-items: flex-start; gap: 10px; padding: 14px 15px 10px; border-bottom: 1px solid var(--proto-line); }
.surface-header > div:first-child { min-width: 0; flex: 1; }
.surface-header h2 { margin: 0; font-size: 13px; }
.surface-header p { margin: 4px 0 0; color: var(--proto-text-muted); font-size: 10px; }
.surface-header-icon { color: var(--proto-text-faint); }
.substitution-list { padding: 3px 15px 0; }
.substitution-row { display: flex; width: 100%; min-height: 50px; align-items: center; gap: 10px; padding: 8px 0; border: 0; border-bottom: 1px solid #edf0f4; background: transparent; color: var(--proto-text); cursor: pointer; text-align: left; }
.substitution-row:last-child { border-bottom: 0; }
.substitution-row:hover { background: #fbfcfe; }
.substitution-time { width: 47px; flex: 0 0 auto; color: var(--proto-text-muted); font-size: 10px; }
.substitution-main { display: grid; min-width: 0; flex: 1; gap: 3px; }
.substitution-main strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.substitution-main small { color: var(--proto-text-muted); font-size: 10px; }
.substitution-state { flex: 0 0 auto; font-size: 10px; }
.substitution-state.is-pending { color: var(--proto-warning); }
.substitution-state.is-done { color: var(--proto-success); }
.surface-link { margin: 6px 13px 12px; }
.progress-surface { display: flex; min-height: 260px; flex-direction: column; }
.progress-summary { display: flex; align-items: baseline; gap: 8px; padding: 17px 15px 9px; }
.progress-summary strong { color: var(--proto-primary); font-size: 29px; }
.progress-summary span { color: var(--proto-text-muted); font-size: 10px; }
.progress-track { height: 7px; margin: 0 15px 15px; overflow: hidden; border-radius: 5px; background: #e7ecf3; }
.progress-track span { display: block; width: 86%; height: 100%; border-radius: inherit; background: var(--proto-primary); }
.progress-rows { display: grid; gap: 8px; padding: 0 15px; }
.progress-rows div { display: flex; justify-content: space-between; color: var(--proto-text-muted); font-size: 10px; }
.progress-rows strong { color: var(--proto-text); }
.warning-text { color: var(--proto-warning) !important; }
.danger-text { color: var(--proto-danger) !important; }
.progress-surface > .proto-button { align-self: flex-start; margin: auto 15px 15px; }
.shortcut-surface { margin-bottom: 13px; }
.shortcut-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding: 12px 15px 15px; }
.shortcut-row { display: flex; min-width: 0; align-items: center; gap: 9px; padding: 11px 10px; border: 1px solid var(--proto-line); border-radius: 6px; background: var(--proto-surface); color: var(--proto-text); cursor: pointer; text-align: left; }
.shortcut-row:hover { border-color: #cbdcff; background: #fbfcff; }
.shortcut-icon { display: grid; width: 27px; height: 27px; flex: 0 0 auto; place-items: center; border-radius: 5px; }
.shortcut-row > span:nth-child(2) { display: grid; min-width: 0; flex: 1; gap: 3px; }
.shortcut-row strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.shortcut-row small { overflow: hidden; color: var(--proto-text-muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.shortcut-arrow { color: var(--proto-text-faint); transform: rotate(-90deg); }
.variant-a-state-panel { display: grid; min-height: 290px; place-items: center; align-content: center; gap: 9px; padding: 26px; border: 1px dashed var(--proto-line-strong); border-radius: var(--proto-radius); background: var(--proto-surface); color: var(--proto-text-muted); text-align: center; }
.variant-a-state-panel strong { color: var(--proto-text); font-size: 14px; }
.variant-a-state-panel span { font-size: 11px; }
.variant-a-state-panel.is-restricted { border-color: #f0d2ad; color: var(--proto-warning); }
.variant-a-state-panel.is-error { border-color: #efc5c8; color: var(--proto-danger); }
.variant-a-state-panel.is-error strong { color: var(--proto-danger); }
.state-spin { animation: prototype-spin 1s linear infinite; color: var(--proto-primary); }
.variant-a-workbench-toolbar { display: flex; min-height: 54px; align-items: flex-end; gap: 9px; margin-bottom: 12px; padding: 10px 12px; border: 1px solid var(--proto-line); border-radius: var(--proto-radius); background: var(--proto-surface); box-shadow: var(--proto-shadow); }
.variant-a-workbench-toolbar label { display: grid; gap: 4px; color: var(--proto-text-muted); font-size: 10px; }
.variant-a-workbench-toolbar .proto-select { min-width: 156px; }
.view-switch { display: inline-flex; min-height: 36px; align-items: stretch; margin-left: auto; border: 1px solid var(--proto-line-strong); border-radius: 6px; overflow: hidden; }
.view-switch button { min-width: 62px; border: 0; border-right: 1px solid var(--proto-line); background: var(--proto-surface); color: var(--proto-text-muted); cursor: pointer; font-size: 10px; }
.view-switch button:last-child { border-right: 0; }
.view-switch button.is-active { background: var(--proto-blue-soft); color: var(--proto-primary); font-weight: 700; }
.variant-a-workbench-layout { display: grid; grid-template-columns: minmax(0, 1fr) 248px; gap: 13px; align-items: start; }
.timetable-surface { overflow: hidden; }
.timetable-surface-header { align-items: center; }
.surface-header-tags { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 5px; }
.course-inspector { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 12px 15px 15px; padding: 10px 11px; border: 1px solid #cbdcff; border-radius: 6px; background: var(--proto-blue-soft); }
.course-inspector div { display: grid; gap: 3px; }
.course-inspector strong { font-size: 11px; }
.tray-surface { min-height: 310px; }
.tray-tabs { display: flex; gap: 5px; padding: 11px 13px 4px; }
.tray-tabs button { padding: 5px 8px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--proto-text-muted); cursor: pointer; font-size: 10px; }
.tray-tabs button.is-active { border-bottom-color: var(--proto-primary); color: var(--proto-primary); font-weight: 700; }
.tray-tabs span { margin-left: 3px; color: var(--proto-text-faint); }
.tray-list { display: grid; gap: 7px; padding: 5px 13px 14px; }
.tray-course { display: flex; min-width: 0; align-items: center; gap: 8px; padding: 9px 8px; border: 1px solid var(--proto-line); border-radius: 6px; background: var(--proto-surface); color: var(--proto-text); cursor: pointer; text-align: left; }
.tray-course:hover { border-color: #cbdcff; background: #fbfcff; }
.tray-course-mark { width: 4px; height: 32px; flex: 0 0 auto; border-radius: 2px; background: var(--proto-primary); }
.tray-course-mark.tone-teal { background: #12a8a0; }
.tray-course-mark.tone-orange { background: #e17c12; }
.tray-course-mark.tone-purple { background: #7a5af8; }
.tray-course > span:nth-child(2) { display: grid; min-width: 0; flex: 1; gap: 3px; }
.tray-course strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.tray-course small { overflow: hidden; color: var(--proto-text-muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.tray-grip { color: var(--proto-text-faint); font-size: 15px; letter-spacing: -3px; transform: rotate(90deg); }
.tray-empty { display: grid; min-height: 180px; place-items: center; align-content: center; gap: 7px; padding: 18px; color: var(--proto-success); text-align: center; }
.tray-empty strong { color: var(--proto-text); font-size: 12px; }
.tray-empty span { color: var(--proto-text-muted); font-size: 10px; }
.tray-footer { display: flex; align-items: center; gap: 6px; margin: auto 13px 13px; padding-top: 10px; border-top: 1px solid var(--proto-line); color: var(--proto-text-faint); font-size: 9px; }
.variant-a-scrim { position: fixed; z-index: 15; inset: 0; background: rgba(18, 31, 50, .36); }

@media (max-width: 1100px) {
  .variant-a-page-heading { align-items: flex-start; flex-direction: column; }
  .variant-a-heading-actions { justify-content: flex-start; }
  .variant-a-dashboard-grid { grid-template-columns: 1fr; }
}

@media (max-width: 820px) {
  .variant-a-workbench-toolbar { align-items: stretch; flex-wrap: wrap; }
  .variant-a-workbench-toolbar .view-switch { margin-left: 0; }
  .variant-a-workbench-layout { grid-template-columns: 1fr; }
  .tray-surface { min-height: 0; }
  .tray-footer { margin-top: 0; }
  .shortcut-grid { grid-template-columns: 1fr; }
}

@media (max-width: 767px) {
  .variant-a-shell, .variant-a-shell.is-collapsed { display: block; }
  .variant-a-sidebar, .variant-a-shell.is-collapsed .variant-a-sidebar { position: fixed; top: 0; bottom: 0; left: 0; width: 228px; min-height: 100vh; pointer-events: none; transform: translateX(-102%); box-shadow: var(--proto-shadow-strong); }
  .variant-a-shell.is-collapsed .variant-a-sidebar.is-mobile-open, .variant-a-sidebar.is-mobile-open { pointer-events: auto; transform: translateX(0); }
  .variant-a-shell.is-collapsed .variant-a-brand { justify-content: flex-start; padding: 14px 16px; }
  .variant-a-shell.is-collapsed .variant-a-brand-copy, .variant-a-shell.is-collapsed .variant-a-nav-label, .variant-a-shell.is-collapsed .variant-a-nav-text, .variant-a-shell.is-collapsed .variant-a-nav-badge, .variant-a-shell.is-collapsed .variant-a-school-status div, .variant-a-shell.is-collapsed .variant-a-collapse-button span { display: initial; }
  .variant-a-shell.is-collapsed .variant-a-nav-item { justify-content: flex-start; padding: 0 9px; }
  .variant-a-shell.is-collapsed .variant-a-sidebar-footer { padding: 12px; }
  .variant-a-mobile-close { display: inline-grid; }
  .variant-a-main { min-height: 100vh; grid-template-rows: 62px minmax(0, 1fr); }
  .variant-a-topbar { gap: 9px; padding: 0 12px; }
  .variant-a-menu-button { display: inline-grid; }
  .variant-a-breadcrumb { font-size: 11px; }
  .variant-a-breadcrumb span:first-child, .variant-a-profile-copy, .variant-a-profile > svg { display: none; }
  .variant-a-content { padding: 18px 12px 76px; }
  .variant-a-heading-actions { width: 100%; }
  .variant-a-heading-actions .proto-button { flex: 1; }
  .variant-a-semester-banner { align-items: flex-start; flex-wrap: wrap; }
  .semester-banner-copy { min-width: calc(100% - 45px); }
  .variant-a-semester-banner > .proto-chip { margin-left: 42px; }
  .variant-a-semester-banner > .proto-button { margin-left: auto; }
  .variant-a-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .variant-a-workbench-toolbar label { min-width: calc(50% - 5px); flex: 1; }
  .variant-a-workbench-toolbar .proto-select { min-width: 0; width: 100%; }
  .variant-a-workbench-toolbar > .proto-chip { margin-top: 7px; }
}

@media (max-width: 400px) {
  .variant-a-page-heading h1 { font-size: 23px; }
  .variant-a-metric { padding: 10px; }
  .variant-a-metric strong { font-size: 19px; }
  .variant-a-metric small { font-size: 8px; }
  .variant-a-semester-banner > .proto-chip { margin-left: 0; }
  .variant-a-semester-banner > .proto-button { margin-left: 0; }
  .variant-a-topbar .prototype-state-control { display: none; }
}
</style>
