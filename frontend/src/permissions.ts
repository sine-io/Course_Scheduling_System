/**
 * 前端只用于对齐入口和控件状态；真正的授权仍由后端依赖执行。
 * 角色权限取并集，admin 明确列入每个业务动作的允许集合。
 */

export const CORE_VIEW_ROLES = ['admin', 'scheduler', 'director'] as const
export const CORE_EDIT_ROLES = ['admin', 'scheduler'] as const
export const BATCH_EXPORT_ROLES = ['admin', 'scheduler'] as const
export const DAILY_OPERATOR_ROLES = ['admin', 'scheduler', 'director'] as const
export const DAILY_USER_ROLES = ['admin', 'scheduler', 'director', 'teacher'] as const

export function hasAnyRole(
  userRoles: readonly string[] | null | undefined,
  requiredRoles: readonly string[],
): boolean {
  return requiredRoles.some((role) => userRoles?.includes(role) ?? false)
}

export function canViewCore(userRoles: readonly string[] | null | undefined): boolean {
  return hasAnyRole(userRoles, CORE_VIEW_ROLES)
}

export function canEditCore(userRoles: readonly string[] | null | undefined): boolean {
  return hasAnyRole(userRoles, CORE_EDIT_ROLES)
}

export function canBatchExport(userRoles: readonly string[] | null | undefined): boolean {
  return hasAnyRole(userRoles, BATCH_EXPORT_ROLES)
}

export function canOperateDaily(userRoles: readonly string[] | null | undefined): boolean {
  return hasAnyRole(userRoles, DAILY_OPERATOR_ROLES)
}

export function canUseDaily(userRoles: readonly string[] | null | undefined): boolean {
  return hasAnyRole(userRoles, DAILY_USER_ROLES)
}
