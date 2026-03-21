from dailyder_bot.bot import keyboards
from dailyder_bot.bot.callbacks import MenuCallback


def _button_texts(markup) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard]


def _button_callbacks(markup) -> list[list[str | None]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


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
