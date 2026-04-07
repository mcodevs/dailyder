from dailyder_bot.web.server import resolve_allowed_origin


def test_resolve_allowed_origin_matches_trailing_slash_variants() -> None:
    allowed_origin = resolve_allowed_origin(
        configured_value="https://dailyder-e8a28.web.app/",
        request_origin="https://dailyder-e8a28.web.app",
    )

    assert allowed_origin == "https://dailyder-e8a28.web.app"


def test_resolve_allowed_origin_matches_comma_separated_values() -> None:
    allowed_origin = resolve_allowed_origin(
        configured_value="https://example.com/, https://dailyder-e8a28.web.app/",
        request_origin="https://dailyder-e8a28.web.app",
    )

    assert allowed_origin == "https://dailyder-e8a28.web.app"
