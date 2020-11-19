import asyncio
import re

from receptor_satellite.response.response_queue import constants

# EXCEPTION means failure between capsule and the target host
EXIT_STATUS_RE = re.compile(r"Exit status: (([0-9]+)|EXCEPTION)", re.MULTILINE)
UNREACHABLE_RE = re.compile(r"unreachable=[1-9][0-9]*")


class Host:
    def __init__(self, run, id, name):
        self.run = run
        self.id = id
        self.name = name
        self.sequence = 0
        self.since = None if run.config.text_update_full else 0.0
        self.result = None
        self.last_recap_line = ""
        self.host_recap_re = re.compile(f"^.*{name}.*ok=[0-9]+")
        self.last_output = ""
        self.unreachable = None

    def mark_as_failed(self, message, connection_result=True):
        queue = self.run.queue
        playbook_run_id = self.run.playbook_run_id
        queue.playbook_run_update(self.name, playbook_run_id, message, self.sequence)
        queue.playbook_run_finished(
            self.name, playbook_run_id, constants.RESULT_FAILURE, connection_result
        )

    def process_outputs(self, outputs):
        if outputs["output"] and (self.run.config.text_updates or outputs["complete"]):
            self.last_output = "".join(chunk["output"] for chunk in outputs["output"])
            if self.since is not None:
                self.since = outputs["output"][-1]["timestamp"]
            self.run.queue.playbook_run_update(
                self.name, self.run.playbook_run_id, self.last_output, self.sequence
            )
            self.sequence += 1

        self.find_recap_line()

    def find_recap_line(self):
        possible_recaps = list(
            filter(
                lambda x: re.match(self.host_recap_re, x), self.last_output.split("\n")
            )
        )
        if len(possible_recaps) > 0:
            self.last_recap_line = possible_recaps.pop()

    def done(self):
        connection_result = True
        connection_error = re.search(UNREACHABLE_RE, self.last_recap_line)
        result = constants.HOST_RESULT_FAILURE
        matches = re.findall(EXIT_STATUS_RE, self.last_output)
        exit_code = None
        # This means the job was already running on the host
        if matches:
            code = matches[0][1]
            # If there was an exit code
            if code != "":
                exit_code = int(code)
                if exit_code == 0:
                    result = constants.HOST_RESULT_SUCCESS
                elif self.run.cancelled:
                    result = constants.HOST_RESULT_CANCEL
                else:
                    result = constants.HOST_RESULT_FAILURE
        elif self.run.cancelled:
            result = constants.HOST_RESULT_CANCEL
        else:
            self.unreachable = True
            connection_result = None

        if connection_error:
            connection_result = False

        self.run.queue.playbook_run_finished(
            self.name,
            self.run.playbook_run_id,
            result,
            connection_result,
            exit_code,
        )
        self.result = result

    async def polling_loop(self):
        if self.id is None:
            return self.mark_as_failed("This host is not known by Satellite")
        while True:
            response = await self.poll_with_retries()
            if response["error"]:
                break
            body = response["body"]
            self.process_outputs(body)

            if body["complete"]:
                self.done()
                break

    async def poll_with_retries(self):
        retry = 0
        while retry < 5:
            await asyncio.sleep(self.run.config.text_update_interval)
            response = await self.run.satellite_api.output(
                self.run.job_invocation_id, self.id, self.since
            )
            if response["error"] is None:
                return response
            retry += 1
        self.mark_as_failed(response["error"])
        return dict(error=True)
