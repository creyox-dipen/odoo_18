/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { onMounted, onPatched } from "@odoo/owl";

function highlightKeywordsInContainer(containerEl, keywords) {
    if (!containerEl || !Array.isArray(keywords) || keywords.length === 0) return;

    const cleanKeywords = keywords
        .map((k) => String(k).trim())
        .filter((k) => k.length >= 1 && !["|", "&", "!", "(", ")"].includes(k));

    if (cleanKeywords.length === 0) return;

    const escaped = cleanKeywords.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const regex = new RegExp(`(${escaped.join("|")})`, "gi");

    const walker = document.createTreeWalker(
        containerEl,
        NodeFilter.SHOW_TEXT,
        {
            acceptNode(node) {
                if (!node || !node.nodeValue || !node.nodeValue.trim()) {
                    return NodeFilter.FILTER_REJECT;
                }
                const parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;

                if (
                    parent.closest(
                        "input, textarea, select, button, i.fa, script, style, mark.o_search_keyword_highlight, .o_dropdown_menu"
                    )
                ) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            },
        },
        false
    );

    const nodesToReplace = [];
    let currentNode;
    while ((currentNode = walker.nextNode())) {
        if (regex.test(currentNode.nodeValue)) {
            nodesToReplace.push(currentNode);
        }
        regex.lastIndex = 0;
    }

    for (const node of nodesToReplace) {
        const text = node.nodeValue;
        const parent = node.parentNode;
        if (!parent) continue;

        const fragment = document.createDocumentFragment();
        let lastIndex = 0;
        regex.lastIndex = 0;

        let match;
        while ((match = regex.exec(text)) !== null) {
            const matchIndex = match.index;
            const matchText = match[0];

            if (matchIndex > lastIndex) {
                fragment.appendChild(document.createTextNode(text.substring(lastIndex, matchIndex)));
            }

            const mark = document.createElement("mark");
            mark.className = "o_search_keyword_highlight";
            mark.textContent = matchText;
            fragment.appendChild(mark);

            lastIndex = matchIndex + matchText.length;
        }

        if (lastIndex < text.length) {
            fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
        }

        parent.replaceChild(fragment, node);
    }
}

patch(KanbanRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => {
            this.applyKanbanKeywordHighlighting();
        });

        onPatched(() => {
            this.applyKanbanKeywordHighlighting();
        });
    },

    applyKanbanKeywordHighlighting() {
        const root = this.rootRef?.el || document.querySelector(".o_kanban_renderer");
        if (!root) return;

        const keywords = this.env.searchModel?.getActiveSearchKeywords?.() || [];
        if (!keywords || keywords.length === 0) return;

        highlightKeywordsInContainer(root, keywords);
    },
});
