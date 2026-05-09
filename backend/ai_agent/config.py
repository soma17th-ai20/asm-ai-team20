from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


def load_dotenv(path: Path | None = None) -> None:
    target = path or DEFAULT_ENV_PATH
    if not target.exists():
        return
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


@dataclass(slots=True)
class UpstageConfig:
    secret_key: str | None
    model: str
    chat_completions_url: str
    timeout_seconds: int = 20

    @property
    def enabled(self) -> bool:
        return bool(self.secret_key)


def load_upstage_config() -> UpstageConfig:
    load_dotenv()
    return UpstageConfig(
        secret_key=os.getenv("SECRET_KEY"),
        model=os.getenv("UPSTAGE_MODEL", "solar-pro2"),
        chat_completions_url=os.getenv(
            "UPSTAGE_CHAT_COMPLETIONS_URL",
            "https://api.upstage.ai/v1/solar/chat/completions",
        ),
        timeout_seconds=int(os.getenv("UPSTAGE_TIMEOUT_SECONDS", "20")),
    )
