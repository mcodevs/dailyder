from dailyder_bot.bot import keyboards
from dailyder_bot.bot.callbacks import MenuCallback
from dailyder_bot.db.models import SubmissionItem, SubmissionSubtask


def _button_texts(markup) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard]


def _button_callbacks(markup) -> list[list[str | None]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def _button_web_app_urls(markup) -> list[list[str | None]]:
    return [
        [button.web_app.url if button.web_app is not None else None for button in row]
        for row in markup.inline_keyboard
    ]


def test_main_menu_keyboard_includes_top_level_sections() -> None:
    markup = keyboards.main_menu_keyboard(is_admin=False)

    assert _button_texts(markup) == [
        [keyboards.MENU_TODAY, keyboards.MENU_PM],
        [keyboards.MENU_HELP],
    ]
    assert _button_callbacks(markup) == [
        [
            MenuCallback(action="today").pack(),
            MenuCallback(action="pm").pack(),
        ],
        [MenuCallback(action="help").pack()],
    ]


def test_main_menu_keyboard_includes_mini_app_row_when_url_present() -> None:
    markup = keyboards.main_menu_keyboard(
        is_admin=False,
        mini_app_url="https://mini.dailyder.uz",
    )

    assert _button_texts(markup) == [
        [keyboards.MENU_TODAY, keyboards.MENU_PM],
        [keyboards.MENU_HELP],
        [keyboards.MENU_MINI_APP],
    ]
    assert _button_web_app_urls(markup)[-1] == ["https://mini.dailyder.uz"]


def test_with_main_menu_appends_navigation_rows_and_admin_button() -> None:
    base_markup = keyboards.today_summary_keyboard(has_items=False)

    markup = keyboards.with_main_menu(base_markup, is_admin=True)

    assert _button_texts(markup)[0] == ["Task qo'shish", "Matndan import"]
    assert _button_texts(markup)[-3:] == [
        [keyboards.MENU_TODAY, keyboards.MENU_PM],
        [keyboards.MENU_HELP],
        [keyboards.MENU_ADMIN],
    ]
    assert _button_callbacks(markup)[-1] == [MenuCallback(action="admin").pack()]


def test_admin_menu_keyboard_keeps_admin_actions_and_navigation() -> None:
    markup = keyboards.admin_menu_keyboard()

    texts = _button_texts(markup)

    assert texts[:3] == [
        ["Holat", "Pending"],
        ["Metrikalar", "Developerlar"],
        ["AM eslatma", "PM eslatma"],
    ]
    assert texts[-3:] == [
        [keyboards.MENU_TODAY, keyboards.MENU_PM],
        [keyboards.MENU_HELP],
        [keyboards.MENU_ADMIN],
    ]


def test_pm_item_detail_keyboard_callback_data_stays_within_telegram_limit() -> None:
    item_id = "a" * 32
    subtask_id = "b" * 32
    item = SubmissionItem(
        id=item_id,
        submission_id="s" * 32,
        sort_order=1,
        project_name="Dailyder",
        task_name="Optimize bot",
        subtask_name=None,
    )
    item.subtasks = [
        SubmissionSubtask(
            id=subtask_id,
            submission_item_id=item_id,
            sort_order=1,
            subtask_name="Optimize UX",
            status=None,
        )
    ]

    markup = keyboards.pm_item_detail_keyboard(item=item, current_status=None)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]

    assert callbacks
    assert all(len(callback.encode()) <= 64 for callback in callbacks)


def test_pm_status_keyboard_callback_data_stays_within_telegram_limit() -> None:
    markup = keyboards.pm_status_keyboard(target_type="subtask", target_id="f" * 32)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]

    assert callbacks
    assert all(len(callback.encode()) <= 64 for callback in callbacks)
