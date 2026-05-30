# orchestrator/services/manager.py
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Service:
    name: str
    command: List[str]
    cwd: Optional[str] = None
    env: Optional[dict] = None  # Custom environment variables
    use_process_group: bool = False  # True for ROS2, etc.
    process: Optional[subprocess.Popen] = field(default=None, init=False)
    log_file: Optional[Path] = field(default=None, init=False)


class ServiceManager:
    def __init__(self, services: List[Service]) -> None:
        self.services = services
        self._stopping = False
        # Create logs directory
        self.logs_dir = Path.home() / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def start_all(self) -> None:
        print("[orchestrator] Starting services...")
        for service in self.services:
            print(f"[orchestrator]  -> {service.name}: {' '.join(service.command)}")
            preexec_fn = os.setsid if service.use_process_group else None
            
            # Create log file for this service
            log_file_path = self.logs_dir / f"{service.name}.log"
            service.log_file = log_file_path
            log_file_handle = open(log_file_path, "a", buffering=1)  # Line buffered
            
            print(f"[orchestrator]    Logging to: {log_file_path}")
            
            # Prepare environment - inherit current env and add custom vars
            proc_env = os.environ.copy()
            if service.env:
                proc_env.update(service.env)
            
            service.process = subprocess.Popen(
                service.command,
                stdout=log_file_handle,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=service.cwd,
                env=proc_env,
                preexec_fn=preexec_fn,
            )
        print("[orchestrator] All services started.")

    def stop_all(self) -> None:
        if self._stopping:
            return
        self._stopping = True

        print("\n[orchestrator] Stopping services...")
        for service in reversed(self.services):
            proc = service.process
            if proc is None:
                continue

            if proc.poll() is None:
                print(f"[orchestrator]  -> Terminating {service.name}...")
                if service.use_process_group:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    except AttributeError:
                        proc.terminate()
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print(f"[orchestrator]  -> Killing {service.name}...")
                    if service.use_process_group:
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        except (ProcessLookupError, AttributeError):
                            proc.kill()
                    else:
                        proc.kill()

        print("[orchestrator] All services stopped.")

    def run_forever(self) -> None:
        """
        Monitoring loop. Call this in a background thread so the
        main thread can run the HTTP server.
        """
        try:
            while not self._stopping:
                for service in self.services:
                    proc = service.process
                    if proc is None:
                        continue

                    ret = proc.poll()
                    if ret is not None:
                        print(
                            f"[orchestrator] Service '{service.name}' exited with code {ret}."
                        )
                        if service.log_file:
                            print(
                                f"[orchestrator] Check logs at: {service.log_file}"
                            )
                        self.stop_all()
                        return

                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stop_all()
