"""Unified auto-reply safety gate.

should_auto_reply(context) is the single point of truth before any
auto-reply is sent.  It checks all conditions in order and returns
(allowed: bool, reason: str).  Every decision — allow or block — is
logged so the operator can see exactly why a message was or was not sent.

Decision order (all must pass to allow sending):
  1. Owner status is "offline" (OFF) via live screen evidence or DB evidence
  2. Optional Dock safety says the WeChat Dock icon has an unread red badge
  3. Sender is not a group chat (bracket+number pattern, blocklist keywords)
  4. Sender is in the private_chat_whitelist (if require_private_chat_whitelist)
  5. OCR confidence >= min_ocr_confidence
  6. Target is in the allowed contacts list (for real sends)
  7. Global dry_run flag (if True, gate allows but caller must not actually send)

Safe default: when status is unknown, only a config default, or any check fails → return (False, reason).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.auto_reply_policy import auto_reply_config, classify_chat_sender
from src.dock_unread_detector import dock_unread_config
from src.owner_status import OwnerStatusStore


LOGGER = logging.getLogger(__name__)

_SAFE_TEST_CONTACTS = frozenset({"文件传输助手", "File Transfer"})


@dataclass(frozen=True)
class GateDecision:
    """Result of should_auto_reply()."""

    allowed: bool
    reason: str
    sender: str
    system_status: str  # owner status: "online", "offline", or "unknown"
    is_dry_run: bool

    def __bool__(self) -> bool:
        return self.allowed


def _get_current_system_status(config: dict[str, Any], store: OwnerStatusStore | None) -> str:
    """Read current system status from DB.

    Config defaults are not live status evidence, so missing DB status returns
    unknown and blocks sending.
    """
    try:
        if store is not None:
            record = store.get_database_status()
            return record.status if record is not None else "unknown"
        with OwnerStatusStore(config.get("database_path")) as s:
            record = s.get_database_status()
            return record.status if record is not None else "unknown"
    except Exception as exc:
        LOGGER.error("send_gate: failed to read system status from DB: %s", exc)
        return "unknown"


def should_auto_reply(
    sender: str,
    config: dict[str, Any],
    *,
    ocr_confidence: float = 1.0,
    owner_status_store: OwnerStatusStore | None = None,
    override_status: str | None = None,
    dock_has_unread: bool | None = None,
    dock_evidence: str | None = None,
) -> GateDecision:
    """Evaluate whether an auto-reply to *sender* is permitted right now.

    Args:
        sender: The chat name / contact to reply to.
        config: Project config dict (from load_config()).
        ocr_confidence: Confidence of the OCR detection that found this sender.
        owner_status_store: Open OwnerStatusStore to reuse; if None, opens a new one.
        override_status: Pass "online"/"offline"/"unknown" to bypass DB lookup (tests).
        dock_has_unread: Optional live Dock red-badge signal.
        dock_evidence: Short diagnostic string for logging.

    Returns:
        GateDecision(allowed, reason, sender, system_status, is_dry_run)
    """
    ar = auto_reply_config(config)
    # Real-send mode requires BOTH dry_run=False AND allow_real_send=True.
    # Any other combination is dry-run (safe default).
    is_dry_run = (
        bool(config.get("dry_run", True))
        or bool(ar.get("dry_run", True))
        or not bool(config.get("allow_real_send", False))
    )

    # ── Gate 1: owner status must be "offline" (OFF) ────────────────────────
    if override_status is not None:
        system_status = str(override_status).strip().lower()
    else:
        system_status = _get_current_system_status(config, owner_status_store)

    if system_status == "unknown":
        reason = "system_status_unknown: cannot read OL/OFF owner status — safe default: no send"
        LOGGER.warning("send_gate BLOCKED. sender=%r %s", sender, reason)
        return GateDecision(False, reason, sender, system_status, is_dry_run)

    if system_status != "offline":
        reason = f"owner_online: system_status={system_status}; owner is online, no auto-reply"
        LOGGER.info("send_gate BLOCKED. sender=%r %s", sender, reason)
        return GateDecision(False, reason, sender, system_status, is_dry_run)

    # ── Gate 2: optional Dock unread safety ──────────────────────────────────
    dock_cfg = dock_unread_config(config)
    if bool(dock_cfg.get("enabled", False)) and bool(dock_cfg.get("require_for_auto_reply", False)):
        if dock_has_unread is not True:
            reason = (
                "dock_unread_not_detected: WeChat Dock red badge is not confirmed"
                f"{f' ({dock_evidence})' if dock_evidence else ''}"
            )
            LOGGER.info("send_gate BLOCKED. sender=%r %s", sender, reason)
            return GateDecision(False, reason, sender, system_status, is_dry_run)

    # ── Gate 3: sender classification (group chat / blocklist / whitelist) ───
    classification = classify_chat_sender(sender, ar)
    if not classification.is_private:
        reason = f"sender_blocked: {classification.reason or 'not a private chat'} (category={classification.category})"
        LOGGER.info("send_gate BLOCKED. sender=%r %s", sender, reason)
        return GateDecision(False, reason, sender, system_status, is_dry_run)

    # ── Gate 4: OCR confidence ────────────────────────────────────────────────
    min_conf = float(ar.get("min_ocr_confidence", 0.65))
    if ocr_confidence < min_conf:
        reason = f"ocr_confidence_too_low: {ocr_confidence:.3f} < {min_conf:.3f}"
        LOGGER.info("send_gate BLOCKED. sender=%r %s", sender, reason)
        return GateDecision(False, reason, sender, system_status, is_dry_run)

    # ── Gate 5: safe-send target check (for real sends) ───────────────────────
    if not is_dry_run:
        allowed_real = set(_SAFE_TEST_CONTACTS)
        extras = config.get("allowed_real_contacts", [])
        if isinstance(extras, list):
            allowed_real.update(str(c).strip() for c in extras if str(c).strip())

        if sender not in allowed_real:
            reason = (
                f"real_send_target_not_allowed: {sender!r} is not in allowed_real_contacts "
                f"(allowed={sorted(allowed_real)})"
            )
            LOGGER.warning("send_gate BLOCKED. sender=%r %s", sender, reason)
            return GateDecision(False, reason, sender, system_status, is_dry_run)

    reason = (
        f"ALLOWED: owner_status=offline dock_unread={dock_has_unread} "
        f"sender_private=True ocr_confidence={ocr_confidence:.3f} "
        f"{'dry_run' if is_dry_run else 'real_send'}"
    )
    LOGGER.info("send_gate ALLOWED. sender=%r %s", sender, reason)
    return GateDecision(True, reason, sender, system_status, is_dry_run)


def log_send_decision(decision: GateDecision, message: str = "") -> None:
    """Emit a structured log line describing this gate decision (for audit trail)."""
    action = "SEND" if decision.allowed else "BLOCK"
    LOGGER.info(
        "auto_reply_gate action=%s sender=%r system_status=%s dry_run=%s reason=%s%s",
        action,
        decision.sender,
        decision.system_status,
        decision.is_dry_run,
        decision.reason,
        f" message={message!r}" if message else "",
    )
