import argparse
import socket
import sys
import json
import threading

MAX_DATAGRAM_SIZE = 65535


def configure_encoding() -> None:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(errors='replace')
    if sys.stdin.encoding.lower() != 'utf-8':
        sys.stdin.reconfigure(errors='replace')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cliente UDP de Chat.")
    parser.add_argument(
        "nickname",
        type=str,
        help="Apelido do usuário no chat",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Endereço do servidor (padrão: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Porta do servidor (padrão: 5001)",
    )
    return parser.parse_args()


def receive_messages(sock: socket.socket) -> None:
    while True:
        try:
            data, _ = sock.recvfrom(MAX_DATAGRAM_SIZE)
            message = json.loads(data.decode("utf-8"))
            
            if not isinstance(message, dict):
                continue
                
            msg_type = message.get("type")
            
            if msg_type == "JOIN":
                print(f"\n*** {message.get('nickname')} entrou no chat ***")
            elif msg_type == "LEAVE":
                print(f"\n*** {message.get('nickname')} saiu do chat ***")
            elif msg_type == "MSG":
                print(f"\n[{message.get('nickname')}]: {message.get('content')}")
        except (socket.timeout, OSError):
            break
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue


def main() -> int:
    configure_encoding()
    args = parse_args()

    server_address = (args.host, args.port)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as error:
        print(f"Erro ao criar socket: {error}", file=sys.stderr)
        return 1

    # Handshake: Envia JOIN e aguarda JOIN_ACK
    join_msg = json.dumps({"type": "JOIN", "nickname": args.nickname}).encode("utf-8")
    
    try:
        sock.sendto(join_msg, server_address)
        sock.settimeout(2.0)
        
        while True:
            data, _ = sock.recvfrom(MAX_DATAGRAM_SIZE)
            try:
                message = json.loads(data.decode("utf-8"))
                if not isinstance(message, dict):
                    continue
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
                
            msg_type = message.get("type")
            if msg_type == "JOIN_ACK":
                break
            elif msg_type == "ERROR":
                print(f"Erro: {message.get('message')}")
                sock.close()
                return 1
                
    except socket.timeout:
        print("Erro: Servidor indisponível ou não respondeu a tempo.")
        sock.close()
        return 1
    except OSError as e:
        print(f"Erro de conexão: {e}")
        sock.close()
        return 1
        
    sock.settimeout(None)

    recv_thread = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
    recv_thread.start()

    try:
        while True:
            try:
                texto = input()
                if texto.strip():
                    msg = json.dumps({"type": "MSG", "content": texto}).encode("utf-8")
                    sock.sendto(msg, server_address)
            except EOFError:
                break
    except KeyboardInterrupt:
        pass
    finally:
        leave_msg = json.dumps({"type": "LEAVE"}).encode("utf-8")
        try:
            sock.sendto(leave_msg, server_address)
        except OSError:
            pass
        sock.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
