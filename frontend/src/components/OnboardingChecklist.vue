<script setup lang="ts">
import { ArrowUpRight, CheckCircle2, CircleAlert, ListChecks } from '@lucide/vue'
import { NTag } from 'naive-ui'
import { RouterLink } from 'vue-router'
import type { OnboardingStatus } from '@/api/onboarding'

defineProps<{
  status: OnboardingStatus
}>()

</script>

<template>
  <section class="onboarding-checklist" data-testid="onboarding-status" aria-labelledby="onboarding-title">
    <header class="onboarding-heading">
      <div>
        <p class="onboarding-eyebrow">首次成功 · P0</p>
        <h2 id="onboarding-title">首次成功路径</h2>
        <p v-if="status.current_semester">
          {{ status.current_semester.label }}
          <span v-if="status.current_semester.is_demo"> · 示例数据</span>
        </p>
        <p v-else>还没有正式当前学期</p>
      </div>
      <n-tag :type="status.first_success ? 'success' : 'warning'" size="small">
        {{ status.first_success ? '已完成' : `待完成 ${status.p0_todos.length} 项` }}
      </n-tag>
    </header>

    <div v-if="status.first_success" class="onboarding-success" data-testid="onboarding-success">
      <CheckCircle2 :size="18" aria-hidden="true" />
      <strong>正式当前学期已发布可用课表</strong>
      <span>首次成功状态由当前业务数据自动维护。</span>
    </div>

    <ol class="onboarding-stage-list" data-testid="onboarding-stages">
      <li
        v-for="stage in status.stages"
        :key="stage.key"
        class="onboarding-stage"
        :class="{ 'is-complete': stage.complete }"
        :data-testid="`onboarding-stage-${stage.key}`"
      >
        <span class="onboarding-stage-icon" aria-hidden="true">
          <CheckCircle2 v-if="stage.complete" :size="17" />
          <CircleAlert v-else :size="17" />
        </span>
        <div class="onboarding-stage-copy">
          <strong>{{ stage.label }}</strong>
          <span v-if="stage.complete">已完成</span>
          <span v-else>{{ stage.blocking_reason }}</span>
        </div>
        <RouterLink
          v-if="!stage.complete && stage.next_action"
          class="onboarding-stage-action"
          :to="stage.next_action.href"
          :aria-label="stage.next_action.label"
        >
          {{ stage.next_action.label }}
          <ArrowUpRight :size="14" aria-hidden="true" />
        </RouterLink>
      </li>
    </ol>

    <RouterLink
      v-if="!status.first_success && status.next_action"
      class="onboarding-next-action"
      :to="status.next_action.href"
      data-testid="onboarding-next-action"
    >
      <ListChecks :size="16" aria-hidden="true" />
      {{ status.next_action.label }}
      <ArrowUpRight :size="14" aria-hidden="true" />
    </RouterLink>
  </section>
</template>

<style scoped>
.onboarding-checklist {
  display: grid;
  min-width: 0;
  gap: 16px;
  padding: 22px;
  border: 1px solid var(--app-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-primary-soft);
}
.onboarding-heading { display: flex; min-width: 0; align-items: flex-start; justify-content: space-between; gap: 14px; }
.onboarding-eyebrow { margin: 0 0 6px; color: var(--app-primary-strong); font-size: 11px; font-weight: 700; }
.onboarding-heading h2 { margin: 0; font-size: 17px; line-height: 1.35; }
.onboarding-heading p:last-child { margin: 5px 0 0; color: var(--app-text-muted); font-size: 12px; }
.onboarding-success { display: flex; min-width: 0; align-items: center; gap: 8px; color: var(--app-success-strong, var(--app-primary-strong)); }
.onboarding-success span { color: var(--app-text-muted); font-size: 12px; }
.onboarding-stage-list { display: grid; gap: 1px; margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--app-primary-border); }
.onboarding-stage { display: grid; min-width: 0; grid-template-columns: 22px minmax(0, 1fr) auto; align-items: center; gap: 9px; padding: 11px 0; border-bottom: 1px solid var(--app-primary-border); }
.onboarding-stage-icon { display: grid; place-items: center; color: var(--app-warning, #c47b00); }
.onboarding-stage.is-complete .onboarding-stage-icon { color: var(--app-primary-strong); }
.onboarding-stage-copy { display: grid; min-width: 0; gap: 3px; }
.onboarding-stage-copy strong { font-size: 13px; }
.onboarding-stage-copy span { overflow-wrap: anywhere; color: var(--app-text-muted); font-size: 12px; line-height: 1.45; }
.onboarding-stage-action,
.onboarding-next-action { display: inline-flex; align-items: center; justify-content: center; gap: 5px; color: var(--app-primary-strong); font-size: 12px; font-weight: 650; text-decoration: none; }
.onboarding-stage-action { white-space: nowrap; }
.onboarding-stage-action:hover,
.onboarding-next-action:hover { text-decoration: underline; }
.onboarding-next-action { justify-self: start; min-height: 34px; padding: 0 11px; border: 1px solid var(--app-primary); border-radius: var(--app-radius-sm); background: var(--app-primary); color: var(--app-on-primary); }
@media (max-width: 560px) {
  .onboarding-checklist { padding: 18px 16px; }
  .onboarding-stage { grid-template-columns: 22px minmax(0, 1fr); align-items: start; }
  .onboarding-stage-action { grid-column: 2; justify-self: start; }
  .onboarding-success { align-items: flex-start; flex-wrap: wrap; }
}
</style>
