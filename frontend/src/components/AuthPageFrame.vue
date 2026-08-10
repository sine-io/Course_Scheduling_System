<script setup lang="ts">
import { CalendarDays, ShieldCheck } from '@lucide/vue'

defineProps<{
  eyebrow: string
  title: string
  description: string
  contextTitle: string
  contextDescription: string
}>()
</script>

<template>
  <div class="auth-page">
    <aside class="auth-context" aria-label="产品信息">
      <div class="auth-brand">
        <span class="auth-brand-mark" aria-hidden="true">
          <CalendarDays :size="21" :stroke-width="1.9" />
        </span>
        <span>
          <strong>教务排课</strong>
          <small>排课 · 调课 · 代课</small>
        </span>
      </div>

      <div class="auth-context-copy">
        <p class="auth-context-eyebrow">{{ '学校教务工作台' }}</p>
        <h1>{{ contextTitle }}</h1>
        <p>{{ contextDescription }}</p>
      </div>

      <div class="auth-context-note">
        <ShieldCheck :size="18" :stroke-width="1.9" aria-hidden="true" />
        <span>{{ '会话与权限由学校系统统一管理' }}</span>
      </div>
    </aside>

    <main class="auth-main">
      <section class="auth-panel" aria-labelledby="auth-panel-title">
        <header class="auth-panel-header">
          <p class="auth-eyebrow">{{ eyebrow }}</p>
          <h2 id="auth-panel-title">{{ title }}</h2>
          <p>{{ description }}</p>
        </header>
        <slot />
      </section>
    </main>
  </div>
</template>

<style>
.auth-page {
  display: grid;
  min-height: 100svh;
  grid-template-columns: minmax(280px, 340px) minmax(420px, 1fr);
  background: var(--app-background);
  color: var(--app-text);
}

.auth-context {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  justify-content: space-between;
  gap: 32px;
  padding: 40px 32px;
  border-right: 1px solid var(--app-border);
  background: var(--app-surface);
  color: var(--app-text);
}

.auth-brand,
.auth-brand > span:last-child,
.auth-context-note {
  display: flex;
  align-items: center;
}

.auth-brand { gap: 11px; }
.auth-brand > span:last-child { flex-direction: column; align-items: flex-start; gap: 2px; }
.auth-brand strong { font-size: 18px; letter-spacing: 0; }
.auth-brand small { color: var(--app-text-muted); font-size: 11px; }

.auth-brand-mark {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid var(--app-primary);
  border-radius: var(--app-radius-sm);
  background: var(--app-primary);
  color: var(--app-on-primary);
}

.auth-context-copy { max-width: 390px; }
.auth-context-eyebrow,
.auth-eyebrow {
  margin: 0 0 10px;
  color: var(--app-primary-strong);
  font-size: 12px;
  font-weight: 700;
}

.auth-context-copy h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.25;
  letter-spacing: 0;
}

.auth-context-copy > p:last-child {
  max-width: 34em;
  margin: 16px 0 0;
  color: var(--app-text-muted);
  font-size: 14px;
  line-height: 1.7;
}

.auth-context-note {
  gap: 9px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.auth-main {
  display: grid;
  min-width: 0;
  place-items: center;
  padding: clamp(20px, 5vw, 72px);
}

.auth-panel {
  width: min(100%, 480px);
  padding: clamp(24px, 4vw, 40px);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-lg);
}

.auth-panel-header { margin-bottom: 28px; }
.auth-panel-header h2 { margin: 0; font-size: 28px; line-height: 1.25; }
.auth-panel-header > p:last-child { margin: 10px 0 0; color: var(--app-text-muted); font-size: 14px; line-height: 1.65; }
.auth-eyebrow { margin-bottom: 8px; color: var(--app-primary-strong); }

.auth-form { display: grid; gap: 4px; }
.auth-form .n-form-item-label__text { font-weight: 600; }
.auth-form .n-input { min-height: 42px; }
.auth-form .n-button { min-height: 44px; margin-top: 8px; font-weight: 650; }

.auth-feedback {
  display: grid;
  gap: 3px;
  min-height: 0;
  margin: 4px 0 14px;
  padding: 10px 12px;
  border: 1px solid var(--app-danger);
  border-radius: var(--app-radius-sm);
  background: var(--app-danger-soft);
  color: var(--app-danger);
  font-size: 13px;
  line-height: 1.5;
}

.auth-feedback.is-success {
  border-color: var(--app-success);
  background: var(--app-success-soft);
  color: var(--app-success);
}

.auth-feedback.is-warning {
  border-color: var(--app-warning);
  background: var(--app-warning-soft);
  color: var(--app-warning);
}

.auth-note {
  margin: 18px 0 0;
  color: var(--app-text-faint);
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 820px) {
  .auth-page { grid-template-columns: 1fr; }
  .auth-context { min-height: auto; gap: 18px; padding: 22px 24px; border-right: 0; border-bottom: 1px solid var(--app-border); }
  .auth-context-copy { max-width: 620px; }
  .auth-context-copy h1 { font-size: 26px; }
  .auth-context-copy > p:last-child { margin-top: 8px; font-size: 13px; }
  .auth-context-note { margin-top: 2px; }
  .auth-main { padding: 28px 20px 44px; }
}

@media (max-width: 480px) {
  .auth-context { gap: 16px; padding: 18px 16px; }
  .auth-brand strong { font-size: 16px; }
  .auth-context-copy h1 { font-size: 23px; }
  .auth-context-copy > p:last-child { font-size: 12px; line-height: 1.6; }
  .auth-main { padding: 16px; align-items: start; }
  .auth-panel { padding: 22px 18px 24px; }
  .auth-panel-header { margin-bottom: 22px; }
  .auth-panel-header h2 { font-size: 24px; }
}
</style>
