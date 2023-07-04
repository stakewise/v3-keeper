import logging

from sw_utils import IpfsException
from sw_utils.tenacity_decorators import custom_before_log
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_exponential

from src.config.settings import DEFAULT_RETRY_TIME

logger = logging.getLogger(__name__)


def retry_ipfs_exception(delay: int = DEFAULT_RETRY_TIME):
    return retry(
        retry=retry_if_exception_type(IpfsException),
        wait=wait_exponential(multiplier=1, min=1, max=delay // 2),
        stop=stop_after_delay(delay),
        before=custom_before_log(logger, logging.INFO),
    )
