/** @odoo-module **/

console.log("[Channable] JS loaded");

document.addEventListener("click", function crChannableDarkModeToggle(ev) {
    const toggle = ev.target.closest(".my-dark-mode-toggle");
    console.log("[Channable] Click target:", ev.target, "has toggle:", !!toggle);
    if (!toggle) return;

    ev.stopPropagation();
    ev.preventDefault();

    const recordId = parseInt(toggle.dataset.recordId, 10);
    console.log("[Channable] Record ID:", recordId);
    if (!recordId) return;

    // Optimistically toggle classes for an instant, smooth CSS transition
    const wasActive = toggle.classList.contains("my-switch-active");
    toggle.classList.toggle("my-switch-active", !wasActive);

    const card = toggle.closest(".my-kanban-card");
    if (card) {
        card.classList.toggle("my-kanban-dark-mode", !wasActive);
    }

    // Call the Python backend in the background
    fetch("/web/dataset/call_kw", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            id: Math.floor(Math.random() * 1e9),
            params: {
                model: "channable.marketplace",
                method: "action_toggle_dark_mode",
                args: [[recordId]],
                kwargs: { context: {} },
            },
        }),
    }).then(response => response.json())
      .then(data => {
          console.log("[Channable] RPC response:", data);
          if (data.error) {
              // Revert styling on server error
              toggle.classList.toggle("my-switch-active", wasActive);
              if (card) card.classList.toggle("my-kanban-dark-mode", wasActive);
          }
      })
      .catch((err) => {
          console.error("[Channable] RPC error:", err);
          // Revert styling on network failure
          toggle.classList.toggle("my-switch-active", wasActive);
          if (card) card.classList.toggle("my-kanban-dark-mode", wasActive);
      });
}, true);
