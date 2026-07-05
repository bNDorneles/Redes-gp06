"""Cliente de linha de comando para o servidor Echo UDP."""

from __future__ import annotations

import argparse
import socket
import sys
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_TIMEOUT = 3.0
MAX_UDP_PAYLOAD = 65_507
MAX_DATAGRAM_SIZE = 65_535


def valid_port(value: str) -> int:
    """Converte e valida uma porta informada pela linha de comando."""
    port = int(value)
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("a porta deve estar entre 1 e 65535")
    return port


def positive_timeout(value: str) -> float:
    """Converte e valida o timeout informado pela linha de comando."""
    timeout = float(value)
    if timeout <= 0:
        raise argparse.ArgumentTypeError("o timeout deve ser maior que zero")
    return timeout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cliente Echo sobre UDP.",
    )
    parser.add_argument("message", help="mensagem que será enviada")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"endereço do servidor (padrão: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=valid_port,
        default=DEFAULT_PORT,
        help=f"porta UDP do servidor (padrão: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--timeout",
        type=positive_timeout,
        default=DEFAULT_TIMEOUT,
        help=f"tempo máximo de espera em segundos (padrão: {DEFAULT_TIMEOUT})",
    )
    return parser.parse_args()


def request_echo(
    message: str,
    host: str,
    port: int,
    timeout: float,
) -> tuple[bytes, tuple[str, int]]:
    """Envia uma mensagem e aguarda um datagrama de resposta."""
    payload = message.encode("utf-8")
    if len(payload) > MAX_UDP_PAYLOAD:
        raise ValueError(
            f"a mensagem excede o limite de {MAX_UDP_PAYLOAD} bytes do UDP"
        )

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(timeout)
        client.sendto(payload, (host, port))
        deadline = time.monotonic() + timeout

        while True:
            try:
                return client.recvfrom(MAX_DATAGRAM_SIZE)
            except ConnectionResetError:
                # No Windows, uma resposta ICMP de "porta inalcançável" pode
                # interromper o recvfrom antes do timeout configurado.
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout from None
                client.settimeout(remaining)


def main() -> int:
    args = parse_args()

    try:
        response, server_address = request_echo(
            args.message,
            args.host,
            args.port,
            args.timeout,
        )
    except socket.timeout:
        print(
            f"Tempo esgotado: nenhuma resposta de "
            f"{args.host}:{args.port} em {args.timeout:g}s.",
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as error:
        print(f"Erro no cliente UDP: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCliente encerrado.", file=sys.stderr)
        return 130

    server_host, server_port = server_address
    echoed_message = response.decode("utf-8", errors="replace")
    print(
        f"Resposta de {server_host}:{server_port} "
        f"({len(response)} bytes): {echoed_message}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
