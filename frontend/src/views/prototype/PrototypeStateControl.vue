<script setup lang="ts">
import type { StatusMode } from './prototypeData'
import { stateOptions } from './prototypeData'

defineProps<{
  modelValue: StatusMode
}>()

const emit = defineEmits<{
  'update:modelValue': [value: StatusMode]
}>()
</script>

<template>
  <div class="prototype-state-control" aria-label="原型状态预览">
    <span class="state-control-label">预览状态</span>
    <div class="state-control-options" role="group">
      <button
        v-for="option in stateOptions"
        :key="option.key"
        class="state-control-option"
        :class="{ 'is-selected': modelValue === option.key }"
        type="button"
        :aria-pressed="modelValue === option.key"
        @click="emit('update:modelValue', option.key)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>
