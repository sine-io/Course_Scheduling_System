<script setup lang="ts">
import { NPagination } from 'naive-ui'
import { PAGE_SIZE_OPTIONS } from '@/api/pagination'

withDefaults(defineProps<{
  page: number
  pageSize: number
  total: number
  loading?: boolean
  pageSizes?: number[]
  testId?: string
}>(), {
  loading: false,
  pageSizes: () => [...PAGE_SIZE_OPTIONS],
  testId: 'paged-list',
})

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()
</script>

<template>
  <nav class="paged-list-controls" :data-testid="`${testId}-controls`" aria-label="列表分页">
    <span class="paged-list-total" :data-testid="`${testId}-total`" aria-live="polite">
      {{ `共 ${total} 条` }}
    </span>
    <n-pagination
      class="paged-list-pagination"
      :page="page"
      :page-size="pageSize"
      :item-count="total"
      :page-sizes="pageSizes"
      :page-slot="5"
      :disabled="loading"
      show-size-picker
      show-quick-jumper
      @update:page="emit('update:page', $event)"
      @update:page-size="emit('update:pageSize', $event)"
    />
  </nav>
</template>

<style scoped>
.paged-list-controls {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px 16px;
  padding-top: 4px;
}

.paged-list-total {
  flex: 0 0 auto;
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 650;
}

.paged-list-pagination {
  min-width: 0;
  max-width: 100%;
  flex-wrap: wrap;
  row-gap: 8px;
}

@media (max-width: 560px) {
  .paged-list-controls {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
