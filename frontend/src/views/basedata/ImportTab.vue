<script setup lang="ts">
import ManualEntry from './ManualEntry.vue'

type ManualSection = 'subjects' | 'teachers' | 'classes' | 'rooms'

withDefaults(
  defineProps<{
    semesterId: number
    canEdit?: boolean
    canDelete?: boolean
    canManageAccounts?: boolean
    initialManualSection?: ManualSection
  }>(),
  {
    canEdit: true,
    canDelete: false,
    canManageAccounts: false,
    initialManualSection: 'subjects',
  },
)

const emit = defineEmits<{ imported: [] }>()
</script>

<template>
  <ManualEntry
    :semester-id="semesterId"
    :can-edit="canEdit"
    :can-delete="canDelete"
    :can-manage-accounts="canManageAccounts"
    :initial-section="initialManualSection"
    @changed="emit('imported')"
  />
</template>
