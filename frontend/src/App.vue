<script setup lang="ts">
import {
  NConfigProvider, NDialogProvider, NGlobalStyle, NMessageProvider, zhCN, dateZhCN,
} from 'naive-ui'
import { themeOverrides } from '@/theme'
</script>

<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="themeOverrides">
    <n-global-style />
    <!-- useDialog() 依赖对话框上下文；缺少此组件时，系统管理页无法渲染。 -->
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
