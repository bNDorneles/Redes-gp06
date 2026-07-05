"""Inicia Echo, Chat e a Central UDP web com um único comando."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080

sys.path.insert(0, str(ROOT))

from src.web.server import UdpLabState, create_http_server  # noqa: E402


def request_shutdown(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def install_signal_handlers() -> None:
    for signal_name in ("SIGTERM", "SIGBREAK"):
        candidate = getattr(signal, signal_name, None)
        if candidate is not None:
            signal.signal(candidate, request_shutdown)


class ManagedProcess:
    """Subprocesso Python com logs UTF-8 e encerramento garantido."""

    def __init__(self, name: str, script: Path) -> None:
        self.name = name
        self.script = script
        self.process: subprocess.Popen[str] | None = None
        self.logs: deque[str] = deque(maxlen=40)
        self._reader: threading.Thread | None = None

    def start(self) -> None:
        if not self.script.is_file():
            raise RuntimeError(
                f"{self.name}: arquivo ausente: "
                f"{self.script.relative_to(ROOT)}"
            )

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(self.script)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            creationflags=creation_flags,
        )
        self._reader = threading.Thread(
            target=self._read_logs,
            name=f"log-{self.name.lower()}",
            daemon=True,
        )
        self._reader.start()

    def _read_logs(self) -> None:
        if self.process is None or self.process.stdout is None:
            return
        for line in self.process.stdout:
            self.logs.append(line.rstrip())

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def error_summary(self) -> str:
        return "\n".join(self.logs) or "nenhum log disponível"

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        if self.process.stdout:
            self.process.stdout.close()
        if self._reader:
            self._reader.join(timeout=0.5)


class UdpServerManager:
    def __init__(self) -> None:
        self.processes = {
            "echo": ManagedProcess(
                "Echo UDP",
                ROOT / "src" / "echo" / "server.py",
            ),
            "chat": ManagedProcess(
                "Chat UDP",
                ROOT / "src" / "chat" / "server.py",
            ),
        }

    def start(self) -> None:
        try:
            for process in self.processes.values():
                process.start()
            time.sleep(0.45)
            failed = [
                process
                for process in self.processes.values()
                if not process.is_running()
            ]
            if failed:
                details = "\n\n".join(
                    f"{process.name}:\n{process.error_summary()}"
                    for process in failed
                )
                raise RuntimeError(
                    "não foi possível iniciar os servidores UDP. "
                    "Verifique se as portas 5000 e 5001 estão livres.\n"
                    f"{details}"
                )
        except Exception:
            self.stop()
            raise

    def status(self) -> dict[str, bool]:
        return {
            name: process.is_running()
            for name, process in self.processes.items()
        }

    def stop(self) -> None:
        for process in reversed(tuple(self.processes.values())):
            process.stop()


def valid_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("a porta deve estar entre 1 e 65535")
    return port


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inicia a interface web da demonstração UDP.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"endereço HTTP local (padrão: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=valid_port,
        default=DEFAULT_PORT,
        help=f"porta HTTP local (padrão: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="não abre o navegador automaticamente",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    install_signal_handlers()
    manager = UdpServerManager()
    state: UdpLabState | None = None
    http_server = None

    try:
        manager.start()
        state = UdpLabState(status_provider=manager.status)
        http_server = create_http_server(args.host, args.port, state)
        url = f"http://{args.host}:{args.port}"
        print("Central UDP iniciada.")
        print(f"Acesse: {url}")
        print("Pressione Ctrl+C para encerrar todos os serviços.")

        if not args.no_browser:
            opener = threading.Timer(0.5, webbrowser.open, args=(url,))
            opener.daemon = True
            opener.start()

        http_server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nEncerrando a Central UDP...")
    except OSError as error:
        if getattr(error, "winerror", None) == 10048:
            print(
                f"Erro: a porta HTTP {args.port} já está em uso.",
                file=sys.stderr,
            )
        else:
            print(f"Erro de rede: {error}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    finally:
        if http_server is not None:
            http_server.server_close()
        if state is not None:
            state.close()
        manager.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
