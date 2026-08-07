<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon: Component
  label: string
  active?: boolean
  compact?: boolean
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <button
    class="prototype-icon-button"
    :class="{ 'is-active': active, 'is-compact': compact }"
    type="button"
    :aria-label="label"
    :title="label"
    @click="$emit('click')"
  >
    <component :is="icon" :size="compact ? 16 : 18" :stroke-width="1.8" aria-hidden="true" />
  </button>
</template>
