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
  const input = document.querySelector(`#${clientId}-message`);
  const sendButton = card.querySelector(".message-form button");

  badge.textContent = online ? "ONLINE" : "OFFLINE";
  badge.classList.toggle("offline", !online);
  address.textContent = online
    ? `127.0.0.1:${client.local_port}`
    : "desconectado";
  nickname.disabled = online;
  input.disabled = !online;
  sendButton.disabled = !online;
}

function appendTextElement(parent, className, text, tagName = "span") {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
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
        : `${clientId === "alice" ? "Alice" : "Bob"} ainda não entrou no chat.`,
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
  elements.clientPorts.textContent = ports.length
    ? ports.map((port) => `:${port}`).join(" · ")
    : "portas efêmeras";

  const allConnected = clientIds.every((clientId) => state.clients[clientId]);
  elements.connectAll.textContent = allConnected
    ? "Alice e Bob conectados"
    : "Conectar Alice e Bob";
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
  elements.echoResult.classList.remove("error");
  elements.echoResult.textContent = "Aguardando resposta UDP...";
  try {
    const result = await api("/api/echo", {
      method: "POST",
      body: JSON.stringify({ message: elements.echoMessage.value }),
    });
    elements.echoResult.textContent =
      `Resposta idêntica: “${result.message}” · ${result.bytes} bytes · ` +
      `${result.latency_ms} ms · cliente :${result.client_port}`;
    showToast("Datagrama Echo enviado e recebido.");
    await refreshState();
  } catch (error) {
    elements.echoResult.classList.add("error");
    elements.echoResult.textContent = error.message;
    showToast(error.message, true);
  } finally {
    elements.echoSend.disabled = false;
  }
});

elements.echoClear.addEventListener("click", () => {
  elements.echoMessage.value = "";
  elements.echoMessage.focus();
  elements.echoResult.classList.remove("error");
  elements.echoResult.textContent =
    "Envie uma mensagem para observar a resposta UDP.";
});

elements.connectAll.addEventListener("click", async () => {
  elements.connectAll.disabled = true;
  try {
    for (const clientId of clientIds) {
      if (!state.clients[clientId]) {
        await joinClient(clientId);
      }
    }
    showToast("Alice e Bob entraram no Chat UDP.");
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
    elements.echoResult.classList.remove("error");
    elements.echoResult.textContent =
      "Envie uma mensagem para observar a resposta UDP.";
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
