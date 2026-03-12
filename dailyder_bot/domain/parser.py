from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class ParsedSubmissionItem:
    project_name: str
    task_name: str
    subtask_name: str | None = None


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
        blocks = [block.strip() for block in raw_text.strip().split("\n\n") if block.strip()]
        if not blocks:
            raise SubmissionParseError(
                [
                    "Kamida bitta vazifa kiriting.",
                    "Har blokda `Project:` va `Task:` bo'lishi kerak.",
                ]
            )

        items: list[ParsedSubmissionItem] = []
        errors: list[str] = []
        for index, block in enumerate(blocks, start=1):
            parsed = self._parse_block(block, index)
            if isinstance(parsed, ParsedSubmissionItem):
                items.append(parsed)
            else:
                errors.extend(parsed)

        if errors:
            raise SubmissionParseError(errors)
        return ParsedMorningSubmission(items=items)

    def _parse_block(self, block: str, index: int) -> ParsedSubmissionItem | list[str]:
        values: dict[str, str] = {}
        errors: list[str] = []

        for line in block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if ":" not in stripped:
                errors.append(f"{index}-blok: `{stripped}` satrida `:` yo'q.")
                continue
            key, value = stripped.split(":", 1)
            normalized_key = key.strip().lower()
            normalized_value = value.strip()
            if normalized_key not in (*self.REQUIRED_FIELDS, *self.OPTIONAL_FIELDS):
                errors.append(
                    f"{index}-blok: `{key.strip()}` maydoni qo'llab-quvvatlanmaydi. "
                    "Faqat `Project`, `Task`, `Subtask` ishlaydi."
                )
                continue
            if not normalized_value:
                errors.append(f"{index}-blok: `{key.strip()}` bo'sh bo'lmasligi kerak.")
                continue
            values[normalized_key] = normalized_value

        for field_name in self.REQUIRED_FIELDS:
            if field_name not in values:
                errors.append(f"{index}-blok: `{field_name.title()}: ...` maydoni topilmadi.")

        if errors:
            return errors

        return ParsedSubmissionItem(
            project_name=values["project"],
            task_name=values["task"],
            subtask_name=values.get("subtask"),
        )

