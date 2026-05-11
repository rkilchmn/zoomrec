"""Shared Temporal client connection utilities with exponential retry."""

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from temporalio.client import Client


async def get_temporal_client(temporal_server: str):
    """Get or create a shared Temporal client connection with exponential retry.

    Args:
        temporal_server: Temporal server address (e.g., 'localhost:7233')

    Returns:
        Temporal Client instance or None if connection fails
    """
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RuntimeError)
    )
    async def _connect_with_retry():
        return await Client.connect(temporal_server)

    try:
        client = await _connect_with_retry()
        return client
    except RuntimeError as e:
        if "Connection refused" in str(e):
            return None
        else:
            raise
