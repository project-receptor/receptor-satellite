import asyncio

from .config import Config
from .host import Host
from .run_monitor import run_monitor
from .response.response_queue import constants


class Run:
    def __init__(
        self,
        queue,
        remediation_id,
        playbook_run_id,
        account,
        hosts,
        playbook,
        config,
        satellite_api,
        logger,
    ):
        self.queue = queue
        self.remedation_id = remediation_id
        self.playbook_run_id = playbook_run_id
        self.account = account
        self.playbook = playbook
        self.config = Config.from_raw(Config.validate_input(config, logger))

        unsafe_hostnames = [name for name in hosts if "," in name]
        for name in unsafe_hostnames:
            logger.warning(f"Hostname '{name}' contains a comma, skipping")
            Host(self, None, name).mark_as_failed("Hostname contains a comma, skipping")

        self.hosts = [
            Host(self, None, name) for name in hosts if name not in unsafe_hostnames
        ]
        self.satellite_api = satellite_api
        self.logger = logger
        self.job_invocation_id = None
        self.cancelled = False

    @classmethod
    def from_raw(cls, queue, raw, satellite_api, logger):
        return cls(
            queue,
            raw["remediation_id"],
            raw["playbook_run_id"],
            raw["account"],
            raw["hosts"],
            raw["playbook"],
            raw["config"],
            satellite_api,
            logger,
        )

    async def start(self):
        await self.satellite_api.init_session()
        try:
            if not await run_monitor.register(self):
                self.logger.error(
                    f"Playbook run {self.playbook_run_id} already known, skipping."
                )
                return
            response = await self.satellite_api.trigger(
                {"playbook": self.playbook}, [host.name for host in self.hosts]
            )
            self.queue.ack(self.playbook_run_id)
            if response["error"]:
                self.abort(response["error"])
            else:
                self.job_invocation_id = response["body"]["id"]
                self.logger.info(
                    f"Playbook run {self.playbook_run_id} running as job invocation {self.job_invocation_id}"
                )
                self.update_hosts(response["body"]["targeting"]["hosts"])
                await asyncio.gather(*[host.polling_loop() for host in self.hosts])
                result = constants.RESULT_FAILURE
                infrastructure_error = None
                if self.cancelled:
                    result = constants.RESULT_CANCEL
                elif any(
                    host.result == constants.HOST_RESULT_INFRA_FAILURE
                    for host in self.hosts
                ):
                    infrastructure_error = "Infrastructure error"
                elif all(
                    host.result == constants.HOST_RESULT_SUCCESS for host in self.hosts
                ):
                    result = constants.RESULT_SUCCESS
                self.queue.playbook_run_completed(
                    self.playbook_run_id,
                    result,
                    infrastructure_error=infrastructure_error,
                )
            await run_monitor.done(self)
            self.logger.info(f"Playbook run {self.playbook_run_id} done")
        finally:
            await self.satellite_api.close_session()

    def update_hosts(self, hosts):
        host_map = {host.name: host for host in self.hosts}
        for host in hosts:
            host_map[host["name"]].id = host["id"]

    def abort(self, error):
        error = str(error)
        self.logger.error(
            f"Playbook run {self.playbook_run_id} encountered error `{error}`, aborting."
        )
        for host in self.hosts:
            host.mark_as_failed(error)
        self.queue.playbook_run_completed(
            self.playbook_run_id, constants.RESULT_FAILURE, connection_error=error
        )
