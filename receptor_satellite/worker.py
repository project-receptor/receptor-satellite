import asyncio
import json
import logging

from .satellite_api import SatelliteAPI, HEALTH_CHECK_ERROR, HEALTH_STATUS_RESULTS
from .response.response_queue import ResponseQueue
from .response import constants
from .run_monitor import run_monitor
from .run import Run


def receptor_export(func):
    setattr(func, "receptor_export", True)
    return func


def configure_logger():
    logger = logging.getLogger(__name__)
    receptor_logger = logging.getLogger("receptor")
    logger.setLevel(receptor_logger.level)
    for handler in receptor_logger.handlers:
        logger.addHandler(handler)
    return logger


async def cancel_run(satellite_api, run_id, queue, logger):
    logger.info(f"Cancelling playbook run {run_id}")
    run = await run_monitor.get(run_id)
    status = None
    if run is True:
        logger.info(f"Playbook run {run_id} is already finished")
        status = constants.CANCEL_RESULT_FINISHED
    elif run is None:
        logger.info(f"Playbook run {run_id} is not known by receptor")
        status = constants.CANCEL_RESULT_FAILURE
    else:
        await satellite_api.init_session()
        response = await satellite_api.cancel(run.job_invocation_id)
        run.cancelled = True
        await satellite_api.close_session()
        if response["status"] == 422:
            status = constants.CANCEL_RESULT_FINISHED
        elif response["status"] == 200:
            status = constants.CANCEL_RESULT_CANCELLING
        else:
            status = constants.CANCEL_RESULT_FAILURE
    queue.playbook_run_cancel_ack(run_id, status)


def run(coroutine):
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(coroutine)


@receptor_export
def execute(message, config, queue):
    logger = configure_logger()
    queue = ResponseQueue(queue)
    payload = json.loads(message.raw_payload)
    satellite_api = SatelliteAPI.from_plugin_config(config)
    run(Run.from_raw(queue, payload, satellite_api, logger).run())


@receptor_export
def cancel(message, config, queue):
    logger = configure_logger()
    queue = ResponseQueue(queue)
    satellite_api = SatelliteAPI.from_plugin_config(config)
    payload = json.loads(message.raw_payload)
    run(cancel_run(satellite_api, payload.get("playbook_run_id"), queue, logger))


@receptor_export
def health_check(message, config, queue):
    logger = configure_logger()
    try:
        payload = json.loads(message.raw_payload)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON format for payload.")
        raise

    try:
        api = SatelliteAPI.from_plugin_config(config)
    except KeyError:
        result = dict(
            result=HEALTH_CHECK_ERROR, **HEALTH_STATUS_RESULTS[HEALTH_CHECK_ERROR]
        )
    else:
        result = run(api.health_check(payload.get("satellite_instance_id", "")))
    queue.put(result)
