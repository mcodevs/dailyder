from dailyder_bot.domain.parser import MorningSubmissionParser, SubmissionParseError


def test_parser_parses_multiple_blocks() -> None:
    parser = MorningSubmissionParser()

    parsed = parser.parse(
        """
        Project: TvRain
        Task: IOS bug fix
        Subtask: iphone vs ipad

        Project: AnorDelivery
        Task: Release
        """
    )

    assert len(parsed.items) == 2
    assert parsed.items[0].project_name == "TvRain"
    assert parsed.items[0].task_name == "IOS bug fix"
    assert parsed.items[0].subtask_names == ["iphone vs ipad"]
    assert parsed.items[1].project_name == "AnorDelivery"
    assert parsed.items[1].subtask_names == []


def test_parser_parses_multiple_tasks_under_one_project() -> None:
    parser = MorningSubmissionParser()

    parsed = parser.parse(
        """
        Project: TvRain
        Task: IOS bug fix
        Subtask: iphone bug
        Subtask: ipad bug
        Task: Release
        Task: Analytics review
        """
    )

    assert len(parsed.items) == 3
    assert [item.project_name for item in parsed.items] == ["TvRain", "TvRain", "TvRain"]
    assert [item.task_name for item in parsed.items] == [
        "IOS bug fix",
        "Release",
        "Analytics review",
    ]
    assert parsed.items[0].subtask_names == ["iphone bug", "ipad bug"]
    assert parsed.items[1].subtask_names == []


def test_parser_reports_field_level_errors() -> None:
    parser = MorningSubmissionParser()

    try:
        parser.parse(
            """
            Task: Orphan task
            Project:
            Foo: bar
            """
        )
    except SubmissionParseError as exc:
        assert any("Task` dan oldin `Project" in error for error in exc.errors)
        assert any("Project" in error for error in exc.errors)
        assert any("qo'llab-quvvatlanmaydi" in error for error in exc.errors)
    else:
        raise AssertionError("SubmissionParseError was expected")
