export const defaultStatuses = ['Open', 'In progress']

type QueryValue = string | null | (string | null)[] | undefined

export function readFilterValues(value: QueryValue, defaults: readonly string[] = []): string[] {
  if (value === undefined) return [...defaults]
  return [...new Set((Array.isArray(value) ? value : [value]).filter((value): value is string => !!value))]
}

export function isDefaultStatusFilter(values: string[]): boolean {
  return values.length === defaultStatuses.length && defaultStatuses.every(status => values.includes(status))
}

export function statusFilterQuery(values: string[]): string[] | string | undefined {
  if (isDefaultStatusFilter(values)) return undefined
  // An explicit empty parameter distinguishes all statuses from the default view.
  return values.length ? values : ''
}
