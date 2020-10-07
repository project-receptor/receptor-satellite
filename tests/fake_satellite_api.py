class FakeSatelliteAPI:
    def __init__(self, responses=[]):
        self.requests = []
        self.responses = []

    def record_request(self, request_type, data):
        self.requests.append((request_type, data))

    async def output(self, job_id, host_id, since):
        print(f"{(job_id, host_id, since)}")
        self.record_request("output", (job_id, host_id, since))
        return self.__pop_responses()

    async def bulk_output(self, job_id, host_ids, since):
        print(f"{(job_id, host_ids, since)}")
        self.record_request("bulk_output", (job_id, host_ids, since))
        return self.__pop_responses()

    async def trigger(self, inputs, hosts):
        self.record_request("trigger", (inputs, hosts))
        return self.__pop_responses()

    async def init_session(self):
        pass

    async def close_session(self):
        pass

    def __pop_responses(self):
        [response, *rest] = self.responses
        self.responses = rest
        return response
