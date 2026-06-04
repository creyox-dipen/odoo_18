/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * DrawioDialog
 * ─────────────────────────────────────────────────────────────────────────────
 * Wraps the Draw.io iframe inside an Odoo Dialog.
 *
 * The communication flow is:
 *   1. iframe loads → Draw.io fires  "init"    → we send "load" with XML
 *   2. User edits diagram
 *   3. User clicks Save (💾 icon) → Draw.io fires "save" with the XML
 *   4. We request a PNG export   → send "export" with format "png"
 *   5. Draw.io fires  "export"   → we call onSave({ xml, png }) & close
 *
 * WHY PNG and not SVG?
 *   Odoo's Python server-side sanitizer strips <svg> elements when saving.
 *   PNG is a standard image format that the sanitizer preserves,
 *   and Odoo can upload it as an attachment so it gets a real server URL.
 * ─────────────────────────────────────────────────────────────────────────────
 */
export class DrawioDialog extends Component {
    static components = { Dialog };
    static template = "cr_draw_io.DrawioDialog";
    static props = {
        onSave: Function,                       // (data) => void — called with {xml, png}
        onClose: Function,                      // () => void — called on cancel
        xml: { type: String, optional: true },  // existing diagram XML for re-editing
        close: Function,                        // injected by Odoo dialog service
    };

    setup() {
        this.iframeRef = useRef("iframe");

        // We store the XML received in the "save" event as a fallback,
        // in case the "export" response doesn't include it.
        this._savedXml = "";

        this.onMessage = (event) => {
            // ── Security: only trust diagrams.net ─────────────────────────
            if (
                !event.origin.includes("diagrams.net") &&
                !event.origin.includes("drawio.com")
            ) {
                return;
            }

            // ── Parse the JSON message ─────────────────────────────────────
            let data;
            try {
                data = JSON.parse(event.data);
            } catch {
                return;
            }

            // ── STEP 1: Draw.io is ready — send our content ────────────────
            if (data.event === "init") {
                // Wait 100ms then send the load command.
                // This gives Draw.io a moment to finish its internal listeners.
                setTimeout(() => {
                    this._sendToDrawio({
                        action: "load",
                        xml: this.props.xml || "",
                        autosave: 0,
                    });
                }, 100);
            }

            // ── STEP 2: User clicked Save — request a PNG export ───────────
            // We need a PNG because:
            //   • Odoo's Python sanitizer strips <svg> elements on save
            //   • PNG as a <img> tag survives sanitization
            //   • Odoo can auto-upload the base64 PNG as a server attachment
            if (data.event === "save") {
                this._savedXml = data.xml || "";  // save XML for fallback

                // Ask Draw.io to render the diagram as a PNG image.
                // It will fire an "export" event with the image data.
                this._sendToDrawio({
                    action: "export",
                    format: "png",  // PNG survives Odoo's HTML sanitizer
                });
            }

            // ── STEP 3: PNG is ready — pass to plugin and close ───────────
            if (data.event === "export") {
                const xml = data.xml || this._savedXml;
                const png = data.data;  // "data:image/png;base64,..."

                if (png && xml) {
                    // Pass both the image (for display) and XML (for future re-editing)
                    this.props.onSave({ xml, png });
                }
                this.props.close();
            }

            // ── Exit button clicked (cancel) ───────────────────────────────
            if (data.event === "exit") {
                this.props.onClose();
                this.props.close();
            }
        };

        onMounted(() => window.addEventListener("message", this.onMessage));
        onWillUnmount(() => window.removeEventListener("message", this.onMessage));
    }

    _sendToDrawio(message) {
        const iframe = this.iframeRef.el;
        if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage(JSON.stringify(message), "*");
        }
    }
}
