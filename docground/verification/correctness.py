"""Optional correctness checks in a no-network Docker sandbox only."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True)
class CorrectnessResult:
    status: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class CorrectnessRunner(Protocol):
    def run(self, code: str, test: str, timeout: float) -> CorrectnessResult: ...


class DockerCorrectnessRunner:
    def __init__(
        self,
        image: str = "python:3.11-slim",
        docker_path: str = "docker",
    ) -> None:
        self.image = image
        self.docker_path = docker_path

    def command(
        self, mount_path: str, timeout: float, *, container_name: str | None = None
    ) -> list[str]:
        command = [
            self.docker_path, "run", "--rm", "--pull=never",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "64",
            "--memory", "256m", "--cpus", "0.5", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--mount", f"type=bind,source={mount_path},target=/work,readonly",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
        ]
        if container_name is not None:
            command.extend(("--name", container_name))
        return [*command, self.image, "python", "/work/runner.py"]

    def run(self, code: str, test: str, timeout: float) -> CorrectnessResult:
        if not shutil.which(self.docker_path):
            return CorrectnessResult("unavailable", stderr="Docker executable not found")
        with tempfile.TemporaryDirectory(prefix="docground-check-") as directory:
            # The private outer directory remains 0700 on the host. Only this
            # inner directory is mounted, with access for the container's UID.
            root = Path(directory) / "work"
            root.mkdir()
            root.chmod(0o755)
            for name, content in (
                ("candidate.py", code), ("tests.py", test), ("runner.py", _RUNNER)
            ):
                path = root / name
                path.write_text(content, encoding="utf-8")
                path.chmod(0o644)
            container_name = f"docground-check-{uuid4().hex}"
            try:
                completed = subprocess.run(
                    self.command(os.fspath(root), timeout, container_name=container_name),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                if _is_docker_start_failure(completed.returncode, completed.stderr):
                    result = CorrectnessResult(
                        "unavailable", returncode=completed.returncode,
                        stderr="Docker could not start the isolated test container",
                    )
                else:
                    result = CorrectnessResult(
                        "pass" if completed.returncode == 0 else "fail",
                        returncode=completed.returncode,
                        stdout=completed.stdout, stderr=completed.stderr,
                    )
            except subprocess.TimeoutExpired as error:
                result = CorrectnessResult(
                    "timeout", returncode=None,
                    stdout=_as_text(error.stdout),
                    stderr=f"Sandbox exceeded {timeout:g} seconds",
                    timed_out=True,
                )
            except OSError as error:
                result = CorrectnessResult("unavailable", stderr=type(error).__name__)
            finally:
                # Killing `docker run` only kills the client, not the container.
                # Cleanup also runs when an interrupt propagates to the caller.
                cleaned_up = self._remove_container(container_name)
            if not cleaned_up:
                result = CorrectnessResult(
                    result.status, returncode=result.returncode, stdout=result.stdout,
                    stderr=(result.stderr + "\n" if result.stderr else "")
                    + f"Could not confirm cleanup of Docker container {container_name}.",
                    timed_out=result.timed_out,
                )
            return result

    def _remove_container(self, container_name: str) -> bool:
        try:
            completed = subprocess.run(
                [self.docker_path, "rm", "--force", container_name],
                capture_output=True, text=True, timeout=5.0, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0 or "no such container" in completed.stderr.lower()


def check_correctness(
    code: str,
    test: str | None = None,
    timeout: float = 10.0,
    runner: CorrectnessRunner | None = None,
) -> CorrectnessResult | None:
    if test is None or not test.strip():
        return None
    return (runner or DockerCorrectnessRunner()).run(code, test, timeout)


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else ""


def _is_docker_start_failure(returncode: int, stderr: str) -> bool:
    """Recognize Docker launch failures without confusing user-code exits."""
    lowered = stderr.lower()
    daemon_or_image_markers = (
        "cannot connect to the docker daemon",
        "error during connect",
        "error response from daemon",
        "unable to find image",
        "pull access denied",
        "failed to resolve reference",
        "permission denied while trying to connect",
        "is the docker daemon running",
    )
    command_start_markers = (
        "executable file not found",
        "exec: \"python\"",
        "permission denied",
        "no such file or directory",
    )
    return (
        returncode == 125 and any(marker in lowered for marker in daemon_or_image_markers)
    ) or (
        returncode in {126, 127}
        and any(marker in lowered for marker in command_start_markers)
    )


_RUNNER = '''
import runpy

namespace = runpy.run_path("/work/candidate.py")
with open("/work/tests.py", encoding="utf-8") as handle:
    exec(compile(handle.read(), "/work/tests.py", "exec"), namespace)
tests = [
    value for name, value in sorted(namespace.items())
    if name.startswith("test_") and callable(value)
]
for test in tests:
    test()
'''


def correctness_record(result: CorrectnessResult | None) -> dict[str, object] | None:
    return asdict(result) if result is not None else None
