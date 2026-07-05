"""Orquestra uma demonstração reproduzível do Echo e do Chat UDP."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ECHO_HOST = "127.0.0.1"
ECHO_PORT = 5000
CHAT_HOST = "127.0.0.1"
CHAT_PORT = 5001

STARTUP_WAIT_SECONDS = 0.5
MESSAGE_WAIT_SECONDS = 0.4
SHUTDOWN_WAIT_SECONDS = 2.0
ECHO_CLIENT_TIMEOUT_SECONDS = 5.0

ECHO_SERVER_SCRIPT = ROOT / "src" / "echo" / "server.py"
ECHO_CLIENT_SCRIPT = ROOT / "src" / "echo" / "client.py"
CHAT_SERVER_SCRIPT = ROOT / "src" / "chat" / "server.py"
CHAT_CLIENT_SCRIPT = ROOT / "src" / "chat" / "client.py"

ECHO_DEMO_MESSAGE = "Olá, servidor Echo! Esta é uma mensagem de demonstração."
ALICE_DEMO_MESSAGE = "Oi Bob, aqui é a Alice. Tudo certo por aí?"
BOB_DEMO_MESSAGE = "Oi Alice! Aqui é o Bob, recebi sua mensagem."


class PortInUseError(RuntimeError):
    """Erro levantado quando uma porta UDP necessária já está em uso."""


def configure_parent_encoding() -> None:
    """Força UTF-8 na saída do processo principal, se necessário.

    Evita `UnicodeEncodeError` ao imprimir acentos quando o console usa
    uma codificação legada (ex: `cp1252` no Windows) ou quando a saída
    padrão está redirecionada para um arquivo ou pipe.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding and stream.encoding.lower() != "utf-8":
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_subprocess_environment() -> dict[str, str]:
    """Copia o ambiente atual e força UTF-8 nos subprocessos Python.

    Returns:
        Um dicionário de variáveis de ambiente pronto para uso em
        `subprocess.Popen`, com `PYTHONIOENCODING` e `PYTHONUTF8` definidos.
    """
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    return environment


def check_udp_port_available(host: str, port: int) -> None:
    """Verifica se uma porta UDP está livre antes de iniciar um servidor.

    Args:
        host: Endereço local a testar.
        port: Porta UDP a testar.

    Raises:
        PortInUseError: Se a porta já estiver ocupada por outro processo.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind((host, port))
    except OSError as error:
        raise PortInUseError(
            f"a porta {port}/UDP já está em uso. Feche o processo que a "
            "está utilizando (ou aguarde a demonstração anterior encerrar) "
            "e execute novamente."
        ) from error
    finally:
        probe.close()


class ManagedProcess:
    """Subprocesso Python com logs UTF-8 e encerramento garantido."""

    def __init__(self, name: str, script: Path, args: list[str] | None = None) -> None:
        self.name = name
        self.script = script
        self.args = args or []
        self.process: subprocess.Popen[str] | None = None
        self.logs: list[str] = []
        self._reader: threading.Thread | None = None

    def start(self, environment: dict[str, str]) -> None:
        """Inicia o subprocesso com stdin/stdout redirecionados e UTF-8 forçado.

        Args:
            environment: Variáveis de ambiente já preparadas para UTF-8.
        """
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(self.script), *self.args],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
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

    def send_line(self, text: str) -> None:
        """Envia uma linha para a entrada padrão do processo, como um input do usuário.

        Args:
            text: Conteúdo a enviar; uma quebra de linha é adicionada automaticamente.
        """
        if self.process is None or self.process.stdin is None:
            return
        try:
            self.process.stdin.write(f"{text}\n")
            self.process.stdin.flush()
        except OSError:
            pass

    def close_stdin(self) -> None:
        """Fecha a entrada padrão do processo, sinalizando fim da digitação."""
        if self.process is not None and self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError:
                pass

    def is_running(self) -> bool:
        """Indica se o processo ainda está em execução."""
        return self.process is not None and self.process.poll() is None

    def transcript(self) -> str:
        """Retorna o log acumulado do processo, ou uma mensagem padrão se vazio."""
        return "\n".join(self.logs) if self.logs else "nenhum log disponível"

    def stop(self) -> None:
        """Encerra o processo (se ativo) e aguarda a thread leitora finalizar."""
        if self.process is None:
            return
        self.close_stdin()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=SHUTDOWN_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=SHUTDOWN_WAIT_SECONDS)
        if self.process.stdout:
            self.process.stdout.close()
        if self._reader:
            self._reader.join(timeout=1.0)


class UdpDemo:
    """Orquestra o Echo e o Chat UDP para a demonstração integrada."""

    def __init__(self) -> None:
        self.echo_server = ManagedProcess("Echo UDP", ECHO_SERVER_SCRIPT)
        self.chat_server = ManagedProcess("Chat UDP", CHAT_SERVER_SCRIPT)
        self.alice = ManagedProcess("Chat Alice", CHAT_CLIENT_SCRIPT, ["Alice"])
        self.bob = ManagedProcess("Chat Bob", CHAT_CLIENT_SCRIPT, ["Bob"])

    def start_servers(self, environment: dict[str, str]) -> None:
        """Verifica as portas, inicia os dois servidores e confirma que subiram.

        Args:
            environment: Variáveis de ambiente já preparadas para UTF-8.

        Raises:
            PortInUseError: Se `5000/UDP` ou `5001/UDP` já estiverem em uso.
            RuntimeError: Se algum dos servidores encerrar logo após iniciar.
        """
        check_udp_port_available(ECHO_HOST, ECHO_PORT)
        check_udp_port_available(CHAT_HOST, CHAT_PORT)

        self.echo_server.start(environment)
        self.chat_server.start(environment)
        time.sleep(STARTUP_WAIT_SECONDS)

        failed = [
            process
            for process in (self.echo_server, self.chat_server)
            if not process.is_running()
        ]
        if failed:
            details = "\n\n".join(
                f"{process.name}:\n{process.transcript()}" for process in failed
            )
            raise RuntimeError(
                "não foi possível manter os servidores UDP em execução.\n"
                f"{details}"
            )

    def run_echo_exchange(self, environment: dict[str, str]) -> str:
        """Executa uma troca única de Echo e retorna a saída do cliente.

        Args:
            environment: Variáveis de ambiente já preparadas para UTF-8.

        Returns:
            O texto combinado de stdout/stderr do cliente Echo.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-u", str(ECHO_CLIENT_SCRIPT), ECHO_DEMO_MESSAGE],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=ECHO_CLIENT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return "o cliente Echo não respondeu a tempo"

        standard_output = result.stdout or ""
        standard_error = result.stderr or ""
        combined_output = (standard_output + standard_error).strip()
        return combined_output or "sem saída do cliente Echo"

    def run_chat_conversation(self, environment: dict[str, str]) -> None:
        """Inicia dois clientes de chat e simula uma troca de mensagens entre eles.

        Args:
            environment: Variáveis de ambiente já preparadas para UTF-8.
        """
        self.alice.start(environment)
        self.bob.start(environment)
        time.sleep(STARTUP_WAIT_SECONDS)

        self.alice.send_line(ALICE_DEMO_MESSAGE)
        time.sleep(MESSAGE_WAIT_SECONDS)
        self.bob.send_line(BOB_DEMO_MESSAGE)
        time.sleep(MESSAGE_WAIT_SECONDS)

        self.alice.close_stdin()
        self.bob.close_stdin()

        for process in (self.alice, self.bob):
            if process.process is not None:
                try:
                    process.process.wait(timeout=SHUTDOWN_WAIT_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
        time.sleep(0.2)

    def stop_all(self) -> None:
        """Encerra todos os processos gerenciados, garantindo que nada fique órfão."""
        for process in (self.bob, self.alice, self.chat_server, self.echo_server):
            process.stop()


def print_section(title: str) -> None:
    """Imprime um cabeçalho de seção no terminal da demonstração.

    Args:
        title: Texto do cabeçalho a exibir.
    """
    print(f"\n=== {title} ===")


def main() -> int:
    """Ponto de entrada da demonstração integrada Echo + Chat.

    Returns:
        Código de saída do processo (0 para sucesso, 1 para erro, 130 se
        interrompido pelo usuário).
    """
    configure_parent_encoding()
    environment = build_subprocess_environment()
    demo = UdpDemo()

    try:
        print_section("Iniciando servidores UDP")
        demo.start_servers(environment)
        print(f"Echo UDP ativo em {ECHO_HOST}:{ECHO_PORT}")
        print(f"Chat UDP ativo em {CHAT_HOST}:{CHAT_PORT}")
        print(
            "Se for capturar o tráfego, inicie o Wireshark/tcpdump agora "
            "com o filtro: udp.port == 5000 || udp.port == 5001"
        )

        print_section("Demonstração do Echo (porta 5000)")
        print(demo.run_echo_exchange(environment))

        print_section("Demonstração do Chat (porta 5001) — Alice e Bob")
        demo.run_chat_conversation(environment)
        print("--- Log de Alice ---")
        print(demo.alice.transcript())
        print("--- Log de Bob ---")
        print(demo.bob.transcript())

        print_section("Demonstração concluída")
        return 0
    except PortInUseError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nDemonstração interrompida pelo usuário.", file=sys.stderr)
        return 130
    finally:
        demo.stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
