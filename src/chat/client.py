import argparse
import json
import socket
import sys
import threading

from constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ENCODING_UTF8,
    MAX_DATAGRAM_SIZE,
    MESSAGE_TYPE_ERROR,
    MESSAGE_TYPE_JOIN,
    MESSAGE_TYPE_JOIN_ACK,
    MESSAGE_TYPE_LEAVE,
    MESSAGE_TYPE_MSG,
    SOCKET_TIMEOUT_SECONDS_CLIENT,
)


def configure_encoding() -> None:
    """Configura o codificador padrão de saída e entrada.

    Previne que o cliente termine de forma abrupta por causa de `UnicodeEncodeError`
    quando o terminal não tem suporte para todos os caracteres recebidos (ex: cp1252 no Windows).
    """
    if sys.stdout.encoding.lower() != ENCODING_UTF8:
        sys.stdout.reconfigure(errors="replace")
    if sys.stdin.encoding.lower() != ENCODING_UTF8:
        sys.stdin.reconfigure(errors="replace")


def parse_args() -> argparse.Namespace:
    """Analisa os argumentos de linha de comando para o cliente.

    Returns:
        Um namespace contendo o apelido, host e port.
    """
    parser = argparse.ArgumentParser(description="Cliente UDP de Chat.")
    parser.add_argument(
        "nickname",
        type=str,
        help="Apelido do usuário no chat",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Endereço do servidor (padrão: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Porta do servidor (padrão: {DEFAULT_PORT})",
    )
    return parser.parse_args()


def receive_messages(sock: socket.socket) -> None:
    """Thread dedicada a escutar mensagens recebidas do servidor.

    Args:
        sock: O socket UDP já configurado e conectado ao servidor.
    """
    while True:
        try:
            data, _ = sock.recvfrom(MAX_DATAGRAM_SIZE)
            message = json.loads(data.decode(ENCODING_UTF8))
            
            if not isinstance(message, dict):
                continue
                
            msg_type = message.get("type")
            
            if msg_type == MESSAGE_TYPE_JOIN:
                print(f"\n*** {message.get('nickname')} entrou no chat ***")
            elif msg_type == MESSAGE_TYPE_LEAVE:
                print(f"\n*** {message.get('nickname')} saiu do chat ***")
            elif msg_type == MESSAGE_TYPE_MSG:
                print(f"\n[{message.get('nickname')}]: {message.get('content')}")
        except (socket.timeout, OSError):
            break
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue


def main() -> int:
    """Ponto de entrada principal do script do cliente.

    Realiza o handshake (JOIN) com o servidor de chat e inicializa
    a thread receptora, assumindo a recepção de inputs do usuário.

    Returns:
        Código de saída do processo (0 para sucesso, 1 para erro).
    """
    configure_encoding()
    args = parse_args()
    server_address = (args.host, args.port)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as error:
        print(f"Erro ao criar socket: {error}", file=sys.stderr)
        return 1

    join_msg = json.dumps({"type": MESSAGE_TYPE_JOIN, "nickname": args.nickname}).encode(ENCODING_UTF8)
    
    try:
        sock.sendto(join_msg, server_address)
        sock.settimeout(SOCKET_TIMEOUT_SECONDS_CLIENT)
        
        while True:
            data, _ = sock.recvfrom(MAX_DATAGRAM_SIZE)
            try:
                message = json.loads(data.decode(ENCODING_UTF8))
                if not isinstance(message, dict):
                    continue
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
                
            msg_type = message.get("type")
            if msg_type == MESSAGE_TYPE_JOIN_ACK:
                break
            elif msg_type == MESSAGE_TYPE_ERROR:
                print(f"Erro: {message.get('message')}")
                sock.close()
                return 1
                
    except (socket.timeout, ConnectionResetError):
        print("Erro: Servidor indisponível ou não respondeu a tempo.")
        sock.close()
        return 1
    except OSError as e:
        if getattr(e, "winerror", None) == 10054:
            print("Erro: Servidor indisponível ou não respondeu a tempo.")
        else:
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
                    msg = json.dumps(
                        {"type": MESSAGE_TYPE_MSG, "content": texto}
                    ).encode(ENCODING_UTF8)
                    sock.sendto(msg, server_address)
            except EOFError:
                break
    except KeyboardInterrupt:
        # Interceptado limpamente para enviar LEAVE na cláusula finally
        pass
    finally:
        leave_msg = json.dumps({"type": MESSAGE_TYPE_LEAVE}).encode(ENCODING_UTF8)
        try:
            sock.sendto(leave_msg, server_address)
        except OSError:
            pass
        sock.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
