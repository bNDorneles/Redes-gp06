"""Servidor HTTP local que conecta a interface web aos sockets UDP."""

from __future__ import annotations

import json
import mimetypes
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

HOST = "127.0.0.1"
ECHO_PORT = 5000
CHAT_PORT = 5001
MAX_DATAGRAM_SIZE = 65_535
MAX_UDP_PAYLOAD = 65_507
MAX_HTTP_BODY = 65_536
SOCKET_TIMEOUT = 2.0
WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
CLIENT_IDS = {"alice", "bob"}


class BridgeError(ValueError):
    """Erro de entrada ou comunicação que pode ser exibido ao usuário."""


def log_event(event: str, detail: str = "") -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {event}"
    if detail:
        line += f" · {detail}"
    print(line, flush=True)


def encode_chat(message_type: str, **fields: Any) -> bytes:
    payload = json.dumps(
        {"type": message_type, **fields},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > MAX_UDP_PAYLOAD:
        raise BridgeError("mensagem excede o limite de um datagrama UDP")
    return payload


def decode_chat(payload: bytes) -> dict[str, Any]:
    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BridgeError("servidor retornou uma mensagem inválida") from error
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise BridgeError("servidor retornou uma mensagem inválida")
    return message


@dataclass
class ChatSession:
    client_id: str
    nickname: str
    udp_socket: socket.socket
    local_address: tuple[str, int]
    stop_event: threading.Event = field(default_factory=threading.Event)
    receiver: threading.Thread | None = None


class UdpLabState:
    """Mantém sessões, mensagens e metadados observados nos sockets."""

    def __init__(
        self,
        status_provider: Callable[[], dict[str, bool]] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, ChatSession] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {
            "alice": [],
            "bob": [],
        }
        self._traffic: deque[dict[str, Any]] = deque(maxlen=100)
        self._sequence = 0
        self._status_provider = status_provider or (
            lambda: {"echo": True, "chat": True}
        )

    def _next_id(self) -> int:
        with self._lock:
            self._sequence += 1
            return self._sequence

    def _record_traffic(
        self,
        *,
        app: str,
        direction: str,
        source: tuple[str, int],
        destination: tuple[str, int],
        payload: bytes,
        event: str,
    ) -> None:
        item = {
            "id": self._next_id(),
            "time": datetime.now().strftime("%H:%M:%S"),
            "app": app,
            "direction": direction,
            "source": f"{source[0]}:{source[1]}",
            "destination": f"{destination[0]}:{destination[1]}",
            "bytes": len(payload),
            "event": event,
        }
        with self._lock:
            self._traffic.append(item)

    def _append_message(
        self,
        client_id: str,
        message: dict[str, Any],
    ) -> None:
        message_type = message["type"]
        if message_type not in {"CHAT", "SYSTEM", "ERROR"}:
            return
        event = {
            "id": self._next_id(),
            "type": message_type,
            "nickname": str(message.get("nickname", "")),
            "message": str(message.get("message", "")),
            "time": datetime.now().strftime("%H:%M:%S"),
        }
        with self._lock:
            self._messages[client_id].append(event)
            self._messages[client_id] = self._messages[client_id][-60:]

    @staticmethod
    def _chat_event(message: dict[str, Any]) -> str:
        event = message["type"]
        nickname = message.get("nickname")
        return f"{event} · {nickname}" if nickname else event

    def echo(self, text: Any) -> dict[str, Any]:
        if not isinstance(text, str) or not text:
            raise BridgeError("informe uma mensagem para o Echo")
        payload = text.encode("utf-8")
        if len(payload) > MAX_UDP_PAYLOAD:
            raise BridgeError("mensagem excede o limite de um datagrama UDP")

        started_at = time.perf_counter()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.bind((HOST, 0))
            client.settimeout(SOCKET_TIMEOUT)
            local_address = client.getsockname()
            server_address = (HOST, ECHO_PORT)
            client.sendto(payload, server_address)
            self._record_traffic(
                app="echo",
                direction="TX",
                source=local_address,
                destination=server_address,
                payload=payload,
                event="ECHO request",
            )

            deadline = time.monotonic() + SOCKET_TIMEOUT
            while True:
                try:
                    response, remote_address = client.recvfrom(
                        MAX_DATAGRAM_SIZE
                    )
                    break
                except ConnectionResetError:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise socket.timeout from None
                    client.settimeout(remaining)

            self._record_traffic(
                app="echo",
                direction="RX",
                source=remote_address,
                destination=local_address,
                payload=response,
                event="ECHO response",
            )

        if response != payload:
            raise BridgeError("o servidor Echo alterou o datagrama")
        elapsed_ms = round((time.perf_counter() - started_at) * 1_000, 2)
        log_event(
            "ECHO",
            f"TX → :{ECHO_PORT} · RX ← :{local_address[1]} · "
            f"{len(payload)} bytes · {elapsed_ms}ms",
        )
        return {
            "message": response.decode("utf-8", errors="replace"),
            "bytes": len(response),
            "latency_ms": elapsed_ms,
            "client_port": local_address[1],
        }

    def join_client(self, client_id: Any, nickname: Any) -> dict[str, Any]:
        if client_id not in CLIENT_IDS:
            raise BridgeError("cliente desconhecido")
        if not isinstance(nickname, str) or not nickname.strip():
            raise BridgeError("informe um apelido")
        nickname = nickname.strip()
        if len(nickname) > 24:
            raise BridgeError("apelido deve ter no máximo 24 caracteres")

        with self._lock:
            if client_id in self._sessions:
                raise BridgeError(f"{nickname} já está no chat")

        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind((HOST, 0))
        udp_socket.settimeout(SOCKET_TIMEOUT)
        local_address = udp_socket.getsockname()
        server_address = (HOST, CHAT_PORT)
        join_payload = encode_chat("JOIN", nickname=nickname)

        try:
            udp_socket.sendto(join_payload, server_address)
            self._record_traffic(
                app="chat",
                direction="TX",
                source=local_address,
                destination=server_address,
                payload=join_payload,
                event=f"JOIN · {nickname}",
            )

            pending_messages: list[dict[str, Any]] = []
            while True:
                payload, remote_address = udp_socket.recvfrom(
                    MAX_DATAGRAM_SIZE
                )
                message = decode_chat(payload)
                self._record_traffic(
                    app="chat",
                    direction="RX",
                    source=remote_address,
                    destination=local_address,
                    payload=payload,
                    event=self._chat_event(message),
                )
                if message["type"] == "ERROR":
                    raise BridgeError(str(message.get("message", "entrada recusada")))
                if message["type"] == "WELCOME":
                    break
                pending_messages.append(message)
        except Exception:
            udp_socket.close()
            raise

        session = ChatSession(
            client_id=client_id,
            nickname=nickname,
            udp_socket=udp_socket,
            local_address=local_address,
        )
        with self._lock:
            self._sessions[client_id] = session
            self._messages[client_id] = []
        for message in pending_messages:
            self._append_message(client_id, message)

        udp_socket.settimeout(0.2)
        session.receiver = threading.Thread(
            target=self._receive_chat,
            args=(session,),
            name=f"chat-{client_id}",
            daemon=True,
        )
        session.receiver.start()
        log_event("CHAT JOIN", f"{nickname} ← :{local_address[1]}")
        return {
            "id": client_id,
            "nickname": nickname,
            "local_port": local_address[1],
        }

    def _receive_chat(self, session: ChatSession) -> None:
        while not session.stop_event.is_set():
            try:
                payload, remote_address = session.udp_socket.recvfrom(
                    MAX_DATAGRAM_SIZE
                )
                message = decode_chat(payload)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except (OSError, BridgeError):
                return

            self._record_traffic(
                app="chat",
                direction="RX",
                source=remote_address,
                destination=session.local_address,
                payload=payload,
                event=self._chat_event(message),
            )
            self._append_message(session.client_id, message)

    def send_chat(self, client_id: Any, text: Any) -> None:
        if client_id not in CLIENT_IDS:
            raise BridgeError("cliente desconhecido")
        if not isinstance(text, str) or not text.strip():
            raise BridgeError("digite uma mensagem")
        text = text.strip()
        if len(text) > 1_000:
            raise BridgeError("mensagem deve ter no máximo 1000 caracteres")

        with self._lock:
            session = self._sessions.get(client_id)
        if session is None:
            raise BridgeError("o cliente precisa entrar no chat")

        payload = encode_chat("MSG", message=text)
        server_address = (HOST, CHAT_PORT)
        session.udp_socket.sendto(payload, server_address)
        self._record_traffic(
            app="chat",
            direction="TX",
            source=session.local_address,
            destination=server_address,
            payload=payload,
            event=f"MSG · {session.nickname}",
        )
        self._append_message(client_id, {
            "type": "CHAT",
            "nickname": session.nickname,
            "message": text,
        })
        log_event("CHAT MSG", f"{session.nickname} → :{CHAT_PORT} · {len(payload)} bytes")

    def leave_client(self, client_id: Any) -> None:
        if client_id not in CLIENT_IDS:
            raise BridgeError("cliente desconhecido")
        with self._lock:
            session = self._sessions.pop(client_id, None)
        if session is None:
            return

        payload = encode_chat("LEAVE")
        server_address = (HOST, CHAT_PORT)
        try:
            session.udp_socket.sendto(payload, server_address)
            self._record_traffic(
                app="chat",
                direction="TX",
                source=session.local_address,
                destination=server_address,
                payload=payload,
                event=f"LEAVE · {session.nickname}",
            )
            time.sleep(0.05)
        except OSError:
            pass
        finally:
            log_event("CHAT LEAVE", session.nickname)
            session.stop_event.set()
            session.udp_socket.close()
            if session.receiver:
                session.receiver.join(timeout=0.5)

    def reset(self) -> None:
        log_event("RESET", "reiniciando laboratório")
        for client_id in tuple(CLIENT_IDS):
            self.leave_client(client_id)
        with self._lock:
            self._messages = {"alice": [], "bob": []}
            self._traffic.clear()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            clients = {
                client_id: {
                    "id": client_id,
                    "nickname": session.nickname,
                    "online": True,
                    "local_port": session.local_address[1],
                }
                for client_id, session in self._sessions.items()
            }
            messages = {
                client_id: list(items)
                for client_id, items in self._messages.items()
            }
            traffic = list(reversed(self._traffic))
        return {
            "servers": self._status_provider(),
            "runtime": {
                "python": f"{sys.version_info.major}.{sys.version_info.minor}"
            },
            "clients": clients,
            "messages": messages,
            "traffic": traffic,
        }

    def close(self) -> None:
        self.reset()


class UdpLabHandler(BaseHTTPRequestHandler):
    state: UdpLabState
    web_root = WEB_ROOT

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _send_json(
        self,
        data: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_bytes(payload, "application/json; charset=utf-8", status)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_HTTP_BODY:
            raise BridgeError("corpo da requisição inválido")
        try:
            data = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BridgeError("JSON inválido") from error
        if not isinstance(data, dict):
            raise BridgeError("o corpo deve ser um objeto JSON")
        return data

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            self._send_json(self.state.snapshot())
            return
        if path == "/api/health":
            self._send_json({"status": "ok"})
            return
        log_event("HTTP GET", path)

        static_files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/styles.css": "styles.css",
            "/app.js": "app.js",
        }
        filename = static_files.get(path)
        if filename is None:
            self._send_json(
                {"error": "recurso não encontrado"},
                HTTPStatus.NOT_FOUND,
            )
            return

        file_path = self.web_root / filename
        if not file_path.is_file():
            self._send_json(
                {"error": f"arquivo ausente: {filename}"},
                HTTPStatus.NOT_FOUND,
            )
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "text/plain"
        self._send_bytes(
            file_path.read_bytes(),
            f"{content_type}; charset=utf-8",
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        log_event("HTTP POST", path)
        try:
            data = self._read_json()
            if path == "/api/echo":
                result = self.state.echo(data.get("message"))
                self._send_json(result)
            elif path == "/api/chat/join":
                result = self.state.join_client(
                    data.get("client_id"),
                    data.get("nickname"),
                )
                self._send_json(result, HTTPStatus.CREATED)
            elif path == "/api/chat/message":
                self.state.send_chat(
                    data.get("client_id"),
                    data.get("message"),
                )
                self._send_json({"status": "sent"})
            elif path == "/api/chat/leave":
                self.state.leave_client(data.get("client_id"))
                self._send_json({"status": "left"})
            elif path == "/api/reset":
                self.state.reset()
                self._send_json({"status": "reset"})
            else:
                self._send_json(
                    {"error": "recurso não encontrado"},
                    HTTPStatus.NOT_FOUND,
                )
        except socket.timeout:
            self._send_json(
                {"error": "servidor UDP não respondeu no tempo esperado"},
                HTTPStatus.GATEWAY_TIMEOUT,
            )
        except (BridgeError, OSError, ValueError) as error:
            self._send_json(
                {"error": str(error)},
                HTTPStatus.BAD_REQUEST,
            )


def create_http_server(
    host: str,
    port: int,
    state: UdpLabState,
) -> ThreadingHTTPServer:
    handler = type(
        "ConfiguredUdpLabHandler",
        (UdpLabHandler,),
        {"state": state},
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server
