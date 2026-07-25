<script setup lang="ts">
import {
  NConfigProvider, NDialogProvider, NGlobalStyle, NMessageProvider, zhCN, dateZhCN, zhTW, dateZhTW,
} from 'naive-ui'
import { computed } from 'vue'
import { themeOverrides } from '@/theme'
import { useAppConfigStore } from '@/stores/appConfig'

const appConfig = useAppConfigStore()
const locale = computed(() => appConfig.isMainland ? zhCN : zhTW)
const dateLocale = computed(() => appConfig.isMainland ? dateZhCN : dateZhTW)
</script>

<template>
  <n-config-provider :locale="locale" :date-locale="dateLocale" :theme-overrides="themeOverrides">
    <n-global-style />
    <!-- dialog provider 不可少:useDialog() 找不到它會在 setup 直接擲錯,整頁渲染不出來
         (系統管理頁就是這樣整片空白的)。 -->
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
