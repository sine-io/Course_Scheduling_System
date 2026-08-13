import { describe, expect, it } from 'vitest'
import { apiErrorMessage } from './client'

describe('apiErrorMessage', () => {
  it('prefers API detail and retains ordinary Error messages', () => {
    expect(apiErrorMessage({ detail: '后端说明' }, '默认说明')).toBe('后端说明')
    expect(apiErrorMessage(new Error('网络中断'), '默认说明')).toBe('网络中断')
  })

  it('reads structured API detail messages and falls back when absent', () => {
    expect(apiErrorMessage({ detail: { message: '冲突说明' } }, '默认说明')).toBe('冲突说明')
    expect(apiErrorMessage({}, '默认说明')).toBe('默认说明')
  })
})
