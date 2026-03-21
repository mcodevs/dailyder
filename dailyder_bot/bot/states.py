from aiogram.fsm.state import State, StatesGroup


class MorningSubmissionState(StatesGroup):
    waiting_for_text = State()


class EveningUpdateState(StatesGroup):
    choosing_status = State()
    waiting_for_note = State()


class WarningFlowState(StatesGroup):
    waiting_for_username = State()
    waiting_for_reason = State()
