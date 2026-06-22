console.log("[Channable] Sync progress polling JS loaded");

(function () {
    let syncPollInterval = null;

    function getActiveMarketplaceId() {
        // Check if the progress alert exists in the DOM.
        // If not, we are not on the Marketplace form view.
        if (!document.querySelector(".channable_progress_alert")) {
            return null;
        }

        // 1. Try parsing hash for id parameter (classic Odoo routing)
        const hash = window.location.hash || "";
        const idMatch = hash.match(/[#&]id=(\d+)/);
        if (idMatch) {
            return parseInt(idMatch[1], 10);
        }

        // 2. Try parsing pathname (clean URL routing, e.g. /odoo/channable.marketplace/3)
        const path = window.location.pathname || "";
        const parts = path.split("/").filter(Boolean);
        if (parts.length > 0) {
            const lastPart = parts[parts.length - 1];
            const id = parseInt(lastPart, 10);
            if (!isNaN(id)) {
                return id;
            }
        }
        return null;
    }

    function pollSyncProgress() {
        const recordId = getActiveMarketplaceId();
        if (!recordId) {
            stopPolling();
            return;
        }

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
                    method: "read",
                    args: [[recordId], ["sync_in_progress", "sync_processed_orders", "sync_total_orders", "sync_progress_percentage"]],
                    kwargs: { context: {} },
                },
            }),
        })
        .then(r => r.json())
        .then(data => {
            if (data.result && data.result.length > 0) {
                const res = data.result[0];
                
                const alertEl = document.querySelector(".channable_progress_alert");
                let wasVisible = false;
                if (alertEl) {
                    wasVisible = window.getComputedStyle(alertEl).display !== "none" && !alertEl.hasAttribute("invisible");
                }

                updateProgressDOM(res);
                
                // If sync finished, reload the view once to update all order listings & metrics
                if (!res.sync_in_progress) {
                    stopPolling();
                    if (wasVisible) {
                        console.log("[Channable] Sync finished, reloading page to update statistics");
                        setTimeout(() => {
                            window.location.reload();
                        }, 500);
                    }
                } else {
                    startPolling();
                }
            }
        })
        .catch(err => console.error("[Channable] Poll error:", err));
    }

    function updateProgressDOM(data) {
        const alertEl = document.querySelector(".channable_progress_alert");
        if (!alertEl) return;

        if (data.sync_in_progress) {
            alertEl.style.setProperty("display", "flex", "important");
            alertEl.removeAttribute("invisible");
            
            // Update processed orders
            const processedField = alertEl.querySelector("[name='sync_processed_orders']");
            if (processedField) {
                const span = processedField.querySelector("span") || processedField;
                span.textContent = data.sync_processed_orders;
            }
            
            // Update total orders
            const totalField = alertEl.querySelector("[name='sync_total_orders']");
            if (totalField) {
                const span = totalField.querySelector("span") || totalField;
                span.textContent = data.sync_total_orders;
            }
            
            // Update custom progress bar fill width
            const barFill = alertEl.querySelector(".channable-progress-bar-fill");
            if (barFill) {
                barFill.style.setProperty("width", data.sync_progress_percentage + "%", "important");
            }

            // Update percentage field value
            const percentageField = alertEl.querySelector("[name='sync_progress_percentage']");
            if (percentageField) {
                const span = percentageField.querySelector("span") || percentageField;
                span.textContent = data.sync_progress_percentage;
            }
        } else {
            alertEl.style.setProperty("display", "none", "important");
            alertEl.setAttribute("invisible", "1");
        }
    }

    function startPolling() {
        if (!syncPollInterval) {
            console.log("[Channable] Starting sync progress polling");
            syncPollInterval = setInterval(pollSyncProgress, 1500);
        }
    }

    function stopPolling() {
        if (syncPollInterval) {
            console.log("[Channable] Stopping sync progress polling");
            clearInterval(syncPollInterval);
            syncPollInterval = null;
        }
    }

    // Monitor view state every 1 second
    setInterval(() => {
        const alertEl = document.querySelector(".channable_progress_alert");
        const recordId = getActiveMarketplaceId();
        if (alertEl && recordId) {
            const isVisible = window.getComputedStyle(alertEl).display !== "none" && !alertEl.hasAttribute("invisible");
            if (isVisible) {
                startPolling();
            } else {
                stopPolling();
            }
        } else {
            stopPolling();
        }
    }, 1000);

    // One-off check on load to see if a background sync is already running
    setTimeout(() => {
        const alertEl = document.querySelector(".channable_progress_alert");
        const recordId = getActiveMarketplaceId();
        if (alertEl && recordId) {
            const isVisible = window.getComputedStyle(alertEl).display !== "none" && !alertEl.hasAttribute("invisible");
            if (!isVisible) {
                console.log("[Channable] Running one-off load check for background sync status");
                pollSyncProgress();
            }
        }
    }, 1000);
})();
