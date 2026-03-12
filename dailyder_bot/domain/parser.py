from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(slots=True)
class ParsedSubmissionItem:
    project_name: str
    task_name: str
    subtask_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedMorningSubmission:
    items: list[ParsedSubmissionItem]


class SubmissionParseError(ValueError):
    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


class MorningSubmissionParser:
    REQUIRED_FIELDS = ("project", "task")
    OPTIONAL_FIELDS = ("subtask",)

    def parse(self, raw_text: str) -> ParsedMorningSubmission:
        lines = raw_text.splitlines()
        if not any(line.strip() for line in lines):
            raise SubmissionParseError(
                [
                    "Kamida bitta vazifa kiriting.",
                    "Kamida bitta `Project:` va `Task:` juftligi bo'lishi kerak.",
                ]
            )

        items: list[ParsedSubmissionItem] = []
        errors: list[str] = []
        current_project: str | None = None
        current_item: ParsedSubmissionItem | None = None

        for line_number, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue

            if ":" not in stripped:
                errors.append(f"{line_number}-qator: `{stripped}` satrida `:` yo'q.")
                continue

            key, value = stripped.split(":", 1)
            normalized_key = key.strip().lower()
            normalized_value = value.strip()

            if normalized_key not in (*self.REQUIRED_FIELDS, *self.OPTIONAL_FIELDS):
                errors.append(
                    f"{line_number}-qator: `{key.strip()}` maydoni qo'llab-quvvatlanmaydi. "
                    "Faqat `Project`, `Task`, `Subtask` ishlaydi."
                )
                continue

            if not normalized_value:
                errors.append(f"{line_number}-qator: `{key.strip()}` bo'sh bo'lmasligi kerak.")
                continue

            if normalized_key == "project":
                current_project = normalized_value
                current_item = None
                continue

            if normalized_key == "task":
                if current_project is None:
                    errors.append(f"{line_number}-qator: `Task` dan oldin `Project:` bo'lishi kerak.")
                    continue
                current_item = ParsedSubmissionItem(
                    project_name=current_project,
                    task_name=normalized_value,
                )
                items.append(current_item)
                continue

            if current_item is None:
                errors.append(f"{line_number}-qator: `Subtask` dan oldin `Task:` bo'lishi kerak.")
                continue
            current_item.subtask_names.append(normalized_value)

        if errors:
            raise SubmissionParseError(errors)
        if not items:
            raise SubmissionParseError(
                ["Kamida bitta `Task:` kiriting.", "`Task:` dan oldin `Project:` yozilishi kerak."]
            )
        return ParsedMorningSubmission(items=items)
