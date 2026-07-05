"use strict";

const clientIds = ["alice", "bob"];
const state = {
  clients: {},
  messages: { alice: [], bob: [] },
  traffic: [],
  servers: { echo: false, chat: false },
  runtime: { python: "3.x" },
};

const elements = {
  echoForm: document.querySelector("#echo-form"),
  echoMessage: document.querySelector("#echo-message"),
  echoSend: document.querySelector("#echo-send"),
  echoClear: document.querySelector("#echo-clear"),
  echoResult: document.querySelector("#echo-result"),
  echoStatus: document.querySelector("#echo-status"),
  chatStatus: document.querySelector("#chat-status"),
  pythonVersion: document.querySelector("#python-version"),
  connectAll: document.querySelector("#connect-all"),
  resetLab: document.querySelector("#reset-lab"),
  clientPorts: document.querySelector("#client-ports"),
  trafficBody: document.querySelector("#traffic-body"),
  toast: document.querySelector("#toast"),
};

let toastTimer = null;
let refreshInProgress = false;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "A operação não pôde ser concluída.");
  }
  return payload;
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.classList.add("visible");
  toastTimer = window.setTimeout(() => {
    elements.toast.classList.remove("visible");
  }, 4000);
}

function setServerStatus(name, online) {
  const label = elements[`${name}Status`];
  const statusItem = label.closest(".status-item");
  const dot = statusItem.querySelector(".status-dot");
  dot.classList.toggle("offline", !online);
  label.textContent = online ? "ativo" : "inativo";
}

function renderClient(clientId) {
  const client = state.clients[clientId];
  const online = Boolean(client);
  const card = document.querySelector(`[data-client="${clientId}"]`);
  const badge = document.querySelector(`#${clientId}-online`);
  const address = document.querySelector(`#${clientId}-address`);
  const nickname = document.querySelector(`#${clientId}-nickname`);
  const nicknameValue = nickname.value.trim() || client?.nickname || "";
  const input = document.querySelector(`#${clientId}-message`);
  const sendButton = card.querySelector(".message-form button");
  const avatar = card.querySelector(".avatar");
  const label = card.querySelector(".client-identity label");
  const msgLabel = card.querySelector(`label[for="${clientId}-message"]`);
  const msgContainer = card.querySelector(".messages");

  const displayName = nicknameValue || (clientId === "alice" ? "Cliente 1" : "Cliente 2");
  const initial = displayName.charAt(0).toUpperCase();
  avatar.textContent = initial;
  label.textContent = displayName;
  msgLabel.textContent = `Mensagem de ${displayName}`;
  input.placeholder = `Mensagem de ${displayName}...`;
  msgContainer.setAttribute("aria-label", `Mensagens de ${displayName}`);

  badge.textContent = online ? "ONLINE" : "OFFLINE";
  badge.classList.toggle("offline", !online);
  address.textContent = online
    ? `127.0.0.1:${client.local_port}`
    : "desconectado";
  nickname.disabled = online;
  input.disabled = !online;
  sendButton.disabled = !online;
}

function setEchoResult(data) {
  elements.echoResult.replaceChildren();
  elements.echoResult.classList.remove("error");
  if (!data) {
    elements.echoResult.textContent = "Envie uma mensagem para observar a resposta UDP.";
    return;
  }
  if (data.error) {
    elements.echoResult.classList.add("error");
    elements.echoResult.textContent = data.error;
    return;
  }
  const grid = document.createElement("div");
  grid.className = "echo-result-grid";
  const fields = [
    { label: "Resposta", value: `"${data.message}"`, cls: "echo-msg" },
    { label: "Bytes", value: `${data.bytes}`, cls: "echo-bytes" },
    { label: "Latência", value: `${data.latency_ms} ms`, cls: "echo-latency" },
    { label: "Porta do cliente", value: `:${data.client_port}`, cls: "echo-port" },
  ];
  for (const f of fields) {
    const div = document.createElement("div");
    div.className = `echo-field ${f.cls}`;
    const lbl = document.createElement("span");
    lbl.className = "echo-label";
    lbl.textContent = f.label;
    const val = document.createElement("strong");
    val.className = "echo-value";
    val.textContent = f.value;
    div.append(lbl, val);
    grid.append(div);
  }
  elements.echoResult.append(grid);
}

function appendTextElement(parent, className, text, tagName = "span") {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function getNickname(clientId) {
  const input = document.querySelector(`#${clientId}-nickname`);
  const nick = input ? input.value.trim() : "";
  return nick || (clientId === "alice" ? "Cliente 1" : "Cliente 2");
}

function renderMessages(clientId) {
  const container = document.querySelector(`#${clientId}-messages`);
  const messages = state.messages[clientId] || [];
  const client = state.clients[clientId];
  container.replaceChildren();

  if (!messages.length) {
    appendTextElement(
      container,
      "empty-message",
      client
        ? "Aguardando mensagens UDP..."
        : `${getNickname(clientId)} ainda não entrou no chat.`,
      "p",
    );
    return;
  }

  for (const message of messages) {
    if (message.type === "SYSTEM") {
      appendTextElement(
        container,
        "system-message",
        message.message,
        "p",
      );
      continue;
    }

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    if (client && message.nickname === client.nickname) {
      bubble.classList.add("own");
    }
    appendTextElement(bubble, "message-author", message.nickname || "Servidor");
    appendTextElement(bubble, "message-text", message.message);
    appendTextElement(bubble, "message-time", message.time);
    container.append(bubble);
  }
  container.scrollTop = container.scrollHeight;
}

function renderTraffic() {
  elements.trafficBody.replaceChildren();
  if (!state.traffic.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.className = "empty-table";
    cell.textContent = "Execute uma ação para gerar tráfego UDP.";
    row.append(cell);
    elements.trafficBody.append(row);
    return;
  }

  for (const item of state.traffic.slice(0, 30)) {
    const row = document.createElement("tr");
    appendTextElement(row, "", item.time, "td");

    const appCell = document.createElement("td");
    appendTextElement(
      appCell,
      `traffic-app ${item.app}`,
      item.app,
    );
    row.append(appCell);

    const directionCell = appendTextElement(
      row,
      `traffic-direction ${item.direction.toLowerCase()}`,
      item.direction,
      "td",
    );
    directionCell.title =
      item.direction === "TX" ? "Datagrama enviado" : "Datagrama recebido";

    appendTextElement(row, "", item.source, "td");
    appendTextElement(row, "", item.destination, "td");
    appendTextElement(row, "", String(item.bytes), "td");
    appendTextElement(row, "", item.event, "td");
    elements.trafficBody.append(row);
  }
}

function renderState() {
  setServerStatus("echo", Boolean(state.servers.echo));
  setServerStatus("chat", Boolean(state.servers.chat));
  elements.pythonVersion.textContent = state.runtime.python;
  for (const clientId of clientIds) {
    renderClient(clientId);
    renderMessages(clientId);
  }

  const ports = clientIds
    .map((clientId) => state.clients[clientId]?.local_port)
    .filter(Boolean);
  elements.clientPorts.replaceChildren();
  if (ports.length) {
    for (const port of ports) {
      const tag = document.createElement("span");
      tag.className = "port-tag";
      tag.textContent = `:${port}`;
      elements.clientPorts.append(tag);
    }
  } else {
    elements.clientPorts.textContent = "portas efêmeras";
  }

  const allConnected = clientIds.every((clientId) => state.clients[clientId]);
  const nick1 = getNickname("alice");
  const nick2 = getNickname("bob");
  elements.connectAll.textContent = allConnected
    ? `${nick1} e ${nick2} conectados`
    : `Conectar ${nick1} e ${nick2}`;
  elements.connectAll.disabled = allConnected;
  renderTraffic();
}

async function refreshState() {
  if (refreshInProgress) {
    return;
  }
  refreshInProgress = true;
  try {
    Object.assign(state, await api("/api/state"));
    renderState();
  } catch (error) {
    setServerStatus("echo", false);
    setServerStatus("chat", false);
  } finally {
    refreshInProgress = false;
  }
}

async function joinClient(clientId) {
  const nickname = document.querySelector(`#${clientId}-nickname`).value;
  await api("/api/chat/join", {
    method: "POST",
    body: JSON.stringify({ client_id: clientId, nickname }),
  });
}

elements.echoForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.echoSend.disabled = true;
  setEchoResult({ error: "Aguardando resposta UDP..." });
  try {
    const result = await api("/api/echo", {
      method: "POST",
      body: JSON.stringify({ message: elements.echoMessage.value }),
    });
    setEchoResult(result);
    showToast("Datagrama Echo enviado e recebido.");
    await refreshState();
  } catch (error) {
    setEchoResult({ error: error.message });
    showToast(error.message, true);
  } finally {
    elements.echoSend.disabled = false;
  }
});

elements.echoClear.addEventListener("click", () => {
  elements.echoMessage.value = "";
  elements.echoMessage.focus();
  setEchoResult(null);
});

elements.connectAll.addEventListener("click", async () => {
  elements.connectAll.disabled = true;
  try {
    for (const clientId of clientIds) {
      if (!state.clients[clientId]) {
        await joinClient(clientId);
      }
    }
    const nickA = getNickname("alice");
    const nickB = getNickname("bob");
    showToast(`${nickA} e ${nickB} entraram no Chat UDP.`);
    await refreshState();
  } catch (error) {
    showToast(error.message, true);
    await refreshState();
  } finally {
    const allConnected = clientIds.every(
      (clientId) => state.clients[clientId],
    );
    elements.connectAll.disabled = allConnected;
  }
});

for (const form of document.querySelectorAll(".message-form")) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const clientId = form.dataset.client;
    const input = form.querySelector("input");
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      await api("/api/chat/message", {
        method: "POST",
        body: JSON.stringify({
          client_id: clientId,
          message: input.value,
        }),
      });
      input.value = "";
      input.focus();
      window.setTimeout(refreshState, 80);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
}

elements.resetLab.addEventListener("click", async () => {
  elements.resetLab.disabled = true;
  try {
    await api("/api/reset", {
      method: "POST",
      body: JSON.stringify({}),
    });
    setEchoResult(null);
    showToast("Laboratório reiniciado.");
    await refreshState();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements.resetLab.disabled = false;
  }
});

refreshState();
window.setInterval(refreshState, 500);
