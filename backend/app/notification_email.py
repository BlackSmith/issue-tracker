"""Render ticket notification snapshots in the recipient's account language."""
import json
import re
from html import escape
from pathlib import Path

catalog = json.loads((Path(__file__).parent / "locales" / "cs.json").read_text(encoding="utf-8"))
quoted = r'"(?:[^"\\]|\\.)*"'
value = rf'(?:{quoted}|\[(?:{quoted}(?:, {quoted})*)?\]|Unassigned|No labels|Not set)'
metadata = re.compile(rf'^(status|type|priority|due date|labels|assignee)(?: from ({value}))? to ({value})(?:, |$)')


def translate(message, language, **parameters):
    template = catalog.get(message, message) if language == "cs" else message
    return template.format_map(parameters) if parameters else template


def summary_text(message, language):
    if language != "cs":
        return message

    def t(text, **parameters):
        return translate(text, language, **parameters)

    if message in {"created this work item", "added a comment", "published this ticket to project members",
                   "restricted this ticket to its author and assignee"}:
        return t(message)
    if message.startswith("uploaded "):
        return t("uploaded {filename}", filename=message[9:])
    if message.startswith("removed attachment "):
        return t("removed attachment {filename}", filename=message[19:])
    checklist = re.fullmatch(r'(checked|unchecked) checklist item #(\d+) "([\s\S]*)" in (a comment|the description)', message)
    if checklist:
        action, number, label, source = checklist.groups()
        return t('{action} checklist item #{number} "{label}" in {source}',
                 action=t(action), number=number, label=label, source=t(source))
    if not message.startswith("updated "):
        return message

    def display(field, raw):
        # Names and user-authored labels must never be translated as enum values.
        if raw.startswith(('"', '[')):
            if field not in {"status", "type", "priority"}:
                return raw
            return json.dumps(t(json.loads(raw)), ensure_ascii=False)
        return t(raw)

    rest, changes = message[8:], []
    while rest:
        match = metadata.match(rest)
        if match:
            field, previous, current = match.groups()
            changes.append(t("{field} from {previous} to {current}", field=t(field),
                             previous=display(field, previous), current=display(field, current)) if previous else
                           t("{field} to {current}", field=t(field), current=display(field, current)))
        else:
            match = re.match(r"^(title|description|status|type|priority|due date|labels|assignee)(?:, |$)", rest)
            if not match:
                return message
            changes.append(t(match[1]))
        rest = rest[match.end():]
    return t("updated {changes}", changes=", ".join(changes))


def render_notification(payload, language):
    if "reference" not in payload:
        # Queued messages from before structured snapshots still need delivery.
        body = payload["body"]
        link = re.search(r"^Open ticket: (https?://[^\s]+)$", body, re.MULTILINE)
        html = f'<p>{escape(body).replace(chr(10), "<br>")}</p>'
        if link:
            url = escape(link[1], quote=True)
            html += f'<p><a href="{url}">Open ticket</a></p>'
        return payload["subject"], body, html, "en"

    language = "cs" if language == "cs" else "en"
    heading = translate("New ticket" if payload["created"] else "Ticket updated", language)
    project_label = translate("Project", language)
    open_label = translate("Open ticket", language)
    subject = " ".join(f'[{payload["reference"]}] {heading}: {payload["title"]}'.splitlines())
    summary = f'{payload["actor"]} {summary_text(payload["summary"], language)}.'
    body = (f'{payload["reference"]}: {payload["title"]}\n{project_label}: {payload["project"]}\n\n'
            f'{summary}\n\n{open_label}: {payload["url"]}\n')
    url = escape(payload["url"], quote=True)
    html = (f'<!doctype html><html lang="{language}"><head><meta charset="utf-8"></head>'
            '<body style="font-family:Arial,sans-serif;line-height:1.5;color:#202124">'
            f'<h1 style="font-size:22px">{escape(heading)}</h1>'
            f'<h2 style="font-size:18px"><a href="{url}">{escape(payload["reference"])}: '
            f'{escape(payload["title"])}</a></h2>'
            f'<p>{escape(project_label)}: {escape(payload["project"])}</p>'
            f'<p style="white-space:pre-wrap">{escape(summary)}</p>'
            f'<p><a href="{url}" style="display:inline-block;padding:10px 16px;background:#166534;'
            f'color:#ffffff;text-decoration:none;border-radius:4px">{escape(open_label)}</a></p>'
            f'<p style="font-size:12px"><a href="{url}">{escape(payload["url"])}</a></p>'
            '</body></html>')
    return subject, body, html, language
