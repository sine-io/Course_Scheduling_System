<script setup lang="ts">
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { onBeforeUnmount, onMounted } from 'vue'
import type { ViewKey } from './prototypeData'

export interface PrototypeVariantMeta {
  key: string
  name: string
}

const props = defineProps<{
  variants: PrototypeVariantMeta[]
  current: string
  currentName: string
  activeView: ViewKey
}>()

const emit = defineEmits<{
  change: [key: string]
}>()

const visible = !import.meta.env.PROD

function move(delta: number) {
  if (!props.variants.length) return
  const index = props.variants.findIndex((item) => item.key === props.current)
  const nextIndex = (index + delta + props.variants.length) % props.variants.length
  emit('change', props.variants[nextIndex].key)
}

function onKeydown(event: KeyboardEvent) {
  if (!visible || (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight')) return
  const target = event.target
  if (target instanceof HTMLElement) {
    const tag = target.tagName.toLowerCase()
    if (tag === 'input' || tag === 'textarea' || target.isContentEditable) return
  }
  event.preventDefault()
  move(event.key === 'ArrowLeft' ? -1 : 1)
}

onMounted(() => {
  if (visible) window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  if (visible) window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div v-if="visible" class="prototype-switcher" role="toolbar" aria-label="原型变体切换">
    <button
      class="prototype-switcher-arrow"
      type="button"
      aria-label="上一个变体"
      title="上一个变体"
      @click="move(-1)"
    >
      <ChevronLeft :size="16" :stroke-width="2" aria-hidden="true" />
    </button>
    <div class="prototype-switcher-label">
      <span class="prototype-switcher-kicker">临时原型</span>
      <strong>{{ current }} · {{ currentName }}</strong>
      <span class="prototype-switcher-view">{{ activeView === 'dashboard' ? '仪表盘' : '排课工作台' }}</span>
    </div>
    <button
      class="prototype-switcher-arrow"
      type="button"
      aria-label="下一个变体"
      title="下一个变体"
      @click="move(1)"
    >
      <ChevronRight :size="16" :stroke-width="2" aria-hidden="true" />
    </button>
  </div>
</template>
