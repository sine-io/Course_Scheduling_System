<script setup lang="ts">
import { NButton, NLayout, NLayoutContent, NLayoutHeader, NLayoutSider, NMenu, NSpace, NTag, NText } from 'naive-ui'
import { computed, h, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppConfigStore } from '@/stores/appConfig'
import NotificationBell from '@/components/NotificationBell.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const roleLabels = computed(() => (auth.user?.roles ?? []).map((r) => auth.roleLabel(r)))
const appConfig = useAppConfigStore()
const cn = computed(() => appConfig.isMainland)
const tr = (tw: string, mainland: string) => cn.value ? mainland : tw

// 手機尺寸預設收合側邊欄:390px 寬的螢幕若被 220px 側欄佔去,課表幾乎沒有空間
const collapsed = ref(typeof window !== 'undefined' && window.innerWidth < 768)

function menuLink(name: string, label: string) {
  return () => h(RouterLink, { to: { name } }, { default: () => label })
}

// 純教師帳號只看得到課表查詢(其餘頁面的後端 API 需教學組長以上權限)
const canManage = computed(() =>
  auth.hasRole('admin') || auth.hasRole('scheduler') || auth.hasRole('director'))

const menuOptions = computed(() => {
  const query = { label: menuLink('timetable-query', tr('課表查詢', '课表查询')), key: 'timetable-query' }
  // 請假是教師自己要做的事,純教師帳號也看得到
  const leaves = { label: menuLink('leaves', tr('請假登記', '请假登记')), key: 'leaves' }
  // 教師可查自己的代課鐘點
  const myStats = { label: menuLink('substitution-stats', tr('我的代課鐘點', '我的代课课时')), key: 'substitution-stats' }
  if (!canManage.value) return [query, leaves, myStats]
  return [
    { label: menuLink('dashboard', tr('儀表板', '仪表盘')), key: 'dashboard' },
    query,
    {
      label: tr('基礎資料', '基础资料'),
      key: 'basedata-group',
      children: [
        { label: menuLink('semesters', tr('學期與節次表', '学期与节次表')), key: 'semesters' },
        { label: menuLink('calendar', tr('校曆與就緒', '校历与就绪')), key: 'calendar' },
        { label: menuLink('basedata', tr('教師/班級/科目/場地', '教师/班级/科目/场地')), key: 'basedata' },
      ],
    },
    {
      label: tr('排課作業', '排课作业'),
      key: 'scheduling-group',
      children: [
        { label: menuLink('assignments', tr('配課管理', '配课管理')), key: 'assignments' },
        { label: menuLink('workbench', tr('排課工作台', '排课工作台')), key: 'workbench' },
        { label: menuLink('auto-schedule', tr('自動排課', '自动排课')), key: 'auto-schedule' },
        { label: menuLink('versions', tr('版本與發布', '版本与发布')), key: 'versions' },
        { label: menuLink('timetable-demo', tr('課表元件(示範)', '课表组件（演示）')), key: 'timetable-demo' },
      ],
    },
    {
      label: tr('調代課', '调代课'),
      key: 'substitution-group',
      children: [
        leaves,
        { label: menuLink('substitutions', tr('調代課處理', '调代课处理')), key: 'substitutions' },
        { label: menuLink('daily-board', tr('今日調代課', '今日调代课')), key: 'daily-board' },
        { label: menuLink('substitution-log', tr('調代課紀錄', '调代课记录')), key: 'substitution-log' },
        { label: menuLink('substitution-stats', tr('代課鐘點統計', '代课课时统计')), key: 'substitution-stats' },
        { label: menuLink('notification-board', tr('通知確認看板', '通知确认看板')), key: 'notification-board' },
      ],
    },
    { label: menuLink('system', tr('系統管理', '系统管理')), key: 'system' },
  ]
})

const activeKey = computed(() => route.name as string)

async function onLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <n-layout has-sider style="height: 100vh">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      show-trigger
      :collapsed="collapsed"
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div style="padding: 16px; font-weight: 700; white-space: nowrap; overflow: hidden">
        {{ collapsed ? (cn ? '排课' : '排課') : tr('排課與調代課系統', '排课与调代课系统') }}
      </div>
      <n-menu
        :value="activeKey"
        :collapsed="collapsed"
        :collapsed-width="64"
        :options="menuOptions"
        :default-expanded-keys="['basedata-group', 'scheduling-group']"
      />
    </n-layout-sider>

    <n-layout>
      <n-layout-header bordered style="padding: 12px 24px">
        <n-space justify="end" align="center">
          <notification-bell />
          <n-text v-if="auth.user">{{ auth.user.display_name }}</n-text>
          <n-tag v-for="label in roleLabels" :key="label" type="info" size="small">
            {{ label }}
          </n-tag>
          <n-button size="small" @click="onLogout">{{ tr('登出', '退出登录') }}</n-button>
        </n-space>
      </n-layout-header>

      <n-layout-content content-style="padding: 24px" style="background: transparent">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>
