export interface CommonSubject {
  name: string
  domain: string
  is_major: boolean
}

/**
 * User-facing shortcuts for the subjects most schools add when preparing a
 * semester.  These are suggestions only: selecting one never writes data
 * until the user confirms the selection.
 */
export const COMMON_SUBJECTS: CommonSubject[] = [
  { name: '语文', domain: '语言与文学', is_major: true },
  { name: '数学', domain: '数学', is_major: true },
  { name: '英语', domain: '语言与文学', is_major: true },
  { name: '道德与法治', domain: '人文社会', is_major: false },
  { name: '历史', domain: '人文社会', is_major: false },
  { name: '地理', domain: '人文社会', is_major: false },
  { name: '物理', domain: '自然科学', is_major: false },
  { name: '化学', domain: '自然科学', is_major: false },
  { name: '生物', domain: '自然科学', is_major: false },
  { name: '信息技术', domain: '技术', is_major: false },
  { name: '体育', domain: '艺术与健康', is_major: false },
  { name: '音乐', domain: '艺术与健康', is_major: false },
  { name: '美术', domain: '艺术与健康', is_major: false },
  { name: '综合实践', domain: '综合实践', is_major: false },
]

// Keep the quick-add labels familiar while storing the canonical names used
// by the rest of the scheduling domain.
export const COMMON_SUBJECT_CANONICAL_NAMES: Record<string, string> = {
  生物: '生物学',
  信息: '信息科技',
  信息技术: '信息科技',
  体育: '体育与健康',
  综合实践: '综合实践活动',
}

export function canonicalCommonSubjectName(name: string): string {
  const trimmed = name.trim()
  return COMMON_SUBJECT_CANONICAL_NAMES[trimmed] ?? trimmed
}
