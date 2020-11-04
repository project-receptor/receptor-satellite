import asyncio
import pytest

from fake_logger import FakeLogger  # noqa: E402
from fake_queue import FakeQueue  # noqa: E402
from fake_satellite_api import FakeSatelliteAPI  # noqa: E402
from receptor_satellite.response.response_queue import ResponseQueue  # noqa: E402
from receptor_satellite.run import Run  # noqa: E402


async def _sleep_override(interval):
    pass


asyncio.sleep = _sleep_override


@pytest.fixture
def base_scenario(request):
    queue = FakeQueue()
    logger = FakeLogger()
    satellite_api = FakeSatelliteAPI()
    run = Run(
        ResponseQueue(queue),
        "rem_id",
        "play_id",
        "account_no",
        ["host1"],
        "playbook",
        {},
        satellite_api,
        logger,
    )
    yield (queue, logger, satellite_api, run)
