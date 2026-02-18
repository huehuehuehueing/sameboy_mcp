/* SameBoy Dashboard — WebSocket client */

(() => {
  "use strict";

  // ── Theme toggle ───────────────────────────────
  function applyTheme(theme) {
    if (theme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "light" ? "\u263E" : "\u2606";
  }

  const savedTheme = localStorage.getItem("sameboy-dashboard-theme") || "dark";
  applyTheme(savedTheme);

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
        const next = current === "light" ? "dark" : "light";
        applyTheme(next);
        localStorage.setItem("sameboy-dashboard-theme", next);
      });
    }
  });

  // ── State ───────────────────────────────────────
  let ws = null;
  let reconnectTimer = null;
  const RECONNECT_MS = 2000;
  let prevRegisters = {};
  let frameCount = 0;
  let lastFpsTime = performance.now();
  let fpsFrames = 0;
  let lastAgentStateTime = 0;

  // ── DOM refs ────────────────────────────────────
  const canvas = document.getElementById("game-canvas");
  const ctx = canvas.getContext("2d");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const fpsEl = document.getElementById("fps-counter");
  const registersEl = document.getElementById("registers-body");
  const disasmEl = document.getElementById("disasm-body");
  const llmMessages = document.getElementById("llm-messages");
  const stateEl = document.getElementById("state-body");
  const promptInput = document.getElementById("prompt-input");
  const promptSend = document.getElementById("prompt-send");
  const frameIndicator = document.getElementById("frame-indicator");

  // Canvas setup
  canvas.width = 320;
  canvas.height = 288;
  ctx.imageSmoothingEnabled = false;

  // ── WebSocket ───────────────────────────────────

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/dashboard/ws`;

    ws = new WebSocket(url);
    ws.binaryType = "blob";

    ws.onopen = () => {
      statusDot.classList.add("connected");
      statusText.textContent = "Connected";
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onclose = () => {
      statusDot.classList.remove("connected");
      statusText.textContent = "Reconnecting\u2026";
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (evt) => {
      if (evt.data instanceof Blob) {
        handleFrame(evt.data);
      } else {
        try {
          const msg = JSON.parse(evt.data);
          handleEvent(msg);
        } catch (e) { /* ignore parse errors */ }
      }
    };
  }

  function scheduleReconnect() {
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(connect, RECONNECT_MS);
    }
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }

  // ── Frame rendering ─────────────────────────────

  async function handleFrame(blob) {
    try {
      const bitmap = await createImageBitmap(blob);
      ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();

      // FPS calculation
      fpsFrames++;
      const now = performance.now();
      if (now - lastFpsTime >= 1000) {
        const fps = Math.round(fpsFrames * 1000 / (now - lastFpsTime));
        fpsEl.textContent = `${fps} fps`;
        fpsFrames = 0;
        lastFpsTime = now;
      }
    } catch (e) {
      // Ignore decode errors
    }
  }

  // ── Event dispatch ──────────────────────────────

  function handleEvent(msg) {
    switch (msg.type) {
      case "snapshot":
        updateSnapshot(msg.data);
        break;
      case "agent_state":
        lastAgentStateTime = performance.now();
        updateGameState(msg.data);
        break;
      case "llm_message":
        addLlmMessage(msg.data);
        break;
      case "llm_tool_call":
        addLlmToolCall(msg.data);
        break;
      case "agent_decision":
        addLlmDecision(msg.data);
        break;
      case "panel_data":
        updatePanel(msg.data);
        break;
      case "agent_actions":
        if (msg.data.actions) updateAgentActions(msg.data.actions);
        // ignore trigger events ({"trigger": "..."}) — those are for the agent
        break;
    }
  }

  // ── Snapshot (registers + disasm) ───────────────

  function updateSnapshot(data) {
    if (data.registers) updateRegisters(data.registers);
    if (data.disassembly) updateDisassembly(data.disassembly, data.registers?.PC);
    if (data.frame_count != null) {
      frameCount = data.frame_count;
      if (frameIndicator) {
        frameIndicator.textContent = `F:${frameCount}`;
      }
    }
    if (data.status) {
      updateEmulatorStatus(data.status, data.activity);
    }
    // Use plugin game_state from snapshot when no recent agent state
    if (data.game_state) {
      const agentStale = (performance.now() - lastAgentStateTime) > 5000;
      if (agentStale || lastAgentStateTime === 0) {
        updateGameState(data.game_state);
      }
    }
  }

  function updateRegisters(regs) {
    const pairs = [
      ["AF", regs.AF], ["BC", regs.BC], ["DE", regs.DE],
      ["HL", regs.HL], ["SP", regs.SP], ["PC", regs.PC],
    ];

    let html = '<div class="register-grid">';
    for (const [name, value] of pairs) {
      const hex = value.toString(16).toUpperCase().padStart(4, "0");
      const changed = prevRegisters[name] !== undefined && prevRegisters[name] !== value;
      html += `<div class="register-row">
        <span class="reg-name">${name}</span>
        <span class="reg-value${changed ? " changed" : ""}">${hex}</span>
      </div>`;
    }
    html += "</div>";

    // Flags
    if (regs.flags) {
      html += '<div class="flags-row">';
      for (const [flag, val] of Object.entries(regs.flags)) {
        html += `<span class="flag">
          <span class="flag-name">${flag}</span>
          <span class="flag-val ${val ? "set" : "clear"}">${val ? "1" : "0"}</span>
        </span>`;
      }
      html += "</div>";
    }

    registersEl.innerHTML = html;
    prevRegisters = { AF: regs.AF, BC: regs.BC, DE: regs.DE, HL: regs.HL, SP: regs.SP, PC: regs.PC };
  }

  function updateDisassembly(text, pc) {
    const lines = text.split("\n").filter(l => l.trim());
    let html = "";
    for (const line of lines) {
      // Parse "ADDR: MNEMONIC OPERANDS" format
      const match = line.match(/^\s*([0-9A-Fa-f]{1,4}):\s+(.+)/);
      if (match) {
        const addr = match[1].toUpperCase().padStart(4, "0");
        const rest = match[2];
        const parts = rest.split(/\s+/);
        const mnemonic = parts[0] || "";
        const operands = parts.slice(1).join(" ");
        const addrNum = parseInt(addr, 16);
        const isCurrent = pc !== undefined && addrNum === pc;

        html += `<div class="disasm-line${isCurrent ? " current" : ""}">
          <span class="disasm-addr">${addr}</span>
          <span class="disasm-mnemonic">${esc(mnemonic)}</span>
          <span class="disasm-operands">${esc(operands)}</span>
        </div>`;
      } else {
        html += `<div class="disasm-line"><span class="disasm-operands">${esc(line)}</span></div>`;
      }
    }
    disasmEl.innerHTML = html;
  }

  function updateEmulatorStatus(status, activity) {
    // Show "Active"/"Idle" instead of raw "PAUSED" when emulator is paused between commands
    let displayState = status.state || "—";
    if (displayState === "PAUSED" && activity) {
      displayState = activity === "active" ? "Active" : "Idle";
    }

    const items = [
      ["State", displayState],
      ["ROM", status.rom_title || "—"],
      ["Frame", frameCount.toLocaleString()],
    ];
    if (status.is_cgb != null) items.push(["CGB", status.is_cgb ? "Yes" : "No"]);
    if (status.trace_enabled) items.push(["Trace", "On"]);
    if (status.breakpoint_count) items.push(["BPs", status.breakpoint_count]);
    if (status.live_display) items.push(["Display", "On"]);

    updateStateGrid("emu-status", items);
  }

  // ── Game State ──────────────────────────────────

  function updateGameState(data) {
    const items = [];
    if (data.mode) items.push(["Mode", data.mode]);
    if (data.map_name) items.push(["Map", data.map_name]);
    if (data.map_id != null) items.push(["Map ID", data.map_id]);
    if (data.player_x != null) items.push(["Pos", `(${data.player_x}, ${data.player_y})`]);
    if (data.party_count != null) items.push(["Party", data.party_count]);
    if (data.badge_count != null) items.push(["Badges", `${data.badge_count}/8`]);

    updateStateGrid("game-status", items);
  }

  function updateStateGrid(sectionId, items) {
    let section = document.getElementById(sectionId);
    if (!section) {
      // Create section in state panel
      section = document.createElement("div");
      section.id = sectionId;
      section.className = "state-section";
      stateEl.appendChild(section);
    }

    let html = '<div class="state-grid">';
    for (const [label, value] of items) {
      html += `<span class="state-label">${esc(label)}</span>`;
      html += `<span class="state-value">${esc(String(value))}</span>`;
    }
    html += "</div>";
    section.innerHTML = html;
  }

  // ── LLM Log ─────────────────────────────────────

  const MAX_MESSAGES = 200;

  function addLlmMessage(data) {
    const role = data.role || "system";
    const content = data.content || "";
    const truncated = content.length > 500 ? content.slice(0, 500) + "\u2026" : content;

    const el = document.createElement("div");
    el.className = `llm-msg role-${role}`;
    el.innerHTML = `<span class="msg-role">${esc(role)}</span>${esc(truncated)}`;
    llmMessages.appendChild(el);

    trimMessages();
    scrollToBottom();
  }

  function addLlmToolCall(data) {
    const name = data.name || "?";
    const args = data.args ? JSON.stringify(data.args) : "";
    const result = data.result ? JSON.stringify(data.result).slice(0, 200) : "";

    const el = document.createElement("div");
    el.className = "llm-msg role-tool";
    el.innerHTML = `<span class="msg-role">tool</span>${esc(name)}(${esc(args)})`;
    if (result) {
      el.innerHTML += ` \u2192 ${esc(result)}`;
    }
    llmMessages.appendChild(el);

    trimMessages();
    scrollToBottom();
  }

  function addLlmDecision(data) {
    const action = data.action || "?";
    const reasoning = data.reasoning || "";

    const el = document.createElement("div");
    el.className = "llm-msg role-decision";
    el.innerHTML = `<span class="msg-role">decision</span><strong>${esc(action)}</strong>`;
    if (data.direction) el.innerHTML += ` ${esc(data.direction)}`;
    if (reasoning) el.innerHTML += ` \u2014 ${esc(reasoning)}`;
    llmMessages.appendChild(el);

    trimMessages();
    scrollToBottom();
  }

  function trimMessages() {
    while (llmMessages.children.length > MAX_MESSAGES) {
      llmMessages.removeChild(llmMessages.firstChild);
    }
  }

  function scrollToBottom() {
    const body = llmMessages.closest(".panel-body");
    if (body) body.scrollTop = body.scrollHeight;
  }

  // ── Plugin panels ───────────────────────────────

  function updatePanel(data) {
    const id = data.panel_id;
    const content = data.content || "";
    const el = document.getElementById(`panel-${id}`);
    if (el) {
      const body = el.querySelector(".panel-body");
      if (body) body.textContent = content;
    }
  }

  // ── Agent action buttons ────────────────────────

  function updateAgentActions(actions) {
    const container = document.getElementById("agent-actions-container");
    const section = document.getElementById("agent-actions-section");
    if (!container || !section) return;

    // Group by action.group
    const groups = {};
    for (const action of actions) {
      const group = action.group || "default";
      if (!groups[group]) groups[group] = [];
      groups[group].push(action);
    }

    let html = "";
    for (const [groupName, groupActions] of Object.entries(groups)) {
      html += `<div class="agent-action-group">`;
      html += `<div class="agent-action-group-label">${esc(groupName)}</div>`;
      html += `<div class="agent-action-buttons">`;
      for (const action of groupActions) {
        html += `<button class="btn-agent-action" data-action-id="${esc(action.id)}">${esc(action.label)}</button>`;
      }
      html += `</div></div>`;
    }
    container.innerHTML = html;
    section.style.display = "";

    // Bind click handlers
    container.querySelectorAll("[data-action-id]").forEach((btn) => {
      btn.addEventListener("mousedown", () => {
        const id = btn.dataset.actionId;
        send({ type: "agent_action", action_id: id });
        addLlmMessage({ role: "agent", content: `[action] ${id}` });
        btn.classList.add("pressed");
        setTimeout(() => btn.classList.remove("pressed"), 200);
      });
    });
  }

  // ── Prompt injection ────────────────────────────

  function sendPrompt() {
    const text = promptInput.value.trim();
    if (!text) return;
    send({ type: "inject_prompt", text });

    // Show locally
    addLlmMessage({ role: "injection", content: text });
    promptInput.value = "";
  }

  promptSend.addEventListener("click", sendPrompt);
  promptInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  });

  // ── Key controls ────────────────────────────────

  const keyButtons = document.querySelectorAll("[data-key]");
  keyButtons.forEach((btn) => {
    btn.addEventListener("mousedown", () => {
      const key = btn.dataset.key;
      btn.classList.add("pressed");
      send({ type: "press_key", key });
      setTimeout(() => btn.classList.remove("pressed"), 150);
    });
  });

  // Keyboard shortcuts (when not focused on input)
  document.addEventListener("keydown", (e) => {
    if (e.target === promptInput) return;

    const keyMap = {
      ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
      z: "a", x: "b", Enter: "start", Shift: "select", Backspace: "select",
    };
    const gbKey = keyMap[e.key];
    if (gbKey) {
      e.preventDefault();
      send({ type: "press_key", key: gbKey });
      // Highlight button
      const btn = document.querySelector(`[data-key="${gbKey}"]`);
      if (btn) {
        btn.classList.add("pressed");
        setTimeout(() => btn.classList.remove("pressed"), 150);
      }
    }
  });

  // ── Utility ─────────────────────────────────────

  function esc(s) {
    const el = document.createElement("span");
    el.textContent = s;
    return el.innerHTML;
  }

  // ── Init ────────────────────────────────────────
  connect();

})();
