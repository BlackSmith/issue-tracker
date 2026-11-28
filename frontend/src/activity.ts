import { dateOnly, language, t } from './i18n.ts'

// Activity history predates localization. Parse only the application's exact
// generated grammar; never translate names, filenames, labels or task content.
const quoted = '"(?:[^"\\\\]|\\\\.)*"'
const value = `(?:${quoted}|\\[(?:${quoted}(?:, ${quoted})*)?\\]|Unassigned|No labels|No milestone|Not set)`
const metadata = new RegExp(`^(status|type|priority|due date|labels|assignee|milestone)(?: from (${value}))? to (${value})(?:, |$)`)
const fields: Record<string, string> = { status: 'Status', type: 'Type', priority: 'Priority', 'due date': 'Due date', labels: 'Labels', assignee: 'Assignee', milestone: 'Milestone', title: 'Title', description: 'Description' }

function display(field: string, raw: string): string {
  if (!raw.startsWith('"') && !raw.startsWith('[')) return t(raw)
  const parsed = JSON.parse(raw)
  if (field === 'labels' || field === 'assignee' || field === 'milestone') return raw
  return JSON.stringify(field === 'due date' ? dateOnly(parsed) : t(parsed))
}

export function activityText(message: string): string {
  if (language.value === 'en') return message
  if (message === 'created this work item') return t('created this work item')
  if (message === 'published this ticket to project members' || message === 'restricted this ticket to its author and assignee') return t(message)
  if (message.startsWith('uploaded ')) return t('uploaded {filename}', { filename: message.slice(9) })
  if (message.startsWith('removed attachment ')) return t('removed attachment {filename}', { filename: message.slice(19) })
  const checklist = /^(checked|unchecked) checklist item #(\d+) "([\s\S]*)" in (a comment|the description)$/.exec(message)
  if (checklist) return t('{action} checklist item #{number} "{label}" in {source}', {
    action: t(checklist[1]!), number: checklist[2]!, label: checklist[3]!, source: t(checklist[4]!),
  })
  if (!message.startsWith('updated ')) return message
  let rest = message.slice(8)
  const changes: string[] = []
  while (rest) {
    const match = metadata.exec(rest)
    if (match) {
      const field = match[1]!, previous = match[2], current = match[3]!
      changes.push(previous
        ? t('{field} from {previous} to {current}', { field: t(fields[field]!), previous: display(field, previous), current: display(field, current) })
        : t('{field} to {current}', { field: t(fields[field]!), current: display(field, current) }))
      rest = rest.slice(match[0].length)
    } else {
      const field = /^(title|description|status|type|priority|due date|labels|assignee)(?:, |$)/.exec(rest)
      if (!field) return message
      changes.push(t(fields[field[1]!]!))
      rest = rest.slice(field[0].length)
    }
  }
  return t('updated {changes}', { changes: changes.join(', ') })
}
