import argparse
import json
import socket
import sys
from typing import Optional

from constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ENCODING_UTF8,
    MAX_DATAGRAM_SIZE,
    MESSAGE_TYPE_BYE,
    MESSAGE_TYPE_CHAT,
    MESSAGE_TYPE_ERROR,
    MESSAGE_TYPE_JOIN,
    MESSAGE_TYPE_LEAVE,
    MESSAGE_TYPE_MSG,
    MESSAGE_TYPE_SYSTEM,
    MESSAGE_TYPE_WELCOME,
    SOCKET_TIMEOUT_SECONDS_SERVER,
)


def parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando para o servidor.

    Returns:
        Um namespace contendo os argumentos host e port.
    """
    parser = argparse.ArgumentParser(description="Servidor UDP de Chat.")
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Endereço de escuta do servidor (padrão: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Porta de escuta do servidor (padrão: {DEFAULT_PORT})",
    )
    return parser.parse_args()


def send_json(sock: socket.socket, message: dict, address: tuple[str, int]) -> None:
    """Serializa e envia um dicionário JSON para um endereço via UDP.

    Args:
        sock: O socket UDP utilizado para o envio.
        message: Dicionário contendo a mensagem a ser enviada.
        address: Tupla (ip, porta) do destinatário.
    """
    try:
        data = json.dumps(message).encode(ENCODING_UTF8)
        sock.sendto(data, address)
    except OSError:
        pass


def broadcast(
    sock: socket.socket,
    message: dict,
    clients: dict[tuple[str, int], str],
    exclude: Optional[tuple[str, int]] = None,
) -> None:
    """Envia uma mensagem JSON para todos os clientes registrados.

    Args:
        sock: O socket UDP utilizado para o envio.
        message: Dicionário contendo a mensagem a ser retransmitida.
        clients: Dicionário contendo o registro de todos os clientes ativos.
        exclude: Tupla (ip, porta) opcional do cliente que não deve receber a mensagem.
    """
    try:
        data = json.dumps(message).encode(ENCODING_UTF8)
    except (TypeError, ValueError):
        return

    for addr in list(clients.keys()):
        if addr != exclude:
            try:
                sock.sendto(data, addr)
            except OSError:
                pass


def run_server(host: str, port: int) -> None:
    """Executa o servidor de chat UDP.

    Mantém o registro de clientes ativos e retransmite mensagens em
    formato JSON seguindo o protocolo da aplicação. Trata pacotes
    malformados de maneira resiliente sem interromper o processo.

    Args:
        host: O endereço IP onde o servidor será vinculado.
        port: A porta UDP onde o servidor escutará.
    """
    clients: dict[tuple[str, int], str] = {}

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((host, port))
        # O timeout permite checar KeyboardInterrupt periodicamente no Windows
        server.settimeout(SOCKET_TIMEOUT_SECONDS_SERVER)
        print(f"Servidor Chat UDP escutando em {host}:{port}")

        while True:
            try:
                data, client_address = server.recvfrom(MAX_DATAGRAM_SIZE)
            except socket.timeout:
                continue
            except OSError:
                # Contorna falhas subjacentes na rede (como ICMP Port Unreachable no Windows)
                continue

            try:
                message = json.loads(data.decode(ENCODING_UTF8))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            if not isinstance(message, dict):
                continue

            msg_type = message.get("type")
            if not msg_type:
                continue

            if msg_type == MESSAGE_TYPE_JOIN:
                nickname = message.get("nickname")
                if not nickname:
                    continue
                
                nickname_in_use = False
                for addr, nick in clients.items():
                    if nick == nickname and addr != client_address:
                        nickname_in_use = True
                        break
                
                if nickname_in_use:
                    send_json(
                        server,
                        {"type": MESSAGE_TYPE_ERROR, "message": "Apelido já em uso"},
                        client_address,
                    )
                else:
                    clients[client_address] = nickname
                    send_json(server, {"type": MESSAGE_TYPE_WELCOME}, client_address)
                    broadcast(
                        server,
                        {"type": MESSAGE_TYPE_SYSTEM, "message": f"{nickname} entrou no chat"},
                        clients,
                        exclude=client_address,
                    )
            
            elif msg_type == MESSAGE_TYPE_MSG:
                if client_address not in clients:
                    continue
                content = message.get("message")
                if not content:
                    continue
                nickname = clients[client_address]
                broadcast(
                    server,
                    {"type": MESSAGE_TYPE_CHAT, "nickname": nickname, "message": content},
                    clients,
                    exclude=client_address,
                )
                        
            elif msg_type == MESSAGE_TYPE_LEAVE:
                if client_address not in clients:
                    continue
                nickname = clients[client_address]
                del clients[client_address]
                broadcast(
                    server,
                    {"type": MESSAGE_TYPE_SYSTEM, "message": f"{nickname} saiu do chat"},
                    clients,
                )
                send_json(server, {"type": MESSAGE_TYPE_BYE}, client_address)


def main() -> int:
    """Ponto de entrada do script do servidor.

    Returns:
        Código de saída do processo (0 para sucesso, 1 para erro).
    """
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
