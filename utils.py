import os
import json
import time
import random
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with exponential backoff and jitter."""

    def __init__(self, calls_per_second=4, max_retries=6, base_delay=1.5):
        self.min_interval = 1.0 / calls_per_second
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._last_call = 0

    def wait(self):
        """Wait to respect rate limit."""
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()

    def retry_on_error(self, func):
        """Execute func() with exponential backoff on failure."""
        for attempt in range(self.max_retries):
            try:
                self.wait()
                return func()
            except Exception as e:
                error_str = str(e)
                is_retryable = (
                    '429' in error_str
                    or 'Rate Limit' in error_str
                    or 'rateLimitExceeded' in error_str
                    or '403' in error_str and 'quota' in error_str.lower()
                    or '500' in error_str
                    or '503' in error_str
                )
                if is_retryable and attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"API error (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                elif attempt == self.max_retries - 1:
                    raise
                else:
                    raise


class ProgressTracker:
    """Tracks exported items to enable resume after interruption."""

    def __init__(self, account_email, service_name, export_dir='exports'):
        self.account = account_email
        self.service = service_name
        self.progress_dir = Path(export_dir) / account_email / '.progress'
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.progress_dir / f'{service_name}.json'
        self._completed = self._load()

    def _load(self):
        """Load completed item IDs from disk."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('completed', []))
            except (json.JSONDecodeError, KeyError):
                return set()
        return set()

    def _save(self):
        """Save completed item IDs to disk."""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'completed': list(self._completed),
                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_completed': len(self._completed),
            }, f, indent=2)

    def is_done(self, item_id):
        """Check if an item was already exported."""
        return str(item_id) in self._completed

    def mark_done(self, item_id):
        """Mark an item as exported and auto-save every 50 items."""
        self._completed.add(str(item_id))
        if len(self._completed) % 50 == 0:
            self._save()

    def flush(self):
        """Force save progress to disk."""
        self._save()

    @property
    def completed_count(self):
        return len(self._completed)

    def get_status(self):
        """Return progress status dict."""
        return {
            'service': self.service,
            'completed': len(self._completed),
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
        }


def safe_filename(name, max_length=200):
    """Sanitize a string for use as a filename."""
    safe = "".join(c if c.isalnum() or c in ' ._-()' else '_' for c in name)
    safe = safe.strip(' .')
    if len(safe) > max_length:
        safe = safe[:max_length]
    return safe or 'unnamed'


def ensure_dir(path):
    """Create directory if it doesn't exist and return the path string."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return str(path)
