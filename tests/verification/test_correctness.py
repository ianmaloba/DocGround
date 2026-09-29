import os
from pathlib import Path
import stat
import subprocess

import pytest

from docground.verification.correctness import (
    CorrectnessResult,
    DockerCorrectnessRunner,
    check_correctness,
)


class FakeRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, code, test, timeout):
        self.calls.append((code, test, timeout))
        return self.result


def test_missing_test_means_correctness_not_run():
    assert check_correctness("print('hi')", test=None) is None


def test_test_runs_only_through_supplied_sandbox_backend():
    runner = FakeRunner(CorrectnessResult("pass", returncode=0))
    result = check_correctness("def answer(): return 42", "def test_answer(): assert answer() == 42", runner=runner)
    assert result.status == "pass"
    assert len(runner.calls) == 1


def test_docker_command_disables_network_and_privileges():
    command = DockerCorrectnessRunner().command("/tmp/run", 5.0)
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert "--cap-drop" in command and command[command.index("--cap-drop") + 1] == "ALL"
    assert "--read-only" in command
    assert "--pull=never" in command


def test_docker_start_failure_is_unavailable_not_model_failure(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        "docground.verification.correctness.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 125, stdout="", stderr="Cannot connect to the Docker daemon"
        ),
    )
    result = DockerCorrectnessRunner().run("pass", "", 2)
    assert result.status == "unavailable"
    assert "Docker" in result.stderr


def test_docker_container_command_missing_is_unavailable(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        "docground.verification.correctness.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 127, stdout="", stderr='exec: "python": executable file not found in $PATH'
        ),
    )
    assert DockerCorrectnessRunner().run("pass", "", 2).status == "unavailable"


def test_candidate_exit_code_125_is_not_automatically_an_evaluator_error(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        "docground.verification.correctness.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 125, stdout="", stderr="candidate deliberately exited with status 125"
        ),
    )
    assert DockerCorrectnessRunner().run("pass", "", 2).status == "fail"


def test_nonzero_test_process_remains_a_functional_failure(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        "docground.verification.correctness.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, stdout="", stderr="AssertionError"
        ),
    )
    result = DockerCorrectnessRunner().run("pass", "", 2)
    assert result.status == "fail"


def test_sandbox_mount_is_readable_by_unprivileged_uid_but_host_parent_is_private(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")

    def run(command, **kwargs):
        if command[1] == "run":
            mount = command[command.index("--mount") + 1]
            root = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            assert stat.S_IMODE(root.parent.stat().st_mode) == 0o700
            assert stat.S_IMODE(root.stat().st_mode) & 0o005 == 0o005
            for filename in ("candidate.py", "tests.py", "runner.py"):
                assert stat.S_IMODE((root / filename).stat().st_mode) & 0o004
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("docground.verification.correctness.subprocess.run", run)
    assert DockerCorrectnessRunner().run("pass", "assert True", 2).status == "pass"


def test_timeout_removes_the_exact_container_with_a_bounded_cleanup(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"before timeout")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("docground.verification.correctness.subprocess.run", run)
    result = DockerCorrectnessRunner().run("while True: pass", "assert True", 0.1)
    assert result.status == "timeout"
    assert result.timed_out
    assert result.stdout == "before timeout"
    container_name = calls[0][0][calls[0][0].index("--name") + 1]
    assert calls[1][0] == ["docker", "rm", "--force", container_name]
    assert calls[1][1]["timeout"] == 5.0


def test_interrupt_also_removes_the_container(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1] == "run":
            raise KeyboardInterrupt
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("docground.verification.correctness.subprocess.run", run)
    with pytest.raises(KeyboardInterrupt):
        DockerCorrectnessRunner().run("pass", "assert True", 2)
    assert calls[1][1:3] == ["rm", "--force"]


def test_cleanup_failure_is_reported_without_hiding_timeout(monkeypatch):
    monkeypatch.setattr("docground.verification.correctness.shutil.which", lambda _: "/usr/bin/docker")

    def run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("docground.verification.correctness.subprocess.run", run)
    result = DockerCorrectnessRunner().run("pass", "assert True", 2)
    assert result.status == "timeout"
    assert "Could not confirm cleanup" in result.stderr


@pytest.mark.docker
@pytest.mark.skipif(
    os.environ.get("DOCGROUND_RUN_DOCKER_TESTS") != "1",
    reason="Set DOCGROUND_RUN_DOCKER_TESTS=1 with python:3.11-slim already installed locally",
)
@pytest.mark.parametrize(("code", "test", "timeout", "expected"), [
    ("def answer(): return 42", "def test_answer(): assert answer() == 42", 20, "pass"),
    ("def answer(): return 0", "def test_answer(): assert answer() == 42", 20, "fail"),
    ("while True: pass", "assert True", 1, "timeout"),
])
def test_real_docker_runs_checks_and_removes_each_container(monkeypatch, code, test, timeout, expected):
    # --pull=never ensures this opt-in check cannot download an image.
    runner = DockerCorrectnessRunner()
    original_command = runner.command
    containers = []

    def command(mount_path, timeout, *, container_name=None):
        containers.append(container_name)
        return original_command(mount_path, timeout, container_name=container_name)

    monkeypatch.setattr(runner, "command", command)
    result = runner.run(code, test, timeout)
    assert result.status == expected, result
    assert "Could not confirm cleanup" not in result.stderr
    inspected = subprocess.run(
        [runner.docker_path, "inspect", containers[0]],
        capture_output=True, text=True, timeout=5.0, check=False,
    )
    assert inspected.returncode != 0
    assert "no such object" in inspected.stderr.lower()
