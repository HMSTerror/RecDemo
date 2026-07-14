from __future__ import annotations

from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_and_build_r7_paper_evidence.ps1"


def test_sync_script_is_read_only_remote_and_uses_fail_closed_builder() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ssh" in text and "scp" in text
    assert "build_r7_paper_evidence.py" in text
    assert "--expected-manifest-sha256" in text
    assert "--allow-not-ready" in text
    assert "New-Item" in text
    forbidden = ("ssh $SshHost rm", "ssh $SshHost mv", "ssh $SshHost sed", "RISK-08_EXIT.json' -Value")
    assert not any(token in text for token in forbidden)


def test_sync_script_creates_unique_dated_attempt_and_never_overwrites() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "yyyy-MM-dd_HH-mm-ss" in text
    assert "Test-Path -LiteralPath $AttemptRoot" in text
    assert "throw" in text
    assert "paper_evidence_status.json" in text
