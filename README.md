# Redes GP06 — Aplicações UDP (Echo + Chat)

Projeto acadêmico de Redes de Computadores: duas aplicações sobre UDP
(**Echo** na porta `5000` e **Chat** com múltiplos clientes na porta `5001`)
rodando simultaneamente no mesmo host, com uma demonstração integrada e
material de apoio para captura e análise de tráfego.

## Requisitos

- **Python 3.10 ou superior** (testado em Python 3.14, Windows).
- Nenhuma dependência externa: tudo usa apenas a biblioteca padrão do Python
  (`socket`, `argparse`, `json`, `subprocess`, `http.server`).
- Portas `5000/UDP` e `5001/UDP` livres na máquina local (e `8080/TCP` se for
  usar a Central Web).
- (Opcional, apenas para captura de tráfego) [Wireshark](https://www.wireshark.org/)
  ou `tcpdump`.

## Estrutura do projeto

```
.
├── scripts/
│   ├── run_demo.py        # Demonstração integrada Echo + Chat em um único comando
│   └── run_web.py         # Central web (interface gráfica no navegador)
├── evidencias/
│   └── captura-real.pcapng # Captura real da demonstração na interface de loopback
├── src/
│   ├── echo/
│   │   ├── server.py      # Servidor Echo UDP (porta 5000)
│   │   └── client.py      # Cliente Echo UDP (uma mensagem, uma resposta)
│   ├── chat/
│   │   ├── server.py      # Servidor de Chat UDP (porta 5001, múltiplos clientes)
│   │   ├── client.py      # Cliente de Chat UDP (interativo, via terminal)
│   │   └── constants/     # Constantes compartilhadas do protocolo de chat
│   └── web/
│       └── server.py      # Ponte HTTP local usada pela Central Web
└── web/                    # Front-end estático da Central Web (HTML/CSS/JS)
```

## Como executar

### 1. Echo UDP (porta 5000)

Terminal do servidor:

```
python src/echo/server.py
```

Terminal do cliente (uma mensagem por execução):

```
python src/echo/client.py "sua mensagem aqui"
```

Parâmetros opcionais em ambos: `--host` (padrão `127.0.0.1`), `--port`
(padrão `5000`); o cliente aceita também `--timeout` (padrão `3` segundos).

### 2. Chat UDP (porta 5001)

Terminal do servidor:

```
python src/chat/server.py
```

Um terminal por cliente (repita para cada participante):

```
python src/chat/client.py Alice
python src/chat/client.py Bob
```

Digite uma mensagem e pressione Enter para enviá-la a todos os outros
clientes conectados. Encerre com `Ctrl+C` (o cliente avisa o servidor antes
de sair).

### 3. Demonstração integrada (um único comando)

```
python scripts/run_demo.py
```

Esse script:
- verifica se as portas `5000/UDP` e `5001/UDP` estão livres antes de começar;
- inicia o servidor Echo e o servidor de Chat simultaneamente;
- executa uma troca de Echo automaticamente;
- simula uma conversa entre dois clientes de chat (Alice e Bob);
- imprime tudo no terminal e encerra todos os processos ao final (sucesso,
  erro ou `Ctrl+C`), sem deixar nada ocupando as portas depois.

Funciona em qualquer terminal Windows (inclusive com página de código
`cp1252`) sem precisar configurar variáveis de ambiente antes — a
codificação UTF-8 é forçada internamente para os subprocessos e para a
própria saída do script, preservando acentos nos logs.

### 4. Central Web (opcional, interface gráfica no navegador)

```
python scripts/run_web.py
```

Abre `http://127.0.0.1:8080` no navegador, iniciando Echo e Chat por trás de
uma interface visual. Use `--no-browser` para não abrir o navegador
automaticamente. O navegador usa HTTP apenas para conversar com a ponte local
em Python; as trocas exibidas nos painéis Echo e Chat continuam passando por
sockets UDP reais nas portas `5000` e `5001`.

## Captura e análise de tráfego

O repositório inclui `evidencias/captura-real.pcapng`, uma captura real feita
na interface de loopback durante a execução de `scripts/run_demo.py`. Ela
contém 16 datagramas e pode ser aberta diretamente no Wireshark. A captura
mostra:

- requisição e resposta do Echo na porta `5000`;
- entrada de Alice e Bob no Chat (`JOIN`/`WELCOME`);
- mensagens retransmitidas pelo servidor (`MSG`/`CHAT`);
- saída dos clientes (`LEAVE`/`BYE`);
- portas efêmeras distintas escolhidas pelo sistema operacional.

Para inspecionar somente os pacotes relevantes, abra o arquivo e aplique:

```
udp.port == 5000 || udp.port == 5001
```

As portas efêmeras variam em cada execução. Para produzir uma nova captura,
siga o procedimento abaixo.

### Passo a passo (Wireshark)

1. Abra o Wireshark e selecione a interface de **loopback**
   (`Adapter for loopback traffic capture` no Windows, `lo` no Linux/macOS).
2. No campo de filtro, use:
   ```
   udp.port == 5000 || udp.port == 5001
   ```
3. Clique em iniciar a captura **antes** de rodar `scripts/run_demo.py` (ou
   antes de abrir os servidores/clientes manualmente).
4. Rode a demonstração normalmente.
5. Pare a captura ao final.
6. Para cada datagrama, observe na lista (ou no painel de detalhes, seção
   `User Datagram Protocol`):
   - **Source/Destination** (IP e porta de origem/destino);
   - **Length** (tamanho do datagrama);
   - Clique com o botão direito → `Follow` → `UDP Stream` para ver o
     conteúdo (texto puro no Echo, JSON no Chat).
7. Compare um pacote com porta `5000` e um com porta `5001`: mesmo IP de
   origem e destino (`127.0.0.1`), portas diferentes — é isso que permite
   diferenciar as duas aplicações no mesmo host.
8. Salve a captura (`File` → `Save As...`, formato `.pcapng`) e/ou tire um
   print da lista de pacotes como evidência para anexar à entrega.

### Alternativa via linha de comando (tcpdump, Linux/macOS/WSL)

```
sudo tcpdump -i lo -n "udp port 5000 or udp port 5001" -w captura.pcap
```

## Conceitos de rede observados

- **UDP (User Datagram Protocol)**: protocolo de transporte sem conexão e
  orientado a datagramas. Cada mensagem enviada por `sendto()` é um pacote
  independente — não existe um "handshake" antes de trocar dados, o que se
  observa diretamente na captura: o primeiro pacote de cada fluxo já carrega
  dados de aplicação (`JOIN` no chat, a mensagem no Echo), sem nenhum pacote
  de estabelecimento de conexão antes.
- **Portas**: o mesmo host (`127.0.0.1`) atende duas aplicações diferentes
  ao mesmo tempo porque cada uma está associada a uma porta distinta
  (`5000` para o Echo, `5001` para o Chat). É a porta, não o IP, que
  identifica para qual aplicação um datagrama deve ir.
- **Multiplexação**: cada cliente (Echo, Alice, Bob) usa sua própria porta
  local (geralmente uma porta efêmera escolhida pelo sistema operacional)
  para enviar dados a portas de destino diferentes (`5000` ou `5001`) pela
  mesma interface de rede — vários fluxos independentes compartilhando o
  mesmo caminho físico/lógico.
- **Demultiplexação**: quando um datagrama chega à máquina, o sistema
  operacional usa a porta de destino para decidir a qual processo entregá-lo
  — datagramas para `5000` vão exclusivamente para o processo do servidor
  Echo, e datagramas para `5001` vão exclusivamente para o processo do
  servidor de Chat, mesmo os dois rodando ao mesmo tempo no mesmo host.
- **Ausência de conexão**: o UDP não mantém estado de sessão na camada de
  transporte. Por isso o servidor de Chat precisa manter, na própria
  aplicação, um dicionário de clientes ativos (endereço → apelido) e depende
  de mensagens explícitas `JOIN`/`LEAVE` para saber quem está "conectado" —
  não existe isso nativamente no UDP, ao contrário do TCP.

## Limitações do experimento

- **Ambiente local**: todo o tráfego ocorre em `127.0.0.1` (loopback); não
  há rede real envolvida, então efeitos como latência, perda de pacotes ou
  congestionamento não são observados.
- **Poucos clientes**: a demonstração usa apenas dois clientes de chat
  simultâneos; o comportamento do servidor com muitos clientes enviando
  datagramas ao mesmo tempo não foi validado.
- **Estado volátil**: a lista de clientes do chat existe apenas em memória
  no processo do servidor — se ele for reiniciado, todos os apelidos e
  registros de quem está no chat se perdem.
- **Sem garantia de entrega ou ordenação**: por ser UDP, datagramas podem,
  em tese, ser perdidos, duplicados ou chegar fora de ordem; nenhuma das
  aplicações implementa confirmação (ACK), retransmissão ou número de
  sequência.
- **Sem criptografia**: o conteúdo dos datagramas trafega em texto puro
  (Echo) ou JSON legível (Chat) — qualquer captura de tráfego expõe o
  conteúdo das mensagens integralmente, como demonstrado na seção de
  captura acima.
- **Sem autenticação real**: o Chat apenas verifica se um apelido já está
  em uso; não há senha, token ou qualquer verificação de identidade do
  cliente.
