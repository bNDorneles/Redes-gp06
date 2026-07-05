import argparse
import socket
import sys
import json
from typing import Dict, Tuple

MAX_DATAGRAM_SIZE = 65535


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servidor UDP de Chat.")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Endereço de escuta do servidor (padrão: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Porta de escuta do servidor (padrão: 5001)",
    )
    return parser.parse_args()


def run_server(host: str, port: int) -> None:
    clients: Dict[Tuple[str, int], str] = {}

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((host, port))
        server.settimeout(1.0)
        print(f"Servidor Chat UDP escutando em {host}:{port}")

        while True:
            try:
                data, client_address = server.recvfrom(MAX_DATAGRAM_SIZE)
            except socket.timeout:
                continue
            except OSError as e:
                # Trata erros inesperados do socket (como erro 10054 no Windows)
                continue

            try:
                message = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # Validação estrutural básica
            if not isinstance(message, dict):
                continue

            msg_type = message.get("type")
            if not msg_type:
                continue

            if msg_type == "JOIN":
                nickname = message.get("nickname")
                if not nickname:
                    continue
                
                # Verifica apelido duplicado (ignorando o remetente)
                nickname_in_use = False
                for addr, nick in clients.items():
                    if nick == nickname and addr != client_address:
                        nickname_in_use = True
                        break
                
                if nickname_in_use:
                    error_msg = json.dumps({"type": "ERROR", "message": "Apelido já em uso"}).encode("utf-8")
                    server.sendto(error_msg, client_address)
                else:
                    clients[client_address] = nickname
                    # Confirma o JOIN para o remetente
                    ack_msg = json.dumps({"type": "JOIN_ACK"}).encode("utf-8")
                    server.sendto(ack_msg, client_address)
                    
                    # Faz broadcast da notificação de entrada
                    broadcast_msg = json.dumps({"type": "JOIN", "nickname": nickname}).encode("utf-8")
                    for addr in clients:
                        if addr != client_address:
                            server.sendto(broadcast_msg, addr)
            
            elif msg_type == "MSG":
                if client_address not in clients:
                    continue
                content = message.get("content")
                if not content:
                    continue
                nickname = clients[client_address]
                broadcast_msg = json.dumps({"type": "MSG", "nickname": nickname, "content": content}).encode("utf-8")
                for addr in clients:
                    if addr != client_address:
                        server.sendto(broadcast_msg, addr)
                        
            elif msg_type == "LEAVE":
                if client_address not in clients:
                    continue
                nickname = clients[client_address]
                del clients[client_address]
                broadcast_msg = json.dumps({"type": "LEAVE", "nickname": nickname}).encode("utf-8")
                for addr in list(clients.keys()):
                    server.sendto(broadcast_msg, addr)


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
