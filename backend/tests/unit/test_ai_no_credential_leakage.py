"""The AI module never needs CDSE/pilot credentials (Open-Meteo requires no
API key) and must never reference them — see CLAUDE.md rule 7. This scans
the actual committed source for any of the forbidden secret-related
identifiers, so a future edit that starts threading credentials through
app/ai/ or the training script fails a test rather than shipping quietly.
"""

from pathlib import Path

_FORBIDDEN_SUBSTRINGS = (
    "cdse_client_secret",
    "cdse_client_id",
    "pilot_password",
    "authorization",
    "bearer ",
    "access_token",
)

_AI_MODULE_DIR = Path(__file__).resolve().parents[2] / "app" / "ai"
_TRAINING_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "train_ai_soil_moisture.py"


def _source_files() -> list[Path]:
    files = sorted(_AI_MODULE_DIR.glob("*.py"))
    files.append(_TRAINING_SCRIPT)
    return files


def test_no_forbidden_credential_identifiers_in_ai_source() -> None:
    for path in _source_files():
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            assert forbidden not in text, f"{path} contains forbidden identifier '{forbidden}'"


def test_ai_source_files_were_actually_scanned() -> None:
    # Guards against the glob above silently matching nothing (e.g. a path
    # typo), which would make the assertions above vacuously true.
    files = _source_files()
    assert len(files) >= 5
    assert all(path.exists() for path in files)
