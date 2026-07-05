import argparse
import json
import socket
import sys

from constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    MAX_DATAGRAM_SIZE,
    MESSAGE_TYPE_ERROR,
    MESSAGE_TYPE_JOIN,
    MESSAGE_TYPE_JOIN_ACK,
    MESSAGE_TYPE_LEAVE,
    MESSAGE_TYPE_MSG,
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
                message = json.loads(data.decode("utf-8"))
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
                    error_msg = json.dumps(
                        {"type": MESSAGE_TYPE_ERROR, "message": "Apelido já em uso"}
                    ).encode("utf-8")
                    server.sendto(error_msg, client_address)
                else:
                    clients[client_address] = nickname
                    ack_msg = json.dumps({"type": MESSAGE_TYPE_JOIN_ACK}).encode("utf-8")
                    server.sendto(ack_msg, client_address)
                    
                    broadcast_msg = json.dumps(
                        {"type": MESSAGE_TYPE_JOIN, "nickname": nickname}
                    ).encode("utf-8")
                    for addr in clients:
                        if addr != client_address:
                            server.sendto(broadcast_msg, addr)
            
            elif msg_type == MESSAGE_TYPE_MSG:
                if client_address not in clients:
                    continue
                content = message.get("content")
                if not content:
                    continue
                nickname = clients[client_address]
                broadcast_msg = json.dumps(
                    {"type": MESSAGE_TYPE_MSG, "nickname": nickname, "content": content}
                ).encode("utf-8")
                for addr in clients:
                    if addr != client_address:
                        server.sendto(broadcast_msg, addr)
                        
            elif msg_type == MESSAGE_TYPE_LEAVE:
                if client_address not in clients:
                    continue
                nickname = clients[client_address]
                del clients[client_address]
                broadcast_msg = json.dumps(
                    {"type": MESSAGE_TYPE_LEAVE, "nickname": nickname}
                ).encode("utf-8")
                for addr in list(clients.keys()):
                    server.sendto(broadcast_msg, addr)


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
