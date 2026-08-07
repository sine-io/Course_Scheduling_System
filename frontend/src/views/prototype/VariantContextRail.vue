<script setup lang="ts">
import {
  AlertTriangle,
  Bell,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Command,
  Inbox,
  LayoutDashboard,
  Menu,
  PanelRight,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Users,
} from '@lucide/vue'
import { ref } from 'vue'
import PrototypeIconButton from './PrototypeIconButton.vue'
import PrototypeStateControl from './PrototypeStateControl.vue'
import PrototypeTimetable from './PrototypeTimetable.vue'
import type { CourseCell, NavItem, StatusMode, VariantProps, ViewKey } from './prototypeData'
import { navGroups, metrics, substitutionChanges, unscheduledCourses } from './prototypeData'

// THROWAWAY PROTOTYPE — Variant B: icon rail plus contextual work panels.

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

const queueTab = ref<'today' | 'pending'>('today')
const workbenchView = ref<'class' | 'teacher' | 'room'>('class')
const inspectorOpen = ref(true)
const activeRailKey = ref('dashboard')

function chooseNav(item: NavItem) {
  activeRailKey.value = item.key
  if (item.view) emit('navigate', item.view)
  else emit('toast', `“${item.label}”在生产页面中保持原有路由（本原型未展开）`)
}

function selectCourse(course: CourseCell) {
  inspectorOpen.value = true
  emit('select-course', course)
}

function railActive(key: string, view?: ViewKey) {
  return view ? props.activeView === view : activeRailKey.value === key
}
</script>

<template>
  <div class="variant-b-shell" :class="{ 'is-compact': collapsed, 'is-drawer-open': drawerOpen }">
    <aside class="variant-b-icon-rail" aria-label="模块导航">
      <button class="variant-b-rail-mark" type="button" aria-label="返回仪表盘" title="返回仪表盘" @click="emit('navigate', 'dashboard')"><CalendarDays :size="19" aria-hidden="true" /></button>
      <div class="variant-b-rail-items">
        <PrototypeIconButton :icon="LayoutDashboard" label="仪表盘" :active="railActive('dashboard', 'dashboard')" @click="chooseNav({ key: 'dashboard', label: '仪表盘', icon: LayoutDashboard, view: 'dashboard' })" />
        <PrototypeIconButton :icon="Command" label="排课工作台" :active="railActive('workbench', 'workbench')" @click="chooseNav({ key: 'workbench', label: '排课工作台', icon: Command, view: 'workbench' })" />
        <PrototypeIconButton :icon="Users" label="基础数据" :active="railActive('basedata')" @click="chooseNav({ key: 'basedata', label: '基础数据', icon: Users })" />
        <PrototypeIconButton :icon="Bell" label="调课与代课" :active="railActive('substitutions')" @click="chooseNav({ key: 'substitutions', label: '调课与代课', icon: Bell })" />
      </div>
      <div class="variant-b-rail-bottom"><PrototypeIconButton :icon="SlidersHorizontal" label="系统设置" @click="emit('toast', '系统设置入口已打开')" /><span class="variant-b-rail-divider" /><span class="variant-b-rail-avatar">张</span></div>
    </aside>

    <div v-if="drawerOpen" class="variant-b-scrim" aria-hidden="true" @click="emit('close-drawer')" />
    <aside class="variant-b-drawer" :class="{ 'is-open': drawerOpen }" aria-label="完整导航">
      <div class="variant-b-drawer-head"><div><strong>教务排课</strong><small>排课 · 调课 · 代课</small></div><PrototypeIconButton :icon="PanelRight" label="关闭导航" compact @click="emit('close-drawer')" /></div>
      <div class="variant-b-drawer-body">
        <section v-for="group in navGroups" :key="group.label" class="variant-b-drawer-group"><p>{{ group.label }}</p><button v-for="item in group.items" :key="item.key" type="button" :class="{ 'is-active': railActive(item.key, item.view) }" @click="chooseNav(item)"><component :is="item.icon" :size="16" /><span>{{ item.label }}</span><b v-if="item.badge">{{ item.badge }}</b></button></section>
      </div>
      <button class="variant-b-drawer-collapse" type="button" @click="emit('toggle-collapse')">{{ collapsed ? '恢复图标轨道' : '保持图标轨道' }}<ChevronRight :size="14" aria-hidden="true" /></button>
    </aside>

    <main class="variant-b-main">
      <header class="variant-b-topbar">
        <PrototypeIconButton :icon="Menu" label="打开导航" class="variant-b-menu" @click="emit('toggle-drawer')" />
        <div class="variant-b-topbar-title"><span>学校排课、调课与代课管理系统</span><strong>{{ activeView === 'dashboard' ? '仪表盘' : '排课工作台' }}</strong></div>
        <div class="variant-b-context-tabs" role="tablist"><button type="button" :class="{ 'is-active': activeView === 'dashboard' }" role="tab" :aria-selected="activeView === 'dashboard'" @click="emit('navigate', 'dashboard')">运行概览</button><button type="button" :class="{ 'is-active': activeView === 'workbench' }" role="tab" :aria-selected="activeView === 'workbench'" @click="emit('navigate', 'workbench')">排课作业</button></div>
        <div class="variant-b-topbar-spacer" />
        <PrototypeStateControl :model-value="statusMode" @update:model-value="emit('set-status', $event)" />
        <PrototypeIconButton :icon="Bell" label="通知" @click="emit('toast', '有 2 条待确认的调课通知')" />
        <span class="variant-b-topbar-avatar">张</span>
      </header>

      <section v-if="activeView === 'dashboard'" class="variant-b-dashboard" aria-labelledby="variant-b-dashboard-title">
        <header class="variant-b-view-heading"><div><span class="eyebrow">MONDAY · 2026.09.14</span><h1 id="variant-b-dashboard-title">今天，先处理这些</h1><p>当前学期的关键状态和需要人工确认的变动。</p></div><button class="proto-button primary" type="button" @click="emit('navigate', 'workbench')"><Command :size="15" aria-hidden="true" />打开工作台</button></header>
        <div class="variant-b-dashboard-grid">
          <article class="variant-b-queue-panel">
            <div class="b-panel-heading"><div><span class="panel-kicker">待处理队列</span><h2>调课与代课</h2></div><span class="proto-chip orange">4 项</span></div>
            <div class="b-queue-tabs" role="tablist"><button type="button" :class="{ 'is-active': queueTab === 'today' }" role="tab" @click="queueTab = 'today'">今日变动</button><button type="button" :class="{ 'is-active': queueTab === 'pending' }" role="tab" @click="queueTab = 'pending'">待确认 <b>2</b></button></div>
            <div v-if="statusMode === 'normal'" class="b-queue-list">
              <button v-for="change in substitutionChanges.slice(queueTab === 'pending' ? 1 : 0)" :key="change.id" class="b-queue-item" type="button" @click="emit('toast', `${change.className}的处理详情已打开`)"><span class="b-queue-time">{{ change.time }}</span><span class="b-queue-line" /><span class="b-queue-copy"><strong>{{ change.className }} · {{ change.subject }}</strong><small>{{ change.from }} <span aria-hidden="true">→</span> {{ change.to }}</small></span><span class="substitution-state" :class="change.state === '待确认' ? 'is-pending' : 'is-done'">{{ change.state }}</span></button>
            </div>
            <div v-else-if="statusMode === 'loading'" class="b-panel-state is-loading"><Search class="state-spin" :size="20" /><span>队列读取中</span></div>
            <div v-else-if="statusMode === 'empty'" class="b-panel-state"><CheckCircle2 :size="21" /><strong>今日无变动</strong><span>所有安排都已确认。</span></div>
            <div v-else-if="statusMode === 'restricted'" class="b-panel-state is-restricted" role="status"><ShieldAlert :size="21" /><strong>队列仅限排课管理员</strong><span>可在课表查询中查看已发布课表。</span></div>
            <div v-else class="b-panel-state is-error" role="alert"><CircleAlert :size="21" /><strong>队列暂不可用</strong><span>请稍后重试。</span></div>
          </article>

          <div class="variant-b-center-column">
            <article class="variant-b-status-strip"><div><span class="panel-kicker">当前学期</span><strong>2026—2027 秋季学期</strong></div><span class="proto-chip green"><CheckCircle2 :size="12" />配置完整</span><button class="proto-button ghost small" type="button" @click="emit('toast', '学期详情已打开')">查看详情 <ChevronRight :size="13" /></button></article>
            <div v-if="statusMode === 'normal'" class="variant-b-metrics">
              <article v-for="metric in metrics" :key="metric.label" class="variant-b-metric"><span class="b-metric-label">{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.detail }}</small></article>
            </div>
            <div v-else class="variant-b-state-block" :class="`is-${statusMode}`" :role="statusMode === 'error' ? 'alert' : 'status'"><Search v-if="statusMode === 'loading'" class="state-spin" :size="22" /><Inbox v-else-if="statusMode === 'empty'" :size="22" /><ShieldAlert v-else-if="statusMode === 'restricted'" :size="22" /><AlertTriangle v-else :size="22" /><strong>{{ statusMode === 'loading' ? '数据读取中' : statusMode === 'empty' ? '尚无学期摘要' : statusMode === 'restricted' ? '学校级摘要访问受限' : '摘要请求失败' }}</strong><span>{{ statusMode === 'error' ? '后端服务没有响应。' : statusMode === 'restricted' ? '当前角色可查看已发布课表，但不能访问排课摘要。' : '这里会展示真实 API 返回的四项摘要。' }}</span></div>
            <article class="variant-b-progress"><div class="b-panel-heading"><div><span class="panel-kicker">排课工作量</span><h2>八年级 2 班</h2></div><strong>86%</strong></div><div class="progress-track"><span /></div><div class="b-progress-meta"><span>已排 118 节</span><span>待排 3 节</span><span class="danger-text">冲突 1 条</span></div></article>
          </div>

          <aside class="variant-b-command-panel"><div class="b-panel-heading"><div><span class="panel-kicker">快捷动作</span><h2>下一步</h2></div><Plus :size="17" aria-hidden="true" /></div><button class="b-command primary-command" type="button" @click="emit('navigate', 'workbench')"><span><Command :size="16" /><strong>继续排课</strong><small>处理 3 节未排课程</small></span><ChevronRight :size="15" /></button><button class="b-command" type="button" :disabled="statusMode === 'restricted'" @click="emit('open-confirm')"><span><ShieldCheck :size="16" /><strong>检查发布</strong><small>1 条冲突待确认</small></span><ChevronRight :size="15" /></button><button class="b-command" type="button" @click="emit('toast', '教学任务入口已打开')"><span><Users :size="16" /><strong>教学任务</strong><small>查看教师与班级分配</small></span><ChevronRight :size="15" /></button><div class="b-permission-note"><ShieldCheck :size="14" /><span>当前身份：{{ statusMode === 'restricted' ? '只读教务用户' : '排课管理员' }}<br>{{ statusMode === 'restricted' ? '发布与编辑操作已禁用。' : '正式发布仍需人工确认。' }}</span></div></aside>
        </div>
      </section>

      <section v-else class="variant-b-workbench" aria-labelledby="variant-b-workbench-title">
        <header class="variant-b-view-heading"><div><span class="eyebrow">排课作业 / 草稿 v3.2</span><h1 id="variant-b-workbench-title">排课工作台</h1><p>八年级 2 班 · 课程池 · 冲突检查器。</p></div><div class="b-heading-actions"><button class="proto-button" type="button" @click="emit('toast', '筛选条件已展开')"><SlidersHorizontal :size="15" />筛选</button><button class="proto-button primary" type="button" :disabled="statusMode === 'restricted'" @click="emit('open-confirm')">发布草稿</button></div></header>
        <div class="variant-b-workbench-toolbar"><label>班级<select class="proto-select"><option>八年级 2 班</option><option>八年级 3 班</option></select></label><div class="view-switch" role="tablist"><button v-for="item in ['class', 'teacher', 'room']" :key="item" type="button" role="tab" :aria-selected="workbenchView === item" :class="{ 'is-active': workbenchView === item }" @click="workbenchView = item as 'class' | 'teacher' | 'room'">{{ item === 'class' ? '班级' : item === 'teacher' ? '教师' : '教室' }}</button></div><span class="proto-chip red"><AlertTriangle :size="12" />1 条冲突</span><span class="proto-chip blue">6 节已锁定</span></div>
        <div class="variant-b-workbench-layout">
          <aside class="variant-b-pool-panel"><div class="b-panel-heading"><div><span class="panel-kicker">课程池</span><h2>未排课程</h2></div><span class="proto-chip blue">5 节</span></div><div class="pool-search"><Search :size="14" /><input aria-label="搜索未排课程" placeholder="搜索课程"></div><div class="b-pool-list"><button v-for="course in unscheduledCourses" :key="course.id" class="b-pool-item" type="button" :disabled="statusMode === 'restricted'" @click="emit('toast', `${course.subject}已加入拖拽选择`)"><span class="pool-color" :class="`tone-${course.tone}`" /><span><strong>{{ course.subject }}</strong><small>{{ course.teacher }}</small></span><b>{{ course.remaining }}</b></button></div><button class="proto-button secondary small pool-add" type="button" :disabled="statusMode === 'restricted'" @click="emit('toast', '课程筛选器已打开')"><Plus :size="13" />添加筛选</button></aside>
          <article class="variant-b-timetable-panel"><div class="b-panel-heading timetable-panel-heading"><div><span class="panel-kicker">班级视图</span><h2>八年级 2 班课表</h2></div><div><span class="proto-chip green">实时校验</span><PrototypeIconButton :icon="PanelRight" label="切换详情栏" compact :active="inspectorOpen" @click="inspectorOpen = !inspectorOpen" /></div></div><PrototypeTimetable compact :status-mode="statusMode" :selected-course-key="selectedCourseKey" @select="selectCourse" /></article>
          <aside v-if="inspectorOpen" class="variant-b-inspector"><div class="b-panel-heading"><div><span class="panel-kicker">检查器</span><h2>{{ selectedCourseKey ? '课程详情' : '排课提示' }}</h2></div><PrototypeIconButton :icon="PanelRight" label="收起详情栏" compact @click="inspectorOpen = false" /></div><template v-if="selectedCourseKey"><div class="inspector-course"><span class="inspector-course-tone" /><strong>{{ selectedCourseKey }}</strong><span>八年级 2 班 · 周三第 3 节</span></div><dl class="inspector-details"><div><dt>任课教师</dt><dd>张老师</dd></div><div><dt>教室 / 场地</dt><dd>A201</dd></div><div><dt>状态</dt><dd><span class="proto-chip red">冲突待处理</span></dd></div></dl><button class="proto-button primary small" type="button" @click="emit('toast', '替代节次已展开')">查看可用节次</button></template><template v-else><div class="inspector-alert"><AlertTriangle :size="18" /><strong>有 1 条冲突</strong><p>周三第 3 节数学与张老师的教师时间规则冲突。</p><button class="proto-button secondary small" type="button" @click="emit('toast', '冲突说明已展开')">查看冲突说明</button></div><div class="inspector-checks"><div><CheckCircle2 :size="14" /><span>班级不重复</span></div><div><CheckCircle2 :size="14" /><span>场地不重复</span></div><div class="is-warning"><AlertTriangle :size="14" /><span>教师时间规则</span></div></div></template></aside>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.variant-b-shell { display: grid; min-height: 100vh; grid-template-columns: 64px minmax(0, 1fr); }
.variant-b-shell.is-compact { grid-template-columns: 52px minmax(0, 1fr); }
.variant-b-icon-rail { position: relative; z-index: 30; display: flex; min-height: 100vh; flex-direction: column; align-items: center; border-right: 1px solid var(--proto-line); background: #17253b; }
.variant-b-rail-mark { display: grid; width: 34px; height: 34px; margin: 15px 0 20px; place-items: center; border: 0; border-radius: 6px; background: var(--proto-primary); color: #fff; cursor: pointer; }
.variant-b-rail-items { display: grid; gap: 8px; }
.variant-b-icon-rail .prototype-icon-button { color: #aebcd1; }
.variant-b-icon-rail .prototype-icon-button:hover, .variant-b-icon-rail .prototype-icon-button.is-active { border-color: #426caa; background: #263f63; color: #fff; }
.variant-b-rail-bottom { display: grid; justify-items: center; gap: 12px; margin-top: auto; padding: 14px 0 16px; }
.variant-b-rail-divider { width: 24px; height: 1px; background: #334762; }
.variant-b-rail-avatar, .variant-b-topbar-avatar { display: grid; place-items: center; border-radius: 6px; background: #dce7fb; color: var(--proto-primary); font-size: 11px; font-weight: 800; }
.variant-b-rail-avatar { width: 29px; height: 29px; }
.variant-b-main { display: grid; min-width: 0; min-height: 100vh; grid-template-rows: 68px minmax(0, 1fr); }
.variant-b-topbar { display: flex; min-width: 0; align-items: center; gap: 14px; padding: 0 24px; border-bottom: 1px solid var(--proto-line); background: var(--proto-surface); }
.variant-b-menu { display: none; }
.variant-b-topbar-title { display: grid; gap: 2px; min-width: 205px; }
.variant-b-topbar-title span { color: var(--proto-text-muted); font-size: 10px; }
.variant-b-topbar-title strong { font-size: 15px; }
.variant-b-context-tabs { display: flex; align-self: stretch; gap: 15px; }
.variant-b-context-tabs button { position: relative; padding: 0 2px; border: 0; background: transparent; color: var(--proto-text-muted); cursor: pointer; font-size: 12px; }
.variant-b-context-tabs button.is-active { color: var(--proto-primary); font-weight: 700; }
.variant-b-context-tabs button.is-active::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; background: var(--proto-primary); content: ''; }
.variant-b-topbar-spacer { flex: 1; }
.variant-b-topbar-avatar { width: 31px; height: 31px; }
.variant-b-drawer { position: fixed; z-index: 25; top: 0; bottom: 0; left: 64px; display: flex; width: 246px; flex-direction: column; pointer-events: none; transform: translateX(-120%); border-right: 1px solid var(--proto-line); background: var(--proto-surface); box-shadow: var(--proto-shadow-strong); transition: transform 150ms ease; }
.variant-b-drawer.is-open { pointer-events: auto; transform: translateX(0); }
.variant-b-drawer-head { display: flex; align-items: center; justify-content: space-between; padding: 18px 15px; border-bottom: 1px solid var(--proto-line); }
.variant-b-drawer-head div { display: grid; gap: 3px; }
.variant-b-drawer-head strong { font-size: 14px; }
.variant-b-drawer-head small { color: var(--proto-text-muted); font-size: 10px; }
.variant-b-drawer-body { flex: 1; overflow-y: auto; padding: 14px 10px; }
.variant-b-drawer-group + .variant-b-drawer-group { margin-top: 14px; }
.variant-b-drawer-group p { margin: 0 8px 6px; color: var(--proto-text-faint); font-size: 10px; }
.variant-b-drawer-group button { display: flex; width: 100%; min-height: 36px; align-items: center; gap: 9px; padding: 0 9px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--proto-text-muted); cursor: pointer; font-size: 11px; text-align: left; }
.variant-b-drawer-group button:hover, .variant-b-drawer-group button.is-active { border-color: #cbdcff; background: var(--proto-blue-soft); color: var(--proto-primary); }
.variant-b-drawer-group button span { flex: 1; }
.variant-b-drawer-group button b { min-width: 17px; border-radius: 9px; background: var(--proto-red-soft); color: var(--proto-danger); font-size: 9px; text-align: center; }
.variant-b-drawer-collapse { display: flex; align-items: center; justify-content: space-between; margin: 10px; padding: 10px; border: 1px solid var(--proto-line); border-radius: 6px; background: var(--proto-surface-muted); color: var(--proto-text-muted); cursor: pointer; font-size: 10px; }
.variant-b-scrim { position: fixed; z-index: 22; inset: 0; background: rgba(18, 31, 50, .36); }
.variant-b-dashboard, .variant-b-workbench { min-width: 0; overflow: visible; padding: 27px clamp(18px, 3vw, 36px) 86px; }
.variant-b-view-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.variant-b-view-heading h1 { margin: 5px 0 0; font-size: clamp(22px, 2.1vw, 28px); }
.variant-b-view-heading p { margin: 6px 0 0; color: var(--proto-text-muted); font-size: 12px; }
.variant-b-dashboard-grid { display: grid; grid-template-columns: minmax(220px, .75fr) minmax(300px, 1.35fr) minmax(210px, .65fr); gap: 12px; align-items: start; }
.variant-b-queue-panel, .variant-b-command-panel, .variant-b-center-column > article, .variant-b-pool-panel, .variant-b-timetable-panel, .variant-b-inspector { min-width: 0; border: 1px solid var(--proto-line); background: var(--proto-surface); box-shadow: var(--proto-shadow); }
.variant-b-queue-panel, .variant-b-command-panel { min-height: 442px; border-radius: var(--proto-radius); }
.b-panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding: 15px 14px 11px; border-bottom: 1px solid var(--proto-line); }
.b-panel-heading h2 { margin: 4px 0 0; font-size: 13px; }
.panel-kicker { color: var(--proto-text-faint); font-size: 9px; letter-spacing: .06em; text-transform: uppercase; }
.b-queue-tabs { display: flex; gap: 10px; padding: 11px 14px 5px; border-bottom: 1px solid #edf0f4; }
.b-queue-tabs button { position: relative; padding: 0 0 8px; border: 0; background: transparent; color: var(--proto-text-muted); cursor: pointer; font-size: 10px; }
.b-queue-tabs button.is-active { color: var(--proto-primary); font-weight: 700; }
.b-queue-tabs button.is-active::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; background: var(--proto-primary); content: ''; }
.b-queue-tabs b { display: inline-grid; min-width: 16px; height: 16px; place-items: center; margin-left: 3px; border-radius: 8px; background: var(--proto-red-soft); color: var(--proto-danger); font-size: 8px; }
.b-queue-list { padding: 5px 14px 13px; }
.b-queue-item { display: grid; width: 100%; grid-template-columns: 42px 7px minmax(0, 1fr) auto; align-items: center; gap: 7px; min-height: 67px; padding: 7px 0; border: 0; border-bottom: 1px solid #edf0f4; background: transparent; color: var(--proto-text); cursor: pointer; text-align: left; }
.b-queue-item:last-child { border-bottom: 0; }
.b-queue-item:hover { background: #fbfcfe; }
.b-queue-time { color: var(--proto-text-muted); font-size: 10px; }
.b-queue-line { width: 1px; height: 39px; justify-self: center; background: #bcd0f2; }
.b-queue-copy { display: grid; min-width: 0; gap: 4px; }
.b-queue-copy strong { overflow: hidden; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.b-queue-copy small { color: var(--proto-text-muted); font-size: 9px; }
.b-queue-item .substitution-state { font-size: 9px; }
.b-panel-state { display: grid; min-height: 315px; place-items: center; align-content: center; gap: 7px; padding: 20px; color: var(--proto-success); text-align: center; }
.b-panel-state.is-restricted { color: var(--proto-warning); }
.b-panel-state strong { color: var(--proto-text); font-size: 12px; }
.b-panel-state span { color: var(--proto-text-muted); font-size: 10px; }
.b-panel-state.is-loading { color: var(--proto-primary); }
.b-panel-state.is-error { color: var(--proto-danger); }
.b-panel-state.is-error strong { color: var(--proto-danger); }
.variant-b-center-column { display: grid; gap: 12px; }
.variant-b-status-strip { display: flex; min-height: 70px; align-items: center; gap: 10px; padding: 14px; border-radius: var(--proto-radius); }
.variant-b-status-strip > div:first-child { display: grid; min-width: 0; flex: 1; gap: 4px; }
.variant-b-status-strip strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.variant-b-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.variant-b-metric { display: grid; min-height: 105px; align-content: center; gap: 4px; padding: 12px; border-radius: var(--proto-radius); }
.variant-b-metric:nth-child(1) { background: var(--proto-blue-soft); }
.variant-b-metric:nth-child(2) { background: var(--proto-teal-soft); }
.variant-b-metric:nth-child(3) { background: var(--proto-purple-soft); }
.variant-b-metric:nth-child(4) { background: var(--proto-orange-soft); }
.b-metric-label { color: var(--proto-text-muted); font-size: 10px; }
.variant-b-metric strong { font-size: 24px; line-height: 1; }
.variant-b-metric small { overflow: hidden; color: var(--proto-text-muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.variant-b-state-block { display: grid; min-height: 105px; place-items: center; align-content: center; gap: 5px; border: 1px dashed var(--proto-line-strong); border-radius: var(--proto-radius); color: var(--proto-text-muted); text-align: center; }
.variant-b-state-block strong { font-size: 12px; }
.variant-b-state-block span { font-size: 10px; }
.variant-b-state-block.is-error { border-color: #efc5c8; color: var(--proto-danger); }
.variant-b-state-block.is-restricted { border-color: #f0d2ad; color: var(--proto-warning); }
.variant-b-progress { min-height: 134px; border-radius: var(--proto-radius); }
.variant-b-progress .b-panel-heading { align-items: center; }
.variant-b-progress .b-panel-heading > strong { color: var(--proto-primary); font-size: 22px; }
.variant-b-progress .progress-track { margin: 14px 14px 9px; }
.b-progress-meta { display: flex; justify-content: space-between; padding: 0 14px 14px; color: var(--proto-text-muted); font-size: 9px; }
.variant-b-command-panel { padding-bottom: 10px; }
.b-command { display: flex; width: calc(100% - 24px); min-height: 64px; align-items: center; justify-content: space-between; gap: 8px; margin: 8px 12px 0; padding: 10px; border: 1px solid var(--proto-line); border-radius: 6px; background: var(--proto-surface); color: var(--proto-text); cursor: pointer; text-align: left; }
.b-command:hover { border-color: #cbdcff; background: #fbfcff; }
.b-command > span { display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 8px; align-items: center; min-width: 0; }
.b-command > span > svg { grid-row: span 2; color: var(--proto-primary); }
.b-command strong, .b-command small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.b-command strong { font-size: 11px; }
.b-command small { margin-top: 3px; color: var(--proto-text-muted); font-size: 9px; }
.b-command.primary-command { border-color: #b9cef8; background: var(--proto-blue-soft); }
.b-permission-note { display: flex; align-items: flex-start; gap: 7px; margin: 14px 12px 0; padding: 10px; border-top: 1px solid var(--proto-line); color: var(--proto-text-muted); font-size: 9px; line-height: 1.5; }
.b-permission-note svg { flex: 0 0 auto; color: var(--proto-success); }
.variant-b-workbench-layout { display: grid; grid-template-columns: 206px minmax(0, 1fr) 214px; gap: 10px; align-items: start; }
.variant-b-pool-panel, .variant-b-timetable-panel, .variant-b-inspector { min-height: 440px; border-radius: var(--proto-radius); }
.pool-search { display: flex; height: 31px; align-items: center; gap: 7px; margin: 11px 12px 7px; padding: 0 8px; border: 1px solid var(--proto-line); border-radius: 5px; color: var(--proto-text-faint); }
.pool-search input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--proto-text); font-size: 10px; }
.b-pool-list { display: grid; gap: 6px; padding: 4px 12px 11px; }
.b-pool-item { display: grid; grid-template-columns: 4px minmax(0, 1fr) auto; align-items: center; gap: 7px; padding: 9px 7px; border: 1px solid var(--proto-line); border-radius: 5px; background: var(--proto-surface); color: var(--proto-text); cursor: pointer; text-align: left; }
.b-pool-item:hover { border-color: #cbdcff; }
.pool-color { width: 4px; height: 31px; border-radius: 2px; background: var(--proto-primary); }
.pool-color.tone-teal { background: #12a8a0; }
.pool-color.tone-orange { background: #e17c12; }
.pool-color.tone-purple { background: #7a5af8; }
.b-pool-item > span:nth-child(2) { display: grid; min-width: 0; gap: 3px; }
.b-pool-item strong, .b-pool-item small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.b-pool-item strong { font-size: 10px; }
.b-pool-item small { color: var(--proto-text-muted); font-size: 9px; }
.b-pool-item b { display: grid; min-width: 19px; height: 19px; place-items: center; border-radius: 10px; background: var(--proto-blue-soft); color: var(--proto-primary); font-size: 9px; }
.pool-add { margin: 0 12px; }
.variant-b-timetable-panel { overflow: hidden; }
.timetable-panel-heading { align-items: center; }
.timetable-panel-heading > div:last-child { display: flex; align-items: center; gap: 5px; }
.variant-b-inspector { overflow: hidden; }
.inspector-course { display: grid; gap: 5px; padding: 15px 14px; border-bottom: 1px solid var(--proto-line); }
.inspector-course-tone { width: 28px; height: 5px; border-radius: 3px; background: var(--proto-primary); }
.inspector-course strong { font-size: 14px; }
.inspector-course span:last-child { color: var(--proto-text-muted); font-size: 10px; }
.inspector-details { display: grid; gap: 10px; margin: 0; padding: 14px; }
.inspector-details div { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.inspector-details dt { color: var(--proto-text-muted); font-size: 10px; }
.inspector-details dd { margin: 0; font-size: 10px; font-weight: 700; }
.variant-b-inspector > .proto-button { margin: 0 14px; }
.inspector-alert { display: grid; gap: 7px; padding: 17px 14px; color: var(--proto-danger); }
.inspector-alert strong { font-size: 12px; }
.inspector-alert p { margin: 0; color: var(--proto-text-muted); font-size: 10px; line-height: 1.55; }
.inspector-checks { display: grid; gap: 9px; margin: 7px 14px 14px; padding-top: 13px; border-top: 1px solid var(--proto-line); }
.inspector-checks div { display: flex; align-items: center; gap: 7px; color: var(--proto-success); font-size: 10px; }
.inspector-checks div.is-warning { color: var(--proto-warning); }

@media (max-width: 1180px) {
  .variant-b-dashboard-grid { grid-template-columns: minmax(210px, .7fr) minmax(290px, 1.3fr); }
  .variant-b-command-panel { grid-column: 1 / -1; min-height: 0; display: grid; grid-template-columns: repeat(3, 1fr); align-items: start; padding-bottom: 12px; }
  .variant-b-command-panel .b-panel-heading { grid-column: 1 / -1; }
  .variant-b-command { width: auto; margin: 8px 6px 0; }
  .b-permission-note { grid-column: 1 / -1; margin-top: 12px; }
}

@media (max-width: 930px) {
  .variant-b-workbench-layout { grid-template-columns: 180px minmax(0, 1fr); }
  .variant-b-inspector { grid-column: 1 / -1; min-height: 0; }
  .variant-b-inspector .inspector-checks { display: flex; flex-wrap: wrap; }
}

@media (max-width: 767px) {
  .variant-b-shell, .variant-b-shell.is-compact { display: block; }
  .variant-b-icon-rail { position: fixed; z-index: 20; top: 0; bottom: 0; left: 0; width: 0; min-height: 0; overflow: hidden; border: 0; }
  .variant-b-drawer { left: 0; width: min(290px, 84vw); }
  .variant-b-main { min-height: 100vh; grid-template-rows: 62px minmax(0, 1fr); }
  .variant-b-topbar { gap: 8px; padding: 0 12px; }
  .variant-b-menu { display: inline-grid; }
  .variant-b-topbar-title { min-width: 0; flex: 1; }
  .variant-b-topbar-title span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .variant-b-topbar-title strong { font-size: 13px; }
  .variant-b-context-tabs { display: none; }
  .variant-b-topbar .prototype-state-control { display: none; }
  .variant-b-dashboard, .variant-b-workbench { padding: 19px 12px 76px; }
  .variant-b-view-heading { align-items: flex-start; flex-direction: column; }
  .variant-b-view-heading h1 { font-size: 23px; }
  .variant-b-dashboard-grid { grid-template-columns: 1fr; }
  .variant-b-queue-panel, .variant-b-command-panel { min-height: 0; }
  .variant-b-command-panel { display: block; }
  .variant-b-command-panel .b-panel-heading { display: flex; }
  .variant-b-command { width: calc(100% - 24px); margin: 8px 12px 0; }
  .b-permission-note { margin-top: 14px; }
  .variant-b-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .variant-b-workbench-toolbar { flex-wrap: wrap; }
  .variant-b-workbench-toolbar label { flex: 1; }
  .variant-b-workbench-toolbar .proto-select { min-width: 0; width: 100%; }
  .variant-b-workbench-layout { grid-template-columns: 1fr; }
  .variant-b-pool-panel { min-height: 0; }
  .b-pool-list { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .b-pool-item { min-width: 0; }
  .variant-b-inspector { grid-column: auto; }
}

@media (max-width: 450px) {
  .b-pool-list { grid-template-columns: 1fr; }
  .variant-b-workbench-toolbar label { min-width: calc(50% - 5px); }
  .variant-b-workbench-toolbar .view-switch { width: 100%; }
  .variant-b-workbench-toolbar .view-switch button { flex: 1; }
}
</style>
