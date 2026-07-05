"""Módulo central para constantes do sistema de chat UDP."""

MAX_DATAGRAM_SIZE = 65535
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001

# Timeouts definidos separadamente para servidor e cliente
SOCKET_TIMEOUT_SECONDS_SERVER = 1.0
SOCKET_TIMEOUT_SECONDS_CLIENT = 2.0

ENCODING_UTF8 = "utf-8"

# Constantes de Protocolo (Tipos de Mensagem)
MESSAGE_TYPE_JOIN = "JOIN"
MESSAGE_TYPE_MSG = "MSG"
MESSAGE_TYPE_LEAVE = "LEAVE"
MESSAGE_TYPE_JOIN_ACK = "JOIN_ACK"
MESSAGE_TYPE_ERROR = "ERROR"
