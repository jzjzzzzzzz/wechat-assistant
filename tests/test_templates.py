from pathlib import Path

import pytest

from src.templates import (
    MessageTemplate,
    TemplateError,
    load_templates,
    preview_template,
    render_template,
    render_template_body,
    template_from_row,
)


def test_render_template_body_with_placeholders() -> None:
    rendered = render_template_body("生日快乐，{name}，今天是 {date}", {"name": "Alice", "date": "07-05"})

    assert rendered == "生日快乐，Alice，今天是 07-05"


def test_render_template_body_missing_variable_fails_clearly() -> None:
    with pytest.raises(TemplateError, match="missing template variable"):
        render_template_body("生日快乐，{name}", {})


def test_disabled_template_cannot_render() -> None:
    template = MessageTemplate("disabled", "birthday", "Hi {name}", enabled=False)

    with pytest.raises(TemplateError, match="template is disabled"):
        render_template(template, {"name": "Alice"})


def test_template_from_row_validates_required_fields() -> None:
    with pytest.raises(TemplateError, match="name is required"):
        template_from_row({"name": "", "category": "birthday", "body": "Hi", "enabled": "true"})


def test_load_templates_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "message_templates.csv"
    csv_path.write_text(
        "name,category,body,enabled\n"
        "birthday_default,birthday,\"生日快乐，{name}\",true\n"
        "disabled,birthday,\"Hi\",false\n",
        encoding="utf-8",
    )

    templates = load_templates(csv_path)

    assert [template.name for template in templates] == ["birthday_default", "disabled"]
    assert templates[0].enabled is True
    assert templates[1].enabled is False


def test_preview_template_is_dry_run_only() -> None:
    template = MessageTemplate("birthday_default", "birthday", "生日快乐，{name}", enabled=True)

    preview = preview_template(template, {"name": "Alice"})

    assert preview == {
        "name": "birthday_default",
        "category": "birthday",
        "rendered_message": "生日快乐，Alice",
        "dry_run_only": True,
    }
