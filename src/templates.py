"""Local message template rendering and preview helpers."""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MESSAGE_TEMPLATES_PATH = PROJECT_ROOT / "data" / "message_templates.csv"


class TemplateError(ValueError):
    """Raised when a local message template is invalid or cannot be rendered."""


@dataclass(frozen=True)
class MessageTemplate:
    name: str
    category: str
    body: str
    enabled: bool = True

    def placeholders(self) -> set[str]:
        formatter = string.Formatter()
        fields = set()
        for _literal, field_name, _format_spec, _conversion in formatter.parse(self.body):
            if field_name:
                fields.add(field_name.split(".", 1)[0].split("[", 1)[0])
        return fields


def _is_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def validate_template_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("name", "category", "body"):
        if not str(row.get(key, "")).strip():
            errors.append(f"{key} is required")
    return errors


def template_from_row(row: dict[str, Any]) -> MessageTemplate:
    errors = validate_template_row(row)
    if errors:
        raise TemplateError("; ".join(errors))
    return MessageTemplate(
        name=str(row["name"]).strip(),
        category=str(row["category"]).strip(),
        body=str(row["body"]),
        enabled=_is_enabled(row.get("enabled", True)),
    )


def load_templates(path: str | Path = MESSAGE_TEMPLATES_PATH) -> list[MessageTemplate]:
    template_path = Path(path)
    if not template_path.exists():
        template_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["name", "category", "body", "enabled"]).to_csv(
            template_path, index=False, encoding="utf-8"
        )
        return []

    dataframe = pd.read_csv(template_path, dtype=str).fillna("")
    required = {"name", "category", "body", "enabled"}
    missing = required - set(dataframe.columns)
    if missing:
        raise TemplateError(f"message template file missing columns: {', '.join(sorted(missing))}")
    return [template_from_row(row) for row in dataframe.to_dict(orient="records")]


def render_template_body(body: str, context: dict[str, Any]) -> str:
    template = MessageTemplate(name="_inline", category="_inline", body=body)
    missing = sorted(template.placeholders() - set(context))
    if missing:
        raise TemplateError(f"missing template variable(s): {', '.join(missing)}")
    return body.format(**context)


def render_template(template: MessageTemplate, context: dict[str, Any]) -> str:
    if not template.enabled:
        raise TemplateError(f"template is disabled: {template.name}")
    return render_template_body(template.body, context)


def preview_template(template: MessageTemplate, context: dict[str, Any]) -> dict[str, Any]:
    rendered = render_template(template, context)
    return {
        "name": template.name,
        "category": template.category,
        "rendered_message": rendered,
        "dry_run_only": True,
    }
