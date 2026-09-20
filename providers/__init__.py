"""Provider configuration and project-root environment loading."""
import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"


def load_project_environment(env_file: str | Path = ENV_FILE) -> bool:
    """Load project-local variables without overriding the calling shell."""
    return load_dotenv(Path(env_file), override=False)


def require_environment_variable(name: str) -> str:
    """Return one configured value with an actionable setup error."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing {name}. Add it to the project root .env file: {ENV_FILE}"
        )
    return value


load_project_environment()
