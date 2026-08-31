<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight } from '@lucide/vue'

const route = useRoute()
const router = useRouter()

const variants = [
  { id: 'A', label: 'A · 分步向导' },
  { id: 'B', label: 'B · 问题收件箱' },
  { id: 'C', label: 'C · 数据工作台' },
] as const

const activeIndex = computed(() => {
  const value = String(route.query.variant || 'A').toUpperCase()
  const index = variants.findIndex((variant) => variant.id === value)
  return index >= 0 ? index : 0
})

const activeVariant = computed(() => variants[activeIndex.value])

function selectVariant(index: number) {
  const normalizedIndex = (index + variants.length) % variants.length
  const variant = variants[normalizedIndex]
  void router.replace({
    query: {
      ...route.query,
      variant: variant.id,
    },
  })
}

function handleKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  const tagName = target?.tagName?.toLowerCase()
  if (tagName === 'input' || tagName === 'textarea' || tagName === 'select' || target?.isContentEditable) {
    return
  }

  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    selectVariant(activeIndex.value - 1)
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    selectVariant(activeIndex.value + 1)
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <nav class="prototype-switcher" aria-label="原型方案切换">
    <button
      class="prototype-switcher__arrow"
      type="button"
      title="上一个方案（←）"
      aria-label="上一个方案"
      @click="selectVariant(activeIndex - 1)"
    >
      <ArrowLeft :size="16" aria-hidden="true" />
    </button>
    <div class="prototype-switcher__current">
      <span class="prototype-switcher__eyebrow">DEV PROTOTYPE</span>
      <strong>{{ activeVariant.label }}</strong>
    </div>
    <button
      class="prototype-switcher__arrow"
      type="button"
      title="下一个方案（→）"
      aria-label="下一个方案"
      @click="selectVariant(activeIndex + 1)"
    >
      <ArrowRight :size="16" aria-hidden="true" />
    </button>
  </nav>
</template>
