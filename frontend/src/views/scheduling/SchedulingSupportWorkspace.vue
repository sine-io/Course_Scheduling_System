<script setup lang="ts">
import { ArrowLeft, CalendarDays, Database, GraduationCap } from '@lucide/vue'
import { NButton } from 'naive-ui'
import { computed } from 'vue'
import BaseData from '@/views/basedata/BaseData.vue'
import type { BaseDataSection } from '@/views/basedata/BaseData.vue'
import Calendar from '@/views/settings/Calendar.vue'
import Semesters from '@/views/settings/Semesters.vue'

export type SupportPanel = 'semester' | 'calendar' | 'resources'

const props = withDefaults(defineProps<{
  panel: SupportPanel
  semesterId: number
  resourceSection?: BaseDataSection
}>(), {
  resourceSection: 'rooms',
})
const emit = defineEmits<{
  back: []
  changed: []
  semestersChanged: [preferredSemesterId?: number]
  editPeriodTable: [id: number]
}>()

const panelMeta = computed(() => {
  if (props.panel === 'semester') {
    return {
      eyebrow: '学期准备辅助工作面',
      title: '学期与作息时间表',
      description: '维护学期生命周期、日期和作息时间表；完成后返回排课工作台继续准备。',
    }
  }
  if (props.panel === 'calendar') {
    return {
      eyebrow: '学期准备辅助工作面',
      title: '校历与排课准备',
      description: '维护停课与补课日期，并在需要时确认或撤销排课准备状态。',
    }
  }
  return {
    eyebrow: '学期准备辅助工作面',
    title: '基础数据',
    description: '维护教室、模板、参考文件和教师账号绑定等排课资源。',
  }
})

function onSemestersChanged(preferredSemesterId?: number) {
  emit('semestersChanged', preferredSemesterId)
}
</script>

<template>
  <section class="scheduling-support-workspace" data-testid="flow-support-panel">
    <header class="scheduling-support-header">
      <div class="scheduling-support-heading">
        <div class="scheduling-support-icon" aria-hidden="true">
          <GraduationCap v-if="props.panel === 'semester'" :size="20" />
          <CalendarDays v-else-if="props.panel === 'calendar'" :size="20" />
          <Database v-else :size="20" />
        </div>
        <div>
          <p class="scheduling-eyebrow">{{ panelMeta.eyebrow }}</p>
          <h2>{{ panelMeta.title }}</h2>
          <p>{{ panelMeta.description }}</p>
        </div>
      </div>
      <n-button data-testid="flow-support-back" @click="emit('back')">
        <template #icon><ArrowLeft :size="16" aria-hidden="true" /></template>
        {{ '返回排课工作台' }}
      </n-button>
    </header>

    <Semesters
      v-if="props.panel === 'semester'"
      embedded
      :embedded-semester-id="props.semesterId"
      @changed="emit('changed')"
      @semesters-changed="onSemestersChanged"
      @edit-period-table="emit('editPeriodTable', $event)"
    />
    <Calendar
      v-else-if="props.panel === 'calendar'"
      embedded
      :embedded-semester-id="props.semesterId"
      @changed="emit('changed')"
    />
    <BaseData
      v-else
      embedded
      :embedded-semester-id="props.semesterId"
      :embedded-section="props.resourceSection"
      @changed="emit('changed')"
    />
  </section>
</template>

<style scoped>
.scheduling-support-workspace { display: grid; gap: var(--app-space-4); }
.scheduling-support-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  padding: 2px 0;
}
.scheduling-support-heading { display: flex; align-items: flex-start; gap: var(--app-space-3); min-width: 0; }
.scheduling-support-icon {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  color: var(--app-primary-strong);
  background: var(--app-surface-muted);
}
.scheduling-support-header h2 { margin: 0; overflow-wrap: anywhere; font-size: 20px; }
.scheduling-support-header p:last-child { margin: 5px 0 0; color: var(--app-text-muted); font-size: 13px; line-height: 1.55; }
@media (max-width: 700px) {
  .scheduling-support-header { align-items: stretch; flex-direction: column; }
  .scheduling-support-header > .n-button { align-self: flex-start; }
}
</style>
