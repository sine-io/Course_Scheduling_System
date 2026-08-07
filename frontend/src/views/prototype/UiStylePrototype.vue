<script setup lang="ts">
import { AlertTriangle, CheckCircle2, X } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PrototypeSwitcher from './PrototypeSwitcher.vue'
import VariantContextRail from './VariantContextRail.vue'
import VariantFocusCanvas from './VariantFocusCanvas.vue'
import VariantWorkbenchRail from './VariantWorkbenchRail.vue'
import './prototype.css'
import type { CourseCell, StatusMode, ViewKey } from './prototypeData'
import { variantNames } from './prototypeData'

// THROWAWAY PROTOTYPE
// Question: does the reference visual language support this product's real density and responsive shell?
// Three variants of a representative scheduling shell, switchable via ?variant=A|B|C.

const route = useRoute()
const router = useRouter()

const variants = [
  { key: 'A', name: variantNames.A, component: VariantWorkbenchRail },
  { key: 'B', name: variantNames.B, component: VariantContextRail },
  { key: 'C', name: variantNames.C, component: VariantFocusCanvas },
]

const activeView = ref<ViewKey>('dashboard')
const drawerOpen = ref(false)
const collapsed = ref(false)
const statusMode = ref<StatusMode>('normal')
const selectedCourseKey = ref<string | null>(null)
const confirmOpen = ref(false)
const toastMessage = ref('')
let toastTimer: number | undefined

function normalizeVariant(value: unknown): string {
  const candidate = Array.isArray(value) ? value[0] : value
  return variants.some((item) => item.key === candidate) ? String(candidate) : 'A'
}

const currentKey = computed(() => normalizeVariant(route.query.variant))
const currentVariant = computed(() => variants.find((item) => item.key === currentKey.value) ?? variants[0])

function setVariant(key: string) {
  const next = normalizeVariant(key)
  void router.replace({ query: { ...route.query, variant: next } })
  activeView.value = 'dashboard'
  drawerOpen.value = false
  selectedCourseKey.value = null
}

function navigate(view: ViewKey) {
  activeView.value = view
  drawerOpen.value = false
  selectedCourseKey.value = null
}

function showToast(message: string) {
  toastMessage.value = message
  if (toastTimer !== undefined) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toastMessage.value = ''
    toastTimer = undefined
  }, 2600)
}

function selectCourse(course: CourseCell) {
  selectedCourseKey.value = selectedCourseKey.value === course.id ? null : course.id
  showToast(`${course.subject} · ${course.teacher} · ${course.room}`)
}

function confirmPublish() {
  confirmOpen.value = false
  showToast('已生成发布确认草稿，正式课表尚未变更')
}

function syncViewport() {
  collapsed.value = window.innerWidth <= 1100
  if (window.innerWidth > 767) drawerOpen.value = false
}

watch(() => route.query.variant, () => {
  activeView.value = 'dashboard'
  drawerOpen.value = false
  selectedCourseKey.value = null
})

onMounted(() => {
  document.body.classList.add('prototype-body')
  syncViewport()
  window.addEventListener('resize', syncViewport)
})

onBeforeUnmount(() => {
  document.body.classList.remove('prototype-body')
  window.removeEventListener('resize', syncViewport)
  if (toastTimer !== undefined) window.clearTimeout(toastTimer)
})
</script>

<template>
  <div class="prototype-page">
    <component
      :is="currentVariant.component"
      :active-view="activeView"
      :drawer-open="drawerOpen"
      :collapsed="collapsed"
      :status-mode="statusMode"
      :selected-course-key="selectedCourseKey"
      @navigate="navigate"
      @toggle-drawer="drawerOpen = true"
      @close-drawer="drawerOpen = false"
      @toggle-collapse="collapsed = !collapsed"
      @set-status="statusMode = $event"
      @select-course="selectCourse"
      @toast="showToast"
      @open-confirm="confirmOpen = true"
    />

    <PrototypeSwitcher
      :variants="variants"
      :current="currentKey"
      :current-name="currentVariant.name"
      :active-view="activeView"
      @change="setVariant"
    />

    <div v-if="toastMessage" class="prototype-toast" role="status" aria-live="polite">
      <CheckCircle2 :size="16" aria-hidden="true" />
      <span>{{ toastMessage }}</span>
    </div>

    <div v-if="confirmOpen" class="prototype-modal-backdrop" @click.self="confirmOpen = false">
      <section class="prototype-modal" role="dialog" aria-modal="true" aria-labelledby="prototype-confirm-title">
        <header class="prototype-modal-header">
          <span class="prototype-modal-icon"><AlertTriangle :size="18" aria-hidden="true" /></span>
          <div><h2 id="prototype-confirm-title">确认检查并生成发布草稿？</h2><p>这一步只演示正式操作前的确认层，不会调用 API，也不会修改真实课表。</p></div>
          <button class="prototype-icon-button prototype-modal-close" type="button" aria-label="关闭确认框" title="关闭" @click="confirmOpen = false"><X :size="17" aria-hidden="true" /></button>
        </header>
        <div class="prototype-modal-body">
          <ul class="prototype-modal-list"><li><CheckCircle2 :size="14" />当前版本：2026—2027 秋季学期 · 草稿 v3.2</li><li><AlertTriangle :size="14" />仍有 1 条教师时间规则冲突需要人工复核</li><li><CheckCircle2 :size="14" />确认后只生成待发布草稿，不通知教师和班级</li></ul>
          <div class="prototype-modal-actions"><button class="proto-button" type="button" @click="confirmOpen = false">取消</button><button class="proto-button danger" type="button" @click="confirmPublish">确认生成草稿</button></div>
        </div>
      </section>
    </div>
  </div>
</template>

