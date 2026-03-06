import random
import time
from typing import Any, Callable

from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)


_RETRYABLE_ERROR_CODES = {
    "Throttling",
    "ThrottlingException",
    "TooManyRequestsException",
    "RequestLimitExceeded",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    "InternalError",
    "InternalFailure",
    "PriorRequestNotComplete",
}


def call_with_retries(
    operation: Callable[..., Any],
    *args: Any,
    max_attempts: int = 4,
    base_delay_seconds: float = 0.5,
    **kwargs: Any,
) -> Any:
    attempt = 0

    while True:
        try:
            return operation(*args, **kwargs)
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code", "")
            if error_code not in _RETRYABLE_ERROR_CODES or attempt >= (max_attempts - 1):
                raise
        except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError):
            if attempt >= (max_attempts - 1):
                raise

        sleep_seconds = (base_delay_seconds * (2 ** attempt)) + random.uniform(0, 0.2)
        time.sleep(sleep_seconds)
        attempt += 1
