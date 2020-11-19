import pytest
from receptor_satellite.host import Host  # noqa: E402
import receptor_satellite.response.constants as constants  # noqa: E402
import receptor_satellite.response.messages as messages  # noqa: E402
from test_helper import base_scenario  # noqa: F401


def test_mark_as_failed(base_scenario):  # noqa: F811
    queue, logger, satellite_api, run = base_scenario
    host = Host(run, None, "host1")
    host.mark_as_failed("controlled failure")

    assert queue.messages == [
        messages.playbook_run_update(host.name, "play_id", "controlled failure", 0),
        messages.playbook_run_finished(host.name, "play_id", constants.RESULT_FAILURE),
    ]


class PollWithRetriesTestCase:
    def __init__(
        self,
        host_id=1,
        api_output=None,
        result=None,
        api_requests=[],
        queue_messages=[],
    ):
        self.host_id = host_id
        self.api_output = api_output
        self.result = result
        self.api_requests = api_requests
        self.queue_messages = queue_messages


POLL_WITH_RETRIES_TEST_CASES = [
    # Polling loop does not loop if there is no error when talking to
    # the API
    PollWithRetriesTestCase(
        result={"error": None, "key": "value"},
        api_output={"error": None, "key": "value"},
        api_requests=[("output", (None, 1, None))],
    ),
    PollWithRetriesTestCase(
        result={"error": True},
        api_output={"error": "controlled failure"},
        api_requests=[("output", (None, 1, None)) for _x in range(5)],
        queue_messages=[
            messages.playbook_run_update("host1", "play_id", "controlled failure", 0),
            messages.playbook_run_finished(
                "host1", "play_id", constants.RESULT_FAILURE
            ),
        ],
    ),
]


@pytest.fixture(params=POLL_WITH_RETRIES_TEST_CASES)
def poll_with_retries_scenario(request, base_scenario):  # noqa: F811
    # host_id, output_value, result, api_requests, queue_messages = request.param
    param = request.param
    queue, logger, satellite_api, run = base_scenario
    host = Host(run, param.host_id, "host1")

    yield (queue, host, param)


@pytest.mark.asyncio
async def test_poll_with_retries(poll_with_retries_scenario):
    (
        queue,
        host,
        param,
    ) = poll_with_retries_scenario
    satellite_api = host.run.satellite_api
    satellite_api.responses = [
        param.api_output for _x in range(len(param.api_requests))
    ]

    result = await host.poll_with_retries()

    assert result == param.result
    assert satellite_api.requests == param.api_requests
    assert queue.messages == param.queue_messages


class PollingLoopTestCase(PollWithRetriesTestCase):
    def __init__(self, cancelled=False, **kwargs):
        super().__init__(**kwargs)
        self.cancelled = cancelled


POLLING_LOOP_TEST_CASES = [
    # If the host doesn't have an ID, it is assumed to be not known by
    # Satellite and is marked as failed
    PollingLoopTestCase(
        host_id=None,
        queue_messages=[
            messages.playbook_run_update(
                "host1", "play_id", "This host is not known by Satellite", 0
            ),
            messages.playbook_run_finished(
                "host1", "play_id", constants.RESULT_FAILURE
            ),
        ],
    ),
    # If the polling loop receives an error from the API, it marks the
    # host as failed
    PollingLoopTestCase(
        api_output={"error": "controlled failure"},
        api_requests=[("output", (None, 1, None)) for _x in range(5)],
        queue_messages=[
            messages.playbook_run_update("host1", "play_id", "controlled failure", 0),
            messages.playbook_run_finished(
                "host1", "play_id", constants.RESULT_FAILURE
            ),
        ],
    ),
    # If the last output from the API ends with Exit status: 0, mark
    # the run on the host as success
    PollingLoopTestCase(
        api_output={
            "error": None,
            "body": {"complete": True, "output": [{"output": "Exit status: 0"}]},
        },
        api_requests=[("output", (None, 1, None))],
        queue_messages=[
            messages.playbook_run_update("host1", "play_id", "Exit status: 0", 0),
            messages.playbook_run_finished(
                "host1", "play_id", constants.RESULT_SUCCESS
            ),
        ],
    ),
    # If the run was cancelled, but the host managed to finish
    # successfully, mark it as success
    PollingLoopTestCase(
        cancelled=True,
        api_output={
            "error": None,
            "body": {"complete": True, "output": [{"output": "Exit status: 0"}]},
        },
        api_requests=[("output", (None, 1, None))],
        queue_messages=[
            messages.playbook_run_update("host1", "play_id", "Exit status: 0", 0),
            messages.playbook_run_finished(
                "host1", "play_id", constants.RESULT_SUCCESS
            ),
        ],
    ),
    # If the host failed, mark it as failed
    PollingLoopTestCase(
        api_output={
            "error": None,
            "body": {"complete": True, "output": [{"output": "Exit status: 123"}]},
        },
        api_requests=[("output", (None, 1, None))],
        queue_messages=[
            messages.playbook_run_update("host1", "play_id", "Exit status: 123", 0),
            messages.playbook_run_finished(
                "host1", "play_id", constants.RESULT_FAILURE, True, 123
            ),
        ],
    ),
    # If the run was cancelled and the run on the host failed, mark it
    # as cancelled
    PollingLoopTestCase(
        cancelled=True,
        api_output={
            "error": None,
            "body": {"complete": True, "output": [{"output": "Exit status: 123"}]},
        },
        api_requests=[("output", (None, 1, None))],
        queue_messages=[
            messages.playbook_run_update("host1", "play_id", "Exit status: 123", 0),
            messages.playbook_run_finished(
                "host1", "play_id", constants.RESULT_CANCEL, True, 123
            ),
        ],
    ),
]


@pytest.fixture(params=POLLING_LOOP_TEST_CASES)
def polling_loop_scenario(request, base_scenario):  # noqa: F811
    queue, logger, satellite_api, run = base_scenario
    run.cancelled = request.param.cancelled
    host = Host(run, request.param.host_id, "host1")

    yield (queue, host, request.param)


@pytest.mark.asyncio
async def test_polling_loop(polling_loop_scenario):
    (
        queue,
        host,
        param,
    ) = polling_loop_scenario
    satellite_api = host.run.satellite_api
    satellite_api.responses = [
        param.api_output for _x in range(len(param.api_requests))
    ]

    result = await host.polling_loop()
    assert result == param.result
    assert satellite_api.requests == param.api_requests
    assert queue.messages == param.queue_messages
