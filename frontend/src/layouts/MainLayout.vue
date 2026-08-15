<script setup lang="ts">
import {
  Bell,
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  ClipboardClock,
  ClipboardList,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings2,
  Shuffle,
  Table2,
  Users,
  WandSparkles,
  X,
  ChevronRight,
} from '@lucide/vue'
import type { Component } from 'vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import NotificationBell from '@/components/NotificationBell.vue'
import { canViewCore } from '@/permissions'
import { useAuthStore } from '@/stores/auth'
import { useAppConfigStore } from '@/stores/appConfig'
import { useSemesterContextStore } from '@/stores/semesterContext'

interface NavItem {
  key: string
  label: string
  icon: Component
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const auth = useAuthStore()
const appConfig = useAppConfigStore()
const semesterContext = useSemesterContextStore()
const router = useRouter()
const route = useRoute()

const drawerOpen = ref(false)
const isMobile = ref(false)
const menuButton = ref<HTMLButtonElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const drawer = ref<HTMLElement | null>(null)
let mobileQuery: MediaQueryList | null = null
let originalBodyOverflow = ''
let drawerFocusFrame: number | null = null

const roleLabels = computed(() => (auth.user?.roles ?? []).map((role) => auth.roleLabel(role)))
const schoolName = computed(() => appConfig.config.school_name)
const userInitial = computed(() => auth.user?.display_name.trim().charAt(0) || '用')
const semesterOptions = computed(() => semesterContext.semesters.map((semester) => ({
  label: semester.label,
  value: semester.id,
})))

// This predicate mirrors the router guard. Navigation visibility and direct-route access stay aligned.
const canManage = computed(() => (
  canViewCore(auth.user?.roles)
))

function navItem(key: string, label: string, icon: Component): NavItem {
  return { key, label, icon }
}

const navGroups = computed<NavGroup[]>(() => {
  const query = navItem('timetable-query', '课表查询', Table2)
  const leaves = navItem('leaves', '请假登记', ClipboardClock)
  const stats = navItem(
    'substitution-stats',
    canManage.value ? '代课课时统计' : '我的代课课时',
    ChartNoAxesColumnIncreasing,
  )

  if (!canManage.value) {
    return [{ label: '常用', items: [query, leaves, stats] }]
  }

  const groups: NavGroup[] = [
    {
      label: '概览',
      items: [
        navItem('dashboard', '仪表盘', LayoutDashboard),
        navItem('wizard', '设置向导', Settings2),
        query,
      ],
    },
    {
      label: '基础数据',
      items: [
        navItem('semesters', '学期与作息时间表', CalendarDays),
        navItem('calendar', '校历与排课准备', CalendarCheck2),
        navItem('basedata', '教师、班级、科目和教室/场地', Users),
      ],
    },
    {
      label: '排课作业',
      items: [
        navItem('assignments', '教学任务', ClipboardList),
        navItem('workbench', '排课工作台', BookOpen),
        navItem('auto-schedule', '自动排课', WandSparkles),
        navItem('versions', '版本与发布', History),
        navItem('timetable-demo', '课表组件（演示）', Table2),
      ],
    },
    {
      label: '调课与代课',
      items: [
        leaves,
        navItem('substitutions', '调课与代课处理', Shuffle),
        navItem('daily-board', '今日调课与代课', CalendarDays),
        navItem('substitution-log', '调课与代课记录', History),
        stats,
        navItem('notification-board', '通知确认看板', Bell),
      ],
    },
  ]
  if (auth.hasRole('admin')) {
    groups.push({
      label: '系统管理',
      items: [navItem('system', '系统管理', Settings2)],
    })
  }
  return groups
})

const routeNavKey = computed(() => (
  route.name === 'period-table-editor' ? 'semesters' : String(route.name ?? '')
))
const activeItem = computed(() => navGroups.value
  .flatMap((group) => group.items)
  .find((item) => item.key === routeNavKey.value))
const activeGroup = computed(() => navGroups.value
  .find((group) => group.items.some((item) => item.key === routeNavKey.value)))
const currentModule = computed(() => activeItem.value?.label || String(route.name ?? '工作台'))

function isActive(item: NavItem): boolean {
  return item.key === routeNavKey.value
}

function scheduleFrame(callback: FrameRequestCallback): number {
  if (typeof window.requestAnimationFrame === 'function') {
    return window.requestAnimationFrame(callback)
  }
  return window.setTimeout(() => callback(Date.now()), 0)
}

function cancelScheduledFrame() {
  if (drawerFocusFrame === null) return
  if (typeof window.cancelAnimationFrame === 'function') {
    window.cancelAnimationFrame(drawerFocusFrame)
  } else {
    window.clearTimeout(drawerFocusFrame)
  }
  drawerFocusFrame = null
}

function focusDrawerControl(attemptsRemaining: number) {
  drawerFocusFrame = null
  if (!drawerOpen.value) return

  const target = closeButton.value
  const canFocus = target
    && getComputedStyle(target).visibility !== 'hidden'
    && !drawer.value?.inert
  if (canFocus) {
    target.focus()
    if (document.activeElement === target) return
  }

  if (attemptsRemaining > 0) {
    drawerFocusFrame = scheduleFrame(() => focusDrawerControl(attemptsRemaining - 1))
  }
}

function openDrawer() {
  drawerOpen.value = true
  void nextTick(() => {
    cancelScheduledFrame()
    drawerFocusFrame = scheduleFrame(() => focusDrawerControl(5))
  })
}

function closeDrawer(restoreFocus = true) {
  cancelScheduledFrame()
  if (!drawerOpen.value) return
  drawerOpen.value = false
  if (restoreFocus) void nextTick(() => menuButton.value?.focus())
}

function onNavClick() {
  closeDrawer(isMobile.value)
}

function onDrawerKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeDrawer()
    return
  }
  if (event.key !== 'Tab' || !drawerOpen.value || !drawer.value) return

  const focusable = Array.from(drawer.value.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  ))
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

function syncViewport() {
  isMobile.value = mobileQuery?.matches ?? window.innerWidth < 768
  if (!isMobile.value && drawerOpen.value) closeDrawer(false)
}

function onWindowKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && drawerOpen.value) closeDrawer()
}

async function onLogout() {
  await auth.logout()
  await router.push({ name: 'login' })
}

async function onSemesterChange(event: Event) {
  const value = Number((event.target as HTMLSelectElement).value)
  if (!Number.isInteger(value) || value <= 0) return
  try {
    await semesterContext.switchTo(value)
  } catch {
    // The store reloads the authoritative context and exposes the readable error.
  }
}

watch(() => route.fullPath, () => closeDrawer(false))
watch(drawerOpen, (open) => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = open && isMobile.value ? 'hidden' : originalBodyOverflow
})

onMounted(() => {
  void semesterContext.load()
  originalBodyOverflow = document.body.style.overflow
  mobileQuery = typeof window.matchMedia === 'function'
    ? window.matchMedia('(max-width: 767px)')
    : null
  syncViewport()
  mobileQuery?.addEventListener('change', syncViewport)
  window.addEventListener('resize', syncViewport)
  window.addEventListener('keydown', onWindowKeydown)
})

onBeforeUnmount(() => {
  cancelScheduledFrame()
  mobileQuery?.removeEventListener('change', syncViewport)
  window.removeEventListener('resize', syncViewport)
  window.removeEventListener('keydown', onWindowKeydown)
  document.body.style.overflow = originalBodyOverflow
})
</script>

<template>
  <div class="app-shell" data-testid="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>

    <div
      v-if="drawerOpen"
      class="app-shell-scrim"
      data-testid="shell-scrim"
      aria-hidden="true"
      @click="closeDrawer()"
    />

    <aside
      id="app-navigation"
      ref="drawer"
      class="app-sidebar"
      :class="{ 'is-open': drawerOpen }"
      :aria-hidden="isMobile && !drawerOpen ? 'true' : undefined"
      :inert="isMobile && !drawerOpen"
      aria-label="主导航"
      data-testid="mobile-drawer"
      @keydown="onDrawerKeydown"
    >
      <div
        class="app-brand" data-testid="product-identity"
        aria-label="学校排课、调课与代课管理系统"
        title="学校排课、调课与代课管理系统"
      >
        <span class="sr-only">学校排课、调课与代课管理系统</span>
        <span class="app-brand-mark" aria-hidden="true">
          <CalendarDays :size="20" :stroke-width="1.9" />
        </span>
        <span class="app-brand-copy">
          <strong>教务排课</strong>
          <small>排课 · 调课 · 代课</small>
        </span>
        <button
          ref="closeButton"
          type="button"
          class="app-icon-button app-drawer-close"
          aria-label="关闭导航"
          title="关闭导航"
          data-testid="shell-close"
          @click="closeDrawer()"
        >
          <X :size="18" :stroke-width="1.9" aria-hidden="true" />
        </button>
      </div>

      <nav class="app-nav" aria-label="功能导航" data-testid="shell-nav">
        <section
          v-for="(group, groupIndex) in navGroups"
          :key="group.label"
          class="app-nav-group"
          :aria-labelledby="`nav-group-${groupIndex}`"
        >
          <p :id="`nav-group-${groupIndex}`" class="app-nav-label">{{ group.label }}</p>
          <RouterLink
            v-for="item in group.items"
            :key="item.key"
            :to="{ name: item.key }"
            class="app-nav-link"
            :class="{ 'is-active': isActive(item) }"
            :aria-current="isActive(item) ? 'page' : undefined"
            :aria-label="item.label"
            :title="item.label"
            :data-nav-key="item.key"
            @click="onNavClick"
          >
            <span class="app-nav-icon" aria-hidden="true">
              <component :is="item.icon" :size="18" :stroke-width="1.8" />
            </span>
            <span class="app-nav-text">{{ item.label }}</span>
          </RouterLink>
        </section>
      </nav>

      <div class="app-sidebar-footer">
        <span class="app-school-icon" aria-hidden="true">
          <Users :size="17" :stroke-width="1.8" />
        </span>
        <span class="app-school-copy">
          <strong>{{ schoolName }}</strong>
          <small>教学运行工作台</small>
        </span>
      </div>
    </aside>

    <div class="app-main" :inert="isMobile && drawerOpen">
      <header class="app-topbar">
        <button
          ref="menuButton"
          type="button"
          class="app-icon-button app-menu-button"
          aria-label="打开导航"
          title="打开导航"
          aria-controls="app-navigation"
          :aria-expanded="drawerOpen"
          data-testid="shell-menu"
          @click="openDrawer"
        >
          <Menu :size="19" :stroke-width="1.9" aria-hidden="true" />
        </button>

        <div class="app-breadcrumb" data-testid="shell-breadcrumb" aria-label="当前位置">
          <span class="app-breadcrumb-root">教务排课</span>
          <ChevronRight class="app-breadcrumb-separator" :size="14" aria-hidden="true" />
          <span v-if="activeGroup" class="app-breadcrumb-group">{{ activeGroup.label }}</span>
          <ChevronRight v-if="activeGroup" class="app-breadcrumb-separator" :size="14" aria-hidden="true" />
          <strong>{{ currentModule }}</strong>
        </div>

        <div class="app-topbar-actions">
          <div
            v-if="semesterContext.loaded"
            class="app-semester-context"
            :class="{ 'is-switching': semesterContext.switching }"
            data-testid="semester-context"
            :title="semesterContext.error || '当前工作学期'"
          >
            <CalendarDays :size="16" :stroke-width="1.9" aria-hidden="true" />
            <label class="sr-only" for="current-semester-select">当前工作学期</label>
            <select
              v-if="semesterContext.canSwitch"
              id="current-semester-select"
              class="app-semester-select"
              :value="semesterContext.currentSemesterId ?? ''"
              :disabled="semesterContext.switching || !semesterOptions.length"
              aria-label="切换当前学期"
              data-testid="current-semester-select"
              @change="onSemesterChange"
            >
              <option v-if="semesterContext.currentSemesterId === null" value="" disabled>
                {{ semesterOptions.length ? '未选择学期' : '未创建学期' }}
              </option>
              <option v-for="option in semesterOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <span v-else class="app-semester-label" data-testid="current-semester-label">
              {{ semesterContext.currentSemester?.label || '未选择学期' }}
            </span>
          </div>

          <NotificationBell />

          <div
            v-if="auth.user"
            class="app-profile"
            :aria-label="`${auth.user.display_name}，${roleLabels.join('、')}`"
          >
            <span class="app-avatar" aria-hidden="true">{{ userInitial }}</span>
            <span class="app-profile-copy">
              <strong>{{ auth.user.display_name }}</strong>
              <small>{{ roleLabels.join('、') }}</small>
            </span>
          </div>

          <button
            type="button"
            class="app-logout-button"
            aria-label="退出登录"
            title="退出登录"
            data-testid="shell-logout"
            @click="onLogout"
          >
            <LogOut :size="17" :stroke-width="1.9" aria-hidden="true" />
            <span class="app-action-label">退出登录</span>
          </button>
        </div>
      </header>

      <main id="main-content" class="app-content" tabindex="-1">
        <router-view :key="semesterContext.revision" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 228px minmax(0, 1fr);
  width: 100%;
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
  background: var(--app-background);
  color: var(--app-text);
}

.skip-link {
  position: fixed;
  z-index: 100;
  top: var(--app-space-2);
  left: var(--app-space-2);
  padding: var(--app-space-2) var(--app-space-3);
  border-radius: var(--app-radius-sm);
  background: var(--app-primary);
  color: var(--app-on-primary);
  transform: translateY(-160%);
  transition: transform var(--app-motion-duration) var(--app-motion-ease);
}

.skip-link:focus { transform: translateY(0); }

.app-sidebar {
  position: relative;
  z-index: 20;
  display: flex;
  width: 228px;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--app-border);
  background: var(--app-surface);
  transition: transform var(--app-motion-duration) var(--app-motion-ease);
}

.app-brand {
  display: flex;
  min-height: 70px;
  align-items: center;
  gap: var(--app-space-3);
  padding: var(--app-space-3) var(--app-space-4);
  border-bottom: 1px solid var(--app-border);
}

.app-brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: var(--app-primary);
  color: var(--app-on-primary);
  box-shadow: var(--app-shadow-focus);
}

.app-brand-copy,
.app-profile-copy,
.app-school-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.app-brand-copy { flex: 1; }
.app-brand-copy strong { font-size: 15px; line-height: 1.3; }
.app-brand-copy small,
.app-school-copy small,
.app-profile-copy small { color: var(--app-text-muted); font-size: 11px; }

.app-nav {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: var(--app-space-3) var(--app-space-2);
  scrollbar-width: thin;
}

.app-nav-group + .app-nav-group { margin-top: var(--app-space-3); }

.app-nav-label {
  margin: 0;
  padding: 0 var(--app-space-2) var(--app-space-1);
  color: var(--app-text-faint);
  font-size: 11px;
  font-weight: 600;
}

.app-nav-link {
  position: relative;
  display: flex;
  min-height: 40px;
  align-items: center;
  gap: var(--app-space-2);
  margin-top: 2px;
  padding: 0 var(--app-space-2);
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: var(--app-radius-sm);
  color: var(--app-text-muted);
  text-decoration: none;
  transition:
    border-color var(--app-motion-duration) var(--app-motion-ease),
    background-color var(--app-motion-duration) var(--app-motion-ease),
    color var(--app-motion-duration) var(--app-motion-ease);
}

.app-nav-link:hover {
  border-color: var(--app-border);
  background: var(--app-surface-muted);
  color: var(--app-text);
}

.app-nav-link.is-active {
  border-color: var(--app-primary-border);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
  font-weight: 700;
}

.app-nav-link.is-active::before {
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--app-primary);
  content: '';
}

.app-nav-icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--app-radius-sm);
}

.app-nav-link.is-active .app-nav-icon { background: var(--app-surface); }

.app-nav-text {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-sidebar-footer {
  display: flex;
  min-height: 62px;
  align-items: center;
  gap: var(--app-space-2);
  padding: var(--app-space-3);
  border-top: 1px solid var(--app-border);
  background: var(--app-surface-muted);
}

.app-school-icon {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--app-radius-sm);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}

.app-school-copy { overflow: hidden; }
.app-school-copy strong {
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: 70px minmax(0, 1fr);
}

.app-topbar {
  position: relative;
  z-index: 10;
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--app-space-3);
  padding: 0 var(--app-space-5);
  border-bottom: 1px solid var(--app-border);
  background: var(--app-surface);
}

.app-icon-button,
.app-logout-button {
  display: inline-flex;
  min-width: 38px;
  height: 38px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  color: var(--app-text-muted);
  cursor: pointer;
  transition:
    border-color var(--app-motion-duration) var(--app-motion-ease),
    background-color var(--app-motion-duration) var(--app-motion-ease),
    color var(--app-motion-duration) var(--app-motion-ease);
}

.app-icon-button:hover,
.app-logout-button:hover {
  border-color: var(--app-primary-border);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
}

.app-icon-button.app-menu-button,
.app-icon-button.app-drawer-close { display: none; }

.app-breadcrumb {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--app-space-1);
  overflow: hidden;
  color: var(--app-text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.app-breadcrumb strong {
  min-width: 0;
  overflow: hidden;
  color: var(--app-text);
  font-size: 14px;
  text-overflow: ellipsis;
}

.app-breadcrumb-separator { flex: 0 0 auto; color: var(--app-text-faint); }

.app-topbar-actions {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--app-space-2);
  margin-left: auto;
}

.app-semester-context {
  display: inline-flex;
  min-width: 0;
  height: 36px;
  align-items: center;
  gap: var(--app-space-1);
  padding: 0 var(--app-space-2);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-muted);
  color: var(--app-primary-strong);
  transition: opacity var(--app-motion-duration) var(--app-motion-ease);
}

.app-semester-context.is-switching { opacity: 0.62; }

.app-semester-select,
.app-semester-label {
  min-width: 0;
  max-width: 190px;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--app-text);
  font: inherit;
  font-size: 12px;
  font-weight: 650;
}

.app-semester-select { cursor: pointer; }
.app-semester-select:disabled { cursor: wait; }
.app-semester-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-profile {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--app-space-2);
}

.app-avatar {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: var(--app-primary-soft);
  color: var(--app-primary-strong);
  font-size: 13px;
  font-weight: 800;
}

.app-profile-copy { max-width: 128px; }
.app-profile-copy strong,
.app-profile-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-profile-copy strong { font-size: 12px; }

.app-logout-button {
  gap: var(--app-space-2);
  padding: 0 var(--app-space-3);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
}

.app-content {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: var(--app-space-5);
  background: var(--app-background);
  overscroll-behavior: contain;
}

.app-shell-scrim {
  position: fixed;
  z-index: 15;
  inset: 0;
  background: var(--app-overlay);
}

@media (min-width: 768px) and (max-width: 1023px) {
  .app-shell { grid-template-columns: 64px minmax(0, 1fr); }
  .app-sidebar { width: 64px; }
  .app-brand { justify-content: center; padding: var(--app-space-3); }
  .app-brand-copy,
  .app-nav-label,
  .app-nav-text,
  .app-school-copy { display: none; }
  .app-nav { padding: var(--app-space-2) 7px; }
  .app-nav-group + .app-nav-group {
    margin-top: var(--app-space-2);
    padding-top: var(--app-space-2);
    border-top: 1px solid var(--app-border);
  }
  .app-nav-link { justify-content: center; padding: 0; }
  .app-nav-link.is-active::before { top: 7px; bottom: 7px; }
  .app-nav-icon { width: 38px; height: 32px; }
  .app-sidebar-footer { justify-content: center; padding: var(--app-space-2); }
  .app-topbar { padding: 0 var(--app-space-4); }
}

@media (max-width: 900px) {
  .app-action-label { display: none; }
  .app-logout-button { width: 38px; padding: 0; }
  .app-semester-select,
  .app-semester-label { max-width: 145px; }
}

@media (max-width: 767px) {
  .app-shell { display: block; }
  .app-sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    width: min(284px, 86vw);
    visibility: hidden;
    pointer-events: none;
    transform: translateX(-102%);
    box-shadow: var(--app-shadow-lg);
  }
  .app-sidebar.is-open {
    visibility: visible;
    pointer-events: auto;
    transform: translateX(0);
  }
  .app-icon-button.app-drawer-close { display: inline-flex; margin-left: auto; }
  .app-main { height: 100%; grid-template-rows: 62px minmax(0, 1fr); }
  .app-topbar { gap: var(--app-space-2); padding: 0 var(--app-space-3); }
  .app-icon-button.app-menu-button { display: inline-flex; }
  .app-content { padding: var(--app-space-4) var(--app-space-3) var(--app-space-6); }
  .app-breadcrumb { flex: 1; }
  .app-breadcrumb-root,
  .app-breadcrumb-group,
  .app-breadcrumb-group + .app-breadcrumb-separator { display: none; }
  .app-profile-copy { max-width: 76px; }
  .app-profile-copy small { font-size: 10px; }
  .app-semester-context { max-width: 170px; }
  .app-semester-select,
  .app-semester-label { max-width: 118px; }
}

@media (max-width: 420px) {
  .app-topbar-actions { gap: var(--app-space-1); }
  .app-avatar { width: 30px; height: 30px; }
  .app-profile { gap: var(--app-space-1); }
  .app-profile-copy { max-width: 62px; }
  .app-semester-context { max-width: 132px; padding: 0 var(--app-space-1); }
  .app-semester-select,
  .app-semester-label { max-width: 85px; }
}
</style>
