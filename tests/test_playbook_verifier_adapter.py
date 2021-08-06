from receptor_satellite import playbook_verifier_adapter

import subprocess


class FakePopen:
    def __init__(self, returncode=0, response=None):
        self.returncode = returncode
        self.response = response

    def communicate(self, input):
        if self.response is None:
            response = "Playbook Verification has started\nAll templates successfully validated\n"
            response += input.decode("utf-8")
            return [bytes(response, "utf-8"), b""]
        else:
            return self.response


def __raise_oserror(*args, **kwargs):
    raise OSError


def test_success():
    old_popen = subprocess.Popen
    subprocess.Popen = lambda *args, **kwargs: FakePopen()
    result = playbook_verifier_adapter.verify("---\n- hosts: all\n  tasks: []")
    subprocess.Popen = old_popen
    assert result == "---\n- hosts: all\n  tasks: []"


def test_invalid_yaml():
    old_popen = subprocess.Popen
    subprocess.Popen = lambda *args, **kwargs: FakePopen(response=[b"Hello", b""])
    result = playbook_verifier_adapter.verify("Hello")
    subprocess.Popen = old_popen
    assert result == "Hello"


def test_missing_insights_client():
    old_popen = subprocess.Popen
    subprocess.Popen = __raise_oserror
    raised = None
    try:
        playbook_verifier_adapter.verify("Hello")
    except playbook_verifier_adapter.PlaybookValidationError as e:
        raised = e

    subprocess.Popen = old_popen
    assert str(raised) == "/usr/bin/insights-client not found"


def test_unregistered_insights_client():
    old_popen = subprocess.Popen
    response = "This machine has not yet been registered. Use --register to register this machine."
    subprocess.Popen = lambda *args, **kwargs: FakePopen(
        returncode=1, response=[b"", bytes(response, "utf-8")]
    )
    raised = None
    try:
        playbook_verifier_adapter.verify("Hello")
    except playbook_verifier_adapter.PlaybookValidationError as e:
        raised = e

    subprocess.Popen = old_popen
    expected = f"Playbook signature validation exit code: 1\n\n{response}"
    assert str(raised) == expected


def test_any_other_error():
    old_popen = subprocess.Popen
    subprocess.Popen = lambda *args, **kwargs: 1 + "a"
    raised = None
    try:
        playbook_verifier_adapter.verify("Hello")
    except Exception as e:
        raised = e

    subprocess.Popen = old_popen
    assert str(raised) == "unsupported operand type(s) for +: 'int' and 'str'"
