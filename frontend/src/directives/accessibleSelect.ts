import type { Directive } from 'vue'

const cleanupByElement = new WeakMap<HTMLElement, () => void>()

function applyAccessibleName(element: HTMLElement, label: string) {
  cleanupByElement.get(element)?.()

  const trigger = element.querySelector<HTMLElement>(
    '.n-base-selection-label, .n-base-selection-tags',
  )
  if (!trigger) return

  const input = trigger.querySelector<HTMLInputElement>('input')
  const nameTrigger = () => {
    input?.removeAttribute('aria-label')
    trigger.setAttribute('aria-label', label)
  }
  const nameInput = () => {
    trigger.removeAttribute('aria-label')
    input?.setAttribute('aria-label', label)
  }

  if (input) {
    input.addEventListener('focus', nameInput)
    input.addEventListener('blur', nameTrigger)
  }
  if (input && document.activeElement === input) nameInput()
  else nameTrigger()

  cleanupByElement.set(element, () => {
    input?.removeEventListener('focus', nameInput)
    input?.removeEventListener('blur', nameTrigger)
    input?.removeAttribute('aria-label')
    trigger.removeAttribute('aria-label')
  })
}

export const vAccessibleSelect: Directive<HTMLElement, string> = {
  mounted(element, binding) {
    applyAccessibleName(element, binding.value)
  },
  updated(element, binding) {
    applyAccessibleName(element, binding.value)
  },
  unmounted(element) {
    cleanupByElement.get(element)?.()
    cleanupByElement.delete(element)
  },
}
