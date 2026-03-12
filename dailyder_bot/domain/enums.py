from __future__ import annotations

from enum import StrEnum


class DigestPeriod(StrEnum):
    AM = "am"
    PM = "pm"


class ItemStatus(StrEnum):
    COMPLETED = "completed"
    WARNING = "warning"
    BLOCKED = "blocked"
    DROPPED = "dropped"

    @property
    def emoji(self) -> str:
        mapping = {
            ItemStatus.COMPLETED: "✅",
            ItemStatus.WARNING: "⚠️",
            ItemStatus.BLOCKED: "🚫",
            ItemStatus.DROPPED: "🪓",
        }
        return mapping[self]

    @property
    def label_uz(self) -> str:
        mapping = {
            ItemStatus.COMPLETED: "Bajarildi",
            ItemStatus.WARNING: "Xavf bor",
            ItemStatus.BLOCKED: "To'siq bor",
            ItemStatus.DROPPED: "Bekor qilindi",
        }
        return mapping[self]

