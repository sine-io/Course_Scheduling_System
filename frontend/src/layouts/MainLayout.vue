<script setup lang="ts">
import { NButton, NLayout, NLayoutContent, NLayoutHeader, NLayoutSider, NMenu, NSpace, NTag, NText } from 'naive-ui'
import { computed, h, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NotificationBell from '@/components/NotificationBell.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const roleLabels = computed(() => (auth.user?.roles ?? []).map((r) => auth.roleLabel(r)))

// 手机尺寸默认收合侧边栏:390px 宽的屏幕若被 220px 侧栏占去,课表几乎没有空间
const collapsed = ref(typeof window !== 'undefined' && window.innerWidth < 768)

function menuLink(name: string, label: string) {
  return () => h(RouterLink, { to: { name } }, { default: () => label })
}

// 纯教师账号只看得到课表查询(其余页面的后端 API 需排课管理员以上权限)
const canManage = computed(() =>
  auth.hasRole('admin') || auth.hasRole('scheduler') || auth.hasRole('director'))

const menuOptions = computed(() => {
  const query = { label: menuLink('timetable-query', '课表查询'), key: 'timetable-query' }
  // 请假是教师自己要做的事,纯教师账号也看得到
  const leaves = { label: menuLink('leaves', '请假登记'), key: 'leaves' }
  // 教师可查自己的代课课时
  const myStats = { label: menuLink('substitution-stats', '我的代课课时'), key: 'substitution-stats' }
  if (!canManage.value) return [query, leaves, myStats]
  return [
    { label: menuLink('dashboard', '仪表盘'), key: 'dashboard' },
    query,
    {
      label: '基础数据',
      key: 'basedata-group',
      children: [
        { label: menuLink('semesters', '学期与作息时间表'), key: 'semesters' },
        { label: menuLink('calendar', '校历与排课准备'), key: 'calendar' },
        { label: menuLink('basedata', '教师、班级、科目和教室/场地'), key: 'basedata' },
      ],
    },
    {
      label: '排课作业',
      key: 'scheduling-group',
      children: [
        { label: menuLink('assignments', '教学任务'), key: 'assignments' },
        { label: menuLink('workbench', '排课工作台'), key: 'workbench' },
        { label: menuLink('auto-schedule', '自动排课'), key: 'auto-schedule' },
        { label: menuLink('versions', '版本与发布'), key: 'versions' },
        { label: menuLink('timetable-demo', '课表组件（演示）'), key: 'timetable-demo' },
      ],
    },
    {
      label: '调课与代课',
      key: 'substitution-group',
      children: [
        leaves,
        { label: menuLink('substitutions', '调课与代课处理'), key: 'substitutions' },
        { label: menuLink('daily-board', '今日调课与代课'), key: 'daily-board' },
        { label: menuLink('substitution-log', '调课与代课记录'), key: 'substitution-log' },
        { label: menuLink('substitution-stats', '代课课时统计'), key: 'substitution-stats' },
        { label: menuLink('notification-board', '通知确认看板'), key: 'notification-board' },
      ],
    },
    { label: menuLink('system', '系统管理'), key: 'system' },
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
        {{ collapsed ? '排课' : '学校排课、调课与代课管理系统' }}
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
          <n-button size="small" @click="onLogout">{{ '退出登录' }}</n-button>
        </n-space>
      </n-layout-header>

      <n-layout-content content-style="padding: 24px" style="background: transparent">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>
