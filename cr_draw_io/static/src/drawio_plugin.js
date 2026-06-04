/** @odoo-module **/

import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { DrawioDialog } from "./drawio_dialog";
import { parseHTML } from "@html_editor/utils/html";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";

/**
 * DrawioPlugin
 *
 * HOW IT WORKS:
 *  1. Adds a "/drawio" slash command to every Odoo HTML editor field.
 *  2. Inserts the diagram as a PNG <img> (Odoo auto-uploads it as an attachment).
 *  3. Stores the Draw.io XML in data-drawio-xml on the wrapper <div>.
 *     The Python __init__.py patches Odoo's HTML sanitizer to preserve
 *     this attribute when the record is saved.
 *  4. On click, reads data-drawio-xml and reopens Draw.io pre-loaded.
 */
export class DrawioPlugin extends Plugin {
    static id = "drawio";
    static dependencies = ["dialog", "dom", "history", "selection"];

    resources = {
        user_commands: [
            {
                id: "insertDrawio",
                title: _t("Draw.io Diagram"),
                description: _t("Insert a Draw.io diagram"),
                icon: "fa-pencil-square-o",
                run: () => this.openDrawio(),
            },
        ],
        powerbox_items: [
            {
                categoryId: "widget",
                commandId: "insertDrawio",
            },
        ],
    };

    setup() {
        this.addDomListener(this.editable, "click", this.onEditorClick.bind(this));
    }

    openDrawio(existingElement = null) {
        // Read the stored XML from the data attribute (raw, not encoded)
        const existingXml = existingElement
            ? (existingElement.getAttribute("data-drawio-xml") || "")
            : "";

        this.dependencies.dialog.addDialog(DrawioDialog, {
            xml: existingXml,
            onSave: (data) => {
                if (existingElement) {
                    this.updateDiagram(existingElement, data.xml, data.png);
                } else {
                    this.insertDiagram(data.xml, data.png);
                }
            },
            onClose: () => {
                this.dependencies.selection.focusEditable();
            },
        });
    }

    insertDiagram(xml, pngDataUrl) {
        const fragment = parseHTML(this.document, this.buildDiagramHtml(xml, pngDataUrl));
        this.dependencies.dom.insert(fragment);
        this.dependencies.history.addStep();
    }

    updateDiagram(element, xml, pngDataUrl) {
        const fragment = parseHTML(this.document, this.buildDiagramHtml(xml, pngDataUrl));
        const newNode = fragment.firstElementChild;
        if (newNode) {
            element.replaceWith(newNode);
        }
        this.dependencies.history.addStep();
    }

    /**
     * Builds the diagram HTML.
     *
     * KEY POINTS:
     *  - data-drawio-xml: stores raw Draw.io XML for re-editing.
     *    Preserved by the safe_attrs patch in __init__.py.
     *  - o_b64_image_to_save: Odoo will auto-upload this PNG to the server
     *    and replace the data: URI with a /web/image/ URL on save.
     *  - contenteditable="false": prevents cursor entering the diagram.
     */
    buildDiagramHtml(xml, pngDataUrl) {
        return `
            <div class="o_drawio_diagram"
                 data-drawio-xml="${this.escapeAttr(xml)}"
                 contenteditable="false">
                <img class="o_b64_image_to_save"
                     src="${pngDataUrl}"
                     alt="Draw.io Diagram"
                     style="max-width:100%; display:block;" />
            </div>
        `.trim();
    }

    onEditorClick(ev) {
        const diagram = ev.target.closest(".o_drawio_diagram");
        if (diagram) {
            ev.preventDefault();
            ev.stopPropagation();
            this.openDrawio(diagram);
        }
    }

    // Escapes XML so it can be safely placed inside an HTML attribute value
    escapeAttr(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }
}

MAIN_PLUGINS.push(DrawioPlugin);
