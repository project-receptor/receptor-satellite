import subprocess


class PlaybookValidationError(Exception):
    pass


def verify(playbook):
    try:
        sub = subprocess.Popen(
            [
                "/usr/bin/insights-client",
                "--module",
                "insights.client.apps.ansible.playbook_verifier",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        outs, errs = sub.comunicate(bytes(playbook, "utf-8"))
        if sub.returncode == 0:
            return outs.decode("utf-8")
        else:
            raise PlaybookValidationError(errs.decode("utf-8"))
    except OSError:
        raise PlaybookValidationError("/usr/bin/insights-client not found")
    except Exception as e:
        raise PlaybookValidationError(str(e))
