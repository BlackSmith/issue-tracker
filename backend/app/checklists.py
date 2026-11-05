import hashlib
import re
from dataclasses import dataclass

from markdown_it import MarkdownIt

parser = MarkdownIt("commonmark")
task_marker = re.compile(r"^\[([ xX])\][ \t]+")
source_marker = re.compile(r"\[([ xX])\](?=[ \t\r\n]|$)")


@dataclass(frozen=True)
class ChecklistItem:
    offset: int
    checked: bool
    label: str


def content_version(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checklist_items(text: str) -> list[ChecklistItem]:
    """Find actual Markdown list tasks, excluding code, escapes and raw HTML.

    Token line maps locate the marker in the original source so toggling changes
    only its state character, preserving formatting, attachments and line endings.
    """
    # Match Markdown's CR/LF line maps; str.splitlines also splits Unicode
    # separators that remain ordinary paragraph content to the parser.
    lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text)
    offsets = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    tokens = parser.parse(text)
    tasks = []
    for index, token in enumerate(tokens):
        if token.type != "list_item_open":
            continue
        following = tokens[index + 1:index + 3]
        if len(following) != 2 or following[0].type != "paragraph_open" or following[1].type != "inline":
            continue
        inline = following[1]
        marker = task_marker.match(inline.content)
        if not marker or not inline.content[marker.end():].strip() or not inline.map:
            continue
        line_number = inline.map[0]
        original = source_marker.search(lines[line_number])
        if not original:
            continue
        plain = "".join(child.content if child.type in {"text", "code_inline", "image"}
                        else " " if child.type in {"softbreak", "hardbreak"} else ""
                        for child in inline.children or [])
        label = re.sub(r"^\[[ xX]\]\s*", "", plain)
        label = " ".join(label.split())[:300] or "(untitled)"
        tasks.append(ChecklistItem(offsets[line_number] + original.start() + 1, marker[1].lower() == "x", label))
    return tasks


def set_checklist_item(text: str, index: int, checked: bool) -> tuple[str, str, bool]:
    tasks = checklist_items(text)
    if index < 0 or index >= len(tasks):
        raise IndexError("Checklist item not found")
    task = tasks[index]
    if task.checked == checked:
        return text, task.label, False
    return text[:task.offset] + ("x" if checked else " ") + text[task.offset + 1:], task.label, True
