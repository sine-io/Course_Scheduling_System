export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface PageRequest {
  page: number
  pageSize: number
}

export const DEFAULT_PAGE_SIZE = 20
export const PAGE_SIZE_OPTIONS = [20, 50, 100] as const
