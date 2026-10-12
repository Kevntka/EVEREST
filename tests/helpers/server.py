"""Start and stop the backend under test (uvicorn in its own process, against the test DB)."""

import subprocess
import time

import httpx

from .config import BACKEND_DIR, BACKEND_HOST, BACKEND_PYTHON, REPORTS_DIR, backend_env


class BackendProcess:
    def __init__(self, port: int, log_name: str):
        self.port = port
        self.url = f"http://{BACKEND_HOST}:{port}"
        self.log_path = REPORTS_DIR / log_name
        self.proc: subprocess.Popen | None = None
        self._log = None

    def start(self, timeout: float = 40) -> "BackendProcess":
        if not BACKEND_PYTHON.exists():
            raise RuntimeError(f"Backend venv not found at {BACKEND_PYTHON}. Create it first (see tests/README.md).")
        try:
            httpx.get(f"{self.url}/api/test", timeout=1)
            raise RuntimeError(f"Port {self.port} is already in use. Stop that server or set another port in tests/.env.test.")
        except httpx.TransportError:
            pass
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self._log = open(self.log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [str(BACKEND_PYTHON), "-m", "uvicorn", "main:app", "--host", BACKEND_HOST, "--port", str(self.port)],
            cwd=BACKEND_DIR, env=backend_env(), stdout=self._log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"Backend exited early; see {self.log_path}")
            try:
                if httpx.get(f"{self.url}/api/test", timeout=1).status_code == 200:
                    return self
            except httpx.TransportError:
                time.sleep(0.3)
        self.stop()
        raise RuntimeError(f"Backend didn't start within {timeout}s; see {self.log_path}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self._log:
            self._log.close()
