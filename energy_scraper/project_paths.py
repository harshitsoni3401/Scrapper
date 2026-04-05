from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
RUN_REPORTS_DIR = REPORTS_DIR / "runs"
LOGS_DIR = REPORTS_DIR / "logs"
FEEDBACK_DIR = REPORTS_DIR / "feedback"
ARCHIVE_DIR = REPORTS_DIR / "archive"
STATE_DIR = REPORTS_DIR / "state"
CACHE_DIR = REPORTS_DIR / "cache"
ENV_FILE = PROJECT_ROOT / ".env"
GOOGLE_CREDENTIALS_PATH = PROJECT_ROOT / "google_credentials.json"
BROWSER_STATE_PATH = STATE_DIR / "playwright_state.json"
SEEN_CACHE_PATH = CACHE_DIR / "seen_cache.json"
SOURCE_HEALTH_PATH = CACHE_DIR / "source_health.json"


def ensure_runtime_dirs() -> None:
    for path in (REPORTS_DIR, RUN_REPORTS_DIR, LOGS_DIR, FEEDBACK_DIR, ARCHIVE_DIR, STATE_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
