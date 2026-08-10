import { describe, expect, it } from 'vitest'

import {
  PRIMARY,
  PRIMARY_HOVER,
  PRIMARY_PRESSED,
  WARNING_ACTION,
  WARNING_ACTION_HOVER,
  WARNING_ACTION_PRESSED,
} from './theme'

function relativeLuminance(hex: string) {
  const channels = hex.match(/[\da-f]{2}/gi)?.map((value) => Number.parseInt(value, 16) / 255)
  if (!channels || channels.length !== 3) throw new Error(`Invalid color: ${hex}`)

  const [red, green, blue] = channels.map((channel) => (
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ))
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}

function contrastWithWhite(hex: string) {
  return 1.05 / (relativeLuminance(hex) + 0.05)
}

describe('应用主题对比度', () => {
  it.each([
    ['primary', PRIMARY],
    ['primary hover', PRIMARY_HOVER],
    ['primary pressed', PRIMARY_PRESSED],
    ['warning action', WARNING_ACTION],
    ['warning action hover', WARNING_ACTION_HOVER],
    ['warning action pressed', WARNING_ACTION_PRESSED],
  ])('%s 的白色文字达到 WCAG AA', (_state, color) => {
    expect(contrastWithWhite(color)).toBeGreaterThanOrEqual(4.5)
  })
})
