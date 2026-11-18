import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse as parseTemplate } from '@vue/compiler-dom'
import { parse } from '@vue/compiler-sfc'
import cs from '../src/locales/cs.json' with { type: 'json' }
import { activityText } from '../src/activity.ts'
import { dateOnly, dateTime, itemCount, language, t, translatedOptions, validationMessage } from '../src/i18n.ts'

test('language switching preserves enum wire values, interpolates safely and handles Czech plurals', () => {
  language.value = 'cs'
  assert.deepEqual(translatedOptions(['Open', 'High']), [{ value: 'Open', label: 'Otevřeno' }, { value: 'High', label: 'Vysoká' }])
  assert.equal(t('Continue with {provider}', { provider: 'Example {name}' }), 'Pokračovat přes Example {name}')
  assert.equal(t('Unknown message'), 'Unknown message')
  assert.equal(t('{0} labels selected'), 'Vybrané štítky: {0}')
  assert.deepEqual([0, 1, 2, 4, 5, 21].map(itemCount), ['0 ticketů', '1 ticket', '2 tickety', '4 tickety', '5 ticketů', '21 ticketů'])
  assert.equal(dateOnly('2026-11-17'), '17. 11. 2026')
  assert.equal(dateTime(null), 'Nikdy')
  language.value = 'en'
  assert.equal(t('Open'), 'Open')
  assert.deepEqual([0, 1, 2].map(itemCount), ['0 work items', '1 work item', '2 work items'])
})

test('generated activity is localized without translating embedded user content', () => {
  language.value = 'cs'
  assert.equal(activityText('created this work item'), 'vytvořil(a) tento ticket')
  assert.equal(activityText('uploaded Open.txt'), 'nahrál(a) Open.txt')
  assert.equal(activityText('updated status, labels'), 'změnil(a): Stav, Štítky')
  assert.equal(activityText('updated status from "Open" to "Done", assignee from "Open" to "Done", labels to ["High", "a, b"]'),
    'změnil(a): Stav z "Otevřeno" na "Hotovo", Řešitel z "Open" na "Done", Štítky na ["High", "a, b"]')
  assert.equal(activityText('checked checklist item #1 "Open, High" in a comment'), 'zaškrtl(a) položku seznamu úkolů č. 1 „Open, High“ v komentáři')
  assert.equal(activityText('unknown historical activity'), 'unknown historical activity')
  language.value = 'en'
  assert.equal(activityText('updated status from "Open" to "Done"'), 'updated status from "Open" to "Done"')
})

test('API validation reasons are translated without exposing English framework messages', () => {
  language.value = 'cs'
  assert.equal(validationMessage({ type: 'literal_error', msg: 'Input should be…', ctx: { expected: "'Low', 'Medium', 'High' or 'Urgent'" } }), 'Vyberte jednu z možností: Nízká, Střední, Vysoká, Naléhavá')
  assert.equal(validationMessage({ type: 'missing', msg: 'Field required' }), 'Toto pole je povinné.')
  assert.equal(validationMessage({ type: 'string_too_long', msg: 'String should have at most 200 characters' }), 'Hodnota není platná. Zkontrolujte formát a povolenou délku.')
  language.value = 'en'
})

test('catalog entries preserve interpolation placeholders', () => {
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort()
  for (const [key, translation] of Object.entries(cs)) {
    assert.ok(translation.trim(), key)
    assert.deepEqual(placeholders(translation), placeholders(key), key)
  }
})

test('Vue interface text and static accessible labels use translation calls', () => {
  const root = new URL('../src/', import.meta.url)
  const files = [...readdirSync(root).filter(file => file.endsWith('.vue')),
    ...readdirSync(new URL('components/', root)).filter(file => file.endsWith('.vue')).map(file => `components/${file}`)]
  const literalExceptions = new Set(['ISSUE TRACKER', 'Issue Tracker', 'KB', 'APP', 'https://example.com'])
  const failures = []
  function visit(node, file) {
    if (node.type === 2 && /[a-zA-Z]/.test(node.content) && !literalExceptions.has(node.content.trim())) failures.push(`${file}: ${node.content.trim()}`)
    if (node.type === 1) for (const prop of node.props) {
      if (prop.type === 6 && ['aria-label', 'title', 'header', 'placeholder', 'label'].includes(prop.name)
        && prop.value && /[a-zA-Z]/.test(prop.value.content) && !literalExceptions.has(prop.value.content)) failures.push(`${file}: ${prop.name}=${prop.value.content}`)
    }
    for (const child of node.children || []) visit(child, file)
  }
  for (const file of files) {
    const source = readFileSync(new URL(file, root), 'utf8')
    for (const match of source.matchAll(/\bt\(\s*('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")/g)) {
      const key = Function(`return ${match[1]}`)()
      if (!Object.hasOwn(cs, key)) failures.push(`${file}: missing Czech translation for ${key}`)
    }
    const { descriptor } = parse(source)
    if (descriptor.template) visit(parseTemplate(descriptor.template.content), file)
  }
  assert.deepEqual(failures, [])
})
