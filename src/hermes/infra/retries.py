from urllib.error import HTTPError

from tenacity import retry, retry_if_exception, retry_if_exception_type, stop_after_attempt, wait_exponential


def io_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
        retry=retry_if_exception_type((ConnectionError, OSError, TimeoutError)),
    )


def model_retry():
    def _should_retry_model_error(exc: BaseException) -> bool:
        # Avoid long retry loops for deterministic HTTP failures (e.g. 500 from model server)
        # while still retrying transient network/IO issues.
        if isinstance(exc, (HTTPError, TimeoutError, ValueError)):
            return False
        return isinstance(exc, (ConnectionError, OSError))

    return retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=1.0, max=8.0),
        retry=retry_if_exception(_should_retry_model_error),
    )
