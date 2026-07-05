"""Servidor UDP que devolve cada datagrama ao remetente."""

from __future__ import annotations

import argparse
import socket
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
MAX_DATAGRAM_SIZE = 65_535


def valid_port(value: str) -> int:
    """Converte e valida uma porta informada pela linha de comando."""
    port = int(value)
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("a porta deve estar entre 1 e 65535")
    return port


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Servidor Echo sobre UDP.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"endereço local para escuta (padrão: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=valid_port,
        default=DEFAULT_PORT,
        help=f"porta UDP para escuta (padrão: {DEFAULT_PORT})",
    )
    return parser.parse_args()


def run_server(host: str, port: int) -> None:
    """Recebe datagramas e os devolve sem alterar o conteúdo."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((host, port))
        print(f"Servidor Echo UDP escutando em {host}:{port}")

        while True:
            data, client_address = server.recvfrom(MAX_DATAGRAM_SIZE)
            client_host, client_port = client_address
            message = data.decode("utf-8", errors="replace")
            print(
                f"Recebido de {client_host}:{client_port} "
                f"({len(data)} bytes): {message!r}"
            )
            server.sendto(data, client_address)


def main() -> int:
    args = parse_args()

    try:
        run_server(args.host, args.port)
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    except OSError as error:
        print(f"Erro no servidor UDP: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
