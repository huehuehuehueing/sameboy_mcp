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
  const screenTextSlot = document.getElementById("screen-text-slot");

  // Canvas setup
  canvas.width = 480;
  canvas.height = 432;
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
        if (msg.data.llm_model) updateLlmStatus(msg.data);
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
      case "panel_registry":
        handlePanelRegistry(msg.data);
        break;
      case "panel_data":
        updatePanel(msg.data);
        break;
      case "agent_actions":
        if (msg.data.actions) updateAgentActions(msg.data.actions);
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
      updateEmulatorStatus(data.status, data.activity, data.current_state);
    }
    if (data.game_state) {
      const agentStale = (performance.now() - lastAgentStateTime) > 5000;
      if (agentStale || lastAgentStateTime === 0) {
        updateGameState(data.game_state);
        if (data.game_state.llm_model) updateLlmStatus(data.game_state);
      }
    }
  }

  // ── Registers (compact horizontal bar) ──────────

  function updateRegisters(regs) {
    const pairs = [
      ["AF", regs.AF], ["BC", regs.BC], ["DE", regs.DE],
      ["HL", regs.HL], ["SP", regs.SP], ["PC", regs.PC],
    ];

    let html = '';
    for (const [name, value] of pairs) {
      const hex = value.toString(16).toUpperCase().padStart(4, "0");
      const changed = prevRegisters[name] !== undefined && prevRegisters[name] !== value;
      html += `<div class="rbar-reg"><span class="reg-name">${name}</span><span class="reg-value${changed ? " changed" : ""}">${hex}</span></div>`;
    }

    if (regs.flags) {
      html += '<div class="rbar-sep"></div>';
      for (const [flag, val] of Object.entries(regs.flags)) {
        html += `<span class="flag"><span class="flag-name">${flag}</span><span class="flag-val ${val ? "set" : "clear"}">${val ? "1" : "0"}</span></span>`;
      }
    }

    registersEl.innerHTML = html;
    prevRegisters = { AF: regs.AF, BC: regs.BC, DE: regs.DE, HL: regs.HL, SP: regs.SP, PC: regs.PC };
  }

  // Classify Z80/GB mnemonics into semantic groups for color-coding
  const MNEMONIC_CLASSES = {
    // Flow control — jumps, calls, returns
    JP: "flow", JR: "flow", CALL: "flow", RET: "flow", RETI: "flow", RST: "flow",
    // Load / store
    LD: "load", LDH: "load", LDI: "load", LDD: "load", PUSH: "load", POP: "load",
    // Arithmetic
    ADD: "arith", ADC: "arith", SUB: "arith", SBC: "arith",
    INC: "arith", DEC: "arith", DAA: "arith", CPL: "arith", SCF: "arith", CCF: "arith",
    // Logic / comparison
    AND: "logic", OR: "logic", XOR: "logic", CP: "logic",
    BIT: "logic", SET: "logic", RES: "logic",
    // Shift / rotate
    RL: "shift", RLC: "shift", RR: "shift", RRC: "shift",
    RLA: "shift", RLCA: "shift", RRA: "shift", RRCA: "shift",
    SLA: "shift", SRA: "shift", SRL: "shift", SWAP: "shift",
    // System / misc
    NOP: "sys", HALT: "sys", STOP: "sys", DI: "sys", EI: "sys", CB: "sys",
  };

  function classifyMnemonic(mnemonic) {
    return MNEMONIC_CLASSES[mnemonic.toUpperCase()] || "";
  }

  function updateDisassembly(text, pc) {
    const lines = text.split("\n").filter(l => l.trim());
    let html = "";
    let lineIdx = 0;
    for (const line of lines) {
      const match = line.match(/^\s*([0-9A-Fa-f]{1,4}):\s+(.+)/);
      if (match) {
        const addr = match[1].toUpperCase().padStart(4, "0");
        const rest = match[2];
        const parts = rest.split(/\s+/);
        const mnemonic = parts[0] || "";
        const operands = parts.slice(1).join(" ");
        const addrNum = parseInt(addr, 16);
        const isCurrent = pc !== undefined && addrNum === pc;
        const typeClass = classifyMnemonic(mnemonic);
        const zebra = lineIdx % 2 === 1 ? " zebra" : "";

        html += `<div class="disasm-line${isCurrent ? " current" : ""}${zebra}">
          <span class="disasm-addr">${addr}</span>
          <span class="disasm-mnemonic${typeClass ? ` m-${typeClass}` : ""}">${esc(mnemonic)}</span>
          <span class="disasm-operands">${esc(operands)}</span>
        </div>`;
        lineIdx++;
      } else {
        html += `<div class="disasm-line"><span class="disasm-operands">${esc(line)}</span></div>`;
      }
    }
    disasmEl.innerHTML = html;

    // Update instruction count badge
    const countEl = document.getElementById("disasm-count");
    if (countEl) countEl.textContent = `${lineIdx}`;
  }

  function updateEmulatorStatus(status, activity, currentState) {
    let displayState = status.state || "\u2014";
    if (displayState === "PAUSED" && activity) {
      displayState = activity === "active" ? "Active" : "Idle";
    }

    const items = [
      ["State", displayState],
      ["ROM", status.rom_title || "\u2014"],
      ["Frame", frameCount.toLocaleString()],
    ];
    if (currentState) {
      if (currentState.name) items.push(["Save", currentState.name]);
      if (currentState.state_id) items.push(["State ID", currentState.state_id]);
    }
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
    if (data.money != null) items.push(["Money", `\u00A5${data.money.toLocaleString()}`]);

    updateStateGrid("game-status", items);
  }

  function updateLlmStatus(data) {
    const items = [];
    if (data.llm_model) items.push(["Model", data.llm_model]);
    if (data.llm_provider) items.push(["Provider", data.llm_provider]);
    if (data.llm_cost) items.push(["Cost", data.llm_cost]);
    if (data.llm_tokens) items.push(["Tokens", data.llm_tokens.toLocaleString()]);
    if (data.llm_steps) items.push(["Steps", data.llm_steps]);
    if (items.length > 0) updateStateGrid("llm-status", items);
  }

  function updateStateGrid(sectionId, items) {
    let section = document.getElementById(sectionId);
    if (!section) {
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
    const result = data.result != null ? String(data.result) : "";

    const el = document.createElement("div");
    el.className = "llm-msg role-tool";
    el.innerHTML = `<span class="msg-role">tool</span><strong>${esc(name)}</strong>()`;
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

  const registeredPanels = {};

  function handlePanelRegistry(data) {
    const panels = data.panels || [];
    const container = document.getElementById("plugin-panels");
    if (!container) return;

    container.innerHTML = "";
    for (const panel of panels) {
      registeredPanels[panel.id] = panel;

      // Route screen_text panels to the dedicated slot
      if (panel.type === "screen_text" && screenTextSlot) {
        screenTextSlot.style.display = "";
        const header = screenTextSlot.querySelector(".panel-header");
        if (header) {
          header.innerHTML = `<span class="indicator active"></span>${esc(panel.title || "Screen Text")}`;
        }
        registeredPanels[panel.id]._slotEl = screenTextSlot;
        continue;
      }

      const el = document.createElement("div");
      el.id = `panel-${panel.id}`;
      el.className = `panel panel-${panel.type || "generic"}`;
      el.innerHTML = `
        <div class="panel-header">
          <span class="indicator active"></span>
          ${esc(panel.title || panel.id)}
        </div>
        <div class="panel-body">Waiting for data\u2026</div>`;
      container.appendChild(el);
    }
  }

  function updatePanel(data) {
    const id = data.panel_id;
    const panelType = data.type || "";
    const content = data.content || {};

    // Check for slot-routed panels first
    const panelInfo = registeredPanels[id];
    const el = (panelInfo && panelInfo._slotEl) || document.getElementById(`panel-${id}`);
    if (!el) return;

    const body = el.querySelector(".panel-body");
    if (!body) return;

    switch (panelType) {
      case "ascii_map":
        renderAsciiMap(body, content);
        break;
      case "screen_text":
        renderScreenText(body, content);
        break;
      default:
        body.textContent = typeof content === "string" ? content : JSON.stringify(content).slice(0, 300);
    }
  }

  // ASCII map character → CSS class
  const MAP_CHAR_CLASSES = {
    "@": "mc-player",
    "W": "mc-warp",
    "T": "mc-trainer",
    "I": "mc-item",
    "N": "mc-npc",
    "G": "mc-grass",
    "C": "mc-pc",
    "B": "mc-book",
    "!": "mc-sign",
    "#": "mc-wall",
    ".": "mc-walk",
    "v": "mc-ledge",
    "<": "mc-ledge",
    ">": "mc-ledge",
    "H": "mc-item",
  };

  function renderAsciiMap(body, data) {
    const ascii = data.ascii || "";
    const lines = ascii.split("\n");
    let html = "";
    for (const line of lines) {
      if (line.match(/^\s+\d/) && !line.match(/^\s*\d+:/)) {
        html += `<div class="map-row"><span class="mc-header">${esc(line)}</span></div>`;
        continue;
      }
      const match = line.match(/^(\s*\d+:)(.*)/);
      if (match) {
        const label = match[1];
        const chars = match[2];
        let row = `<span class="mc-header">${esc(label)}</span>`;
        for (const ch of chars) {
          const cls = MAP_CHAR_CLASSES[ch];
          if (cls) {
            row += `<span class="${cls}">${esc(ch)}</span>`;
          } else {
            row += esc(ch);
          }
        }
        html += `<div class="map-row">${row}</div>`;
      } else {
        html += `<div class="map-row">${esc(line)}</div>`;
      }
    }
    const mapName = data.map_name || "";
    const player = data.player || {};
    const meta = mapName ? `${esc(mapName)} (${player.x ?? "?"},${player.y ?? "?"})` : "";
    if (meta) {
      html = `<div style="margin-bottom:4px;color:var(--green);font-weight:600;font-size:10px">${meta}</div>${html}`;
    }
    body.innerHTML = html;
  }

  function renderScreenText(body, data) {
    const textLines = data.text_lines || [];
    const key = data.key;

    let html = "";
    if (key) {
      html += `<div class="screen-text-key">Pressed: <span class="key-name">${esc(key)}</span></div>`;
    }
    if (textLines.length === 0) {
      html += `<div class="screen-text-line empty">(no text on screen)</div>`;
    } else {
      for (const line of textLines) {
        const hasText = line.trim().length > 0;
        html += `<div class="screen-text-line ${hasText ? "has-text" : "empty"}">${esc(line || "\u00A0")}</div>`;
      }
    }
    body.innerHTML = html;
  }

  // ── Agent action buttons ────────────────────────

  function wireActionBarButtons() {
    const container = document.getElementById("action-bar-content");
    if (!container) return;
    container.querySelectorAll("[data-action-id]").forEach((btn) => {
      if (btn._wired) return; // avoid double-binding
      btn._wired = true;
      btn.addEventListener("mousedown", () => {
        const id = btn.dataset.actionId;
        send({ type: "agent_action", action_id: id });
        addLlmMessage({ role: "agent", content: `[action] ${id}` });
        btn.classList.add("pressed");
        setTimeout(() => btn.classList.remove("pressed"), 200);
      });
    });
  }

  // Wire up default buttons from HTML on page load
  wireActionBarButtons();

  function updateAgentActions(actions) {
    const bar = document.getElementById("action-bar");
    const container = document.getElementById("action-bar-content");
    if (!bar || !container) return;

    const groups = {};
    for (const action of actions) {
      const group = action.group || "default";
      if (!groups[group]) groups[group] = [];
      groups[group].push(action);
    }

    let html = "";
    let first = true;
    for (const [groupName, groupActions] of Object.entries(groups)) {
      if (!first) html += `<span class="action-group-sep"></span>`;
      first = false;
      for (const action of groupActions) {
        const cls = groupName === "control" ? "btn-action-bar control" : "btn-action-bar";
        html += `<button class="${cls}" data-action-id="${esc(action.id)}" title="${esc(groupName)}">${esc(action.label)}</button>`;
      }
    }
    container.innerHTML = html;
    bar.style.display = "";
    wireActionBarButtons();
  }

  // ── Prompt injection ────────────────────────────

  function sendPrompt() {
    const text = promptInput.value.trim();
    if (!text) return;
    send({ type: "inject_prompt", text });

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
