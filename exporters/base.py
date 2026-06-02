import logging
from googleapiclient.discovery import build
from utils import RateLimiter, ProgressTracker, ensure_dir

logger = logging.getLogger(__name__)


class BaseExporter:
    """Base class for all Google service exporters."""

    SERVICE_NAME = 'base'
    API_NAME = ''
    API_VERSION = ''

    def __init__(self, credentials, email, export_dir='exports'):
        self.email = email
        self.export_dir = export_dir
        self.output_dir = ensure_dir(f'{export_dir}/{email}/{self.SERVICE_NAME}')
        self.rate_limiter = RateLimiter(calls_per_second=4, max_retries=6, base_delay=1.5)
        self.progress = ProgressTracker(email, self.SERVICE_NAME, export_dir)

        if self.API_NAME:
            self.service = build(
                self.API_NAME, self.API_VERSION, credentials=credentials
            )
        else:
            self.service = None

    def export(self):
        """Override in subclasses to implement export logic."""
        raise NotImplementedError

    def api_call(self, request):
        """Execute a Google API request with rate limiting and retry.

        Args:
            request: A Google API request object (the result of e.g.
                     service.users().messages().list(...)). The .execute()
                     method will be called with retry logic.

        Returns:
            The API response dict.
        """
        return self.rate_limiter.retry_on_error(request.execute)
