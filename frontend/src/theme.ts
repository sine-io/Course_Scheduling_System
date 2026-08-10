import type { GlobalThemeOverrides } from 'naive-ui'

// Primary and interactive states all keep at least 4.5:1 contrast with white text.
export const PRIMARY = '#2864dc'
export const PRIMARY_HOVER = '#2358c4'
export const PRIMARY_PRESSED = '#1b47a3'
export const WARNING_ACTION = '#8f4f00'
export const WARNING_ACTION_HOVER = '#743f00'
export const WARNING_ACTION_PRESSED = '#5f3300'

const SYSTEM_FONT = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'

export const themeOverrides: GlobalThemeOverrides = {
  common: {
    fontFamily: SYSTEM_FONT,
    borderRadius: '6px',
    borderRadiusSmall: '4px',
    primaryColor: PRIMARY,
    primaryColorHover: PRIMARY_HOVER,
    primaryColorPressed: PRIMARY_PRESSED,
    primaryColorSuppl: PRIMARY_HOVER,
    infoColor: PRIMARY,
    infoColorHover: PRIMARY_HOVER,
    infoColorPressed: PRIMARY_PRESSED,
    infoColorSuppl: PRIMARY_HOVER,
    successColor: '#16764f',
    successColorHover: '#116442',
    successColorPressed: '#0d5136',
    successColorSuppl: '#116442',
    // Keep the warning fill used by existing status tags; warning text and
    // controls provide the darker contrast where a solid action is needed.
    warningColor: '#f0a020',
    warningColorHover: '#d99016',
    warningColorPressed: '#c47e0f',
    warningColorSuppl: '#d99016',
    errorColor: '#c2383f',
    errorColorHover: '#aa2d34',
    errorColorPressed: '#8d242a',
    errorColorSuppl: '#aa2d34',
    bodyColor: '#f3f6fa',
    baseColor: '#ffffff',
    cardColor: '#ffffff',
    modalColor: '#ffffff',
    popoverColor: '#ffffff',
    tableColor: '#ffffff',
    inputColor: '#ffffff',
    textColor1: '#172033',
    textColor2: '#374257',
    textColor3: '#596579',
    borderColor: '#dfe5ed',
    dividerColor: '#e6ebf1',
    hoverColor: '#f3f6fa',
    pressedColor: '#eef2f7',
    tableHeaderColor: '#f8fafc',
    tableColorHover: '#f4f7fc',
    boxShadow1: '0 1px 2px rgba(23, 32, 51, 0.05)',
    boxShadow2: '0 5px 16px rgba(23, 32, 51, 0.08)',
    boxShadow3: '0 16px 40px rgba(23, 32, 51, 0.18)',
  },
  Button: {
    colorWarning: WARNING_ACTION,
    colorHoverWarning: WARNING_ACTION_HOVER,
    colorPressedWarning: WARNING_ACTION_PRESSED,
    colorFocusWarning: WARNING_ACTION_HOVER,
    colorDisabledWarning: WARNING_ACTION,
    textColorWarning: '#ffffff',
    textColorHoverWarning: '#ffffff',
    textColorPressedWarning: '#ffffff',
    textColorFocusWarning: '#ffffff',
    textColorDisabledWarning: '#ffffff',
  },
}
