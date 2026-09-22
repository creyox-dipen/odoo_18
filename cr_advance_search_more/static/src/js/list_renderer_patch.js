/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { onMounted, onPatched, onWillDestroy } from "@odoo/owl";

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
                        ".o_list_search_row, .o_list_record_selector, input, textarea, select, button, i.fa, script, style, mark.o_search_keyword_highlight"
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

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.activeSelectionDropdown = null;
        this.debounceTimers = {};

        this.onWindowClickCloseSelection = (ev) => {
            if (this.activeSelectionDropdown && !ev.target.closest(".o_column_search_dropdown_wrapper")) {
                this.activeSelectionDropdown = null;
                this.renderSearchRow();
            }
        };
        window.addEventListener("click", this.onWindowClickCloseSelection);
        onWillDestroy(() => {
            window.removeEventListener("click", this.onWindowClickCloseSelection);
        });

        onMounted(() => {
            this.renderSearchRow();
            this.applyKeywordHighlighting();
        });

        onPatched(() => {
            this.renderSearchRow();
            this.applyKeywordHighlighting();
        });
    },

    applyKeywordHighlighting() {
        const table = this.tableEl;
        if (!table) return;
        const tbody = table.querySelector("tbody");
        if (!tbody) return;

        const keywords = this.env.searchModel?.getActiveSearchKeywords?.() || [];
        if (!keywords || keywords.length === 0) return;

        highlightKeywordsInContainer(tbody, keywords);
    },

    get tableEl() {
        if (this.tableRef?.el) return this.tableRef.el;
        if (this.rootRef?.el) return this.rootRef.el.querySelector("table.o_list_table");
        return document.querySelector(".o_list_renderer table.o_list_table");
    },

    getFieldDef(fieldName) {
        if (!fieldName) return null;
        return (
            this.props?.fields?.[fieldName] ||
            this.fields?.[fieldName] ||
            this.props?.list?.fields?.[fieldName] ||
            this.props?.list?.model?.fields?.[fieldName] ||
            this.env?.searchModel?.resModelFields?.[fieldName] ||
            null
        );
    },

    isSearchableColumn(column) {
        if (!column || !column.name || column.type !== "field") return false;
        if (column.name === "id") return false;

        const nonSearchableWidgets = [
            "handle",
            "activity",
            "activity_exception",
            "activity_state",
            "web_ribbon",
            "statinfo",
            "widget",
        ];
        if (column.widget && nonSearchableWidgets.includes(column.widget)) {
            return false;
        }

        const field = this.getFieldDef(column.name);
        if (field && field.searchable === false) {
            return false;
        }

        const colType = this.getColumnType(column);
        const nonSearchableTypes = ["binary", "properties", "json", "html"];
        if (nonSearchableTypes.includes(colType)) {
            return false;
        }

        return true;
    },

    getColumnType(column) {
        const field = this.getFieldDef(column.name);
        if (field && field.type) {
            return field.type;
        }
        return column.fieldType || "char";
    },

    renderSearchRow() {
        const table = this.tableEl;
        if (!table) return;
        const thead = table.querySelector("thead");
        if (!thead) return;

        const isX2Many =
            this.props?.isX2Many ||
            this.props?.archInfo?.isX2Many ||
            !this.env?.searchModel ||
            Boolean(table.closest(".o_field_x2many, .o_field_widget, .o_form_view"));

        if (isX2Many) {
            const existingRow = thead.querySelector(".o_list_search_row");
            if (existingRow) {
                existingRow.remove();
            }
            return;
        }

        let searchRow = thead.querySelector(".o_list_search_row");
        if (!searchRow) {
            searchRow = document.createElement("tr");
            searchRow.className = "o_list_search_row";
            thead.appendChild(searchRow);
        }

        // Capture active focus state before DOM update
        let focusedInfo = null;
        const activeEl = document.activeElement;
        if (activeEl && searchRow.contains(activeEl) && activeEl.tagName === "INPUT") {
            focusedInfo = {
                fieldName: activeEl.getAttribute("data-field"),
                dateType: activeEl.getAttribute("data-type"),
                selectionStart: activeEl.selectionStart,
                selectionEnd: activeEl.selectionEnd,
            };
        } else if (this.lastFocusedInputInfo) {
            focusedInfo = this.lastFocusedInputInfo;
        }

        const hasActiveColumnFilters = Boolean(
            this.env.searchModel?.columnFilters &&
            Object.keys(this.env.searchModel.columnFilters).length > 0
        );

        const columns = Array.isArray(this.columns) ? this.columns : (this.state?.columns || []);
        if (!columns || columns.length === 0) return;

        let html = "";
        if (this.hasSelectors) {
            html += `
                <th class="o_list_record_selector o_list_search_cell text-center">
                    ${
                        hasActiveColumnFilters
                            ? `<button class="o_clear_all_column_filters_btn" title="Clear all column search fields">
                                   <i class="fa fa-times-circle"></i>
                               </button>`
                            : ""
                    }
                </th>
            `;
        }

        for (const column of columns) {
            const isNumeric = ["integer", "float", "monetary"].includes(this.getColumnType(column));
            const alignClass = isNumeric ? "text-end" : "";

            if (column.type === "field" && this.isSearchableColumn(column)) {
                const colType = this.getColumnType(column);
                const colName = column.name;
                const colLabel = column.label || column.string || colName;

                if (colType === "selection" || colType === "boolean") {
                    const selLabel = this.getColumnSelectionLabel(column);
                    const isOpen = this.activeSelectionDropdown === colName;
                    const options = this.getSelectionOptions(column);

                    let optionsHtml = "";
                    for (const opt of options) {
                        const isChecked = this.isOptionSelected(colName, opt[0]);
                        optionsHtml += `
                            <label class="o_selection_option_item" data-field="${colName}" data-val="${opt[0]}">
                                <input type="checkbox" ${isChecked ? "checked" : ""}/>
                                <span class="ms-2">${opt[1]}</span>
                            </label>
                        `;
                    }

                    html += `
                        <th class="o_list_search_cell ${alignClass}">
                            <div class="o_column_search_dropdown_wrapper">
                                <button class="o_column_search_btn" data-field="${colName}" title="Filter ${colLabel}">
                                    <i class="fa fa-filter me-1"></i>
                                    <span class="o_column_btn_text">${selLabel}</span>
                                    <i class="fa fa-caret-down ms-1"></i>
                                </button>
                                ${isOpen ? `<div class="o_column_selection_popup">${optionsHtml}</div>` : ""}
                            </div>
                        </th>
                    `;
                } else if (colType === "date" || colType === "datetime") {
                    const startDate = this.getColumnDateStart(colName);
                    const endDate = this.getColumnDateEnd(colName);

                    html += `
                        <th class="o_list_search_cell ${alignClass}">
                            <div class="o_column_date_range_wrapper">
                                <input type="date" class="o_column_search_input o_column_date_input" data-field="${colName}" data-type="start" value="${startDate}" title="Start Date"/>
                                <span class="o_date_separator">➔</span>
                                <input type="date" class="o_column_search_input o_column_date_input" data-field="${colName}" data-type="end" value="${endDate}" title="End Date"/>
                            </div>
                        </th>
                    `;
                } else {
                    const val = this.getColumnSearchValue(colName);
                    html += `
                        <th class="o_list_search_cell ${alignClass}">
                            <div class="o_column_search_input_wrapper">
                                <input type="text" class="o_column_search_input" data-field="${colName}" placeholder="${colLabel}..." value="${val}"/>
                                <i class="fa fa-search o_column_search_icon"></i>
                            </div>
                        </th>
                    `;
                }
            } else {
                html += `<th class="o_list_search_cell ${alignClass}"></th>`;
            }
        }

        if (this.hasOpenFormViewColumn) {
            html += `<th class="o_list_search_cell"></th>`;
        }
        if (this.hasActionsColumn) {
            html += `<th class="o_list_search_cell"></th>`;
        }

        searchRow.innerHTML = html;
        this.attachSearchRowEvents(searchRow);

        // Restore focus to active input after DOM replacement
        if (focusedInfo && focusedInfo.fieldName) {
            const restoreFocus = () => {
                let targetInput = null;
                if (focusedInfo.dateType) {
                    targetInput = searchRow.querySelector(
                        `input[data-field="${focusedInfo.fieldName}"][data-type="${focusedInfo.dateType}"]`
                    );
                } else {
                    targetInput = searchRow.querySelector(
                        `input[data-field="${focusedInfo.fieldName}"]`
                    );
                }

                if (targetInput) {
                    targetInput.focus();
                    if (
                        typeof focusedInfo.selectionStart === "number" &&
                        typeof focusedInfo.selectionEnd === "number" &&
                        targetInput.setSelectionRange &&
                        targetInput.type !== "date"
                    ) {
                        try {
                            targetInput.setSelectionRange(
                                focusedInfo.selectionStart,
                                focusedInfo.selectionEnd
                            );
                        } catch (e) {
                            // ignore setSelectionRange error on unsupported input types
                        }
                    }
                }
            };

            restoreFocus();
            requestAnimationFrame(() => {
                restoreFocus();
            });
        }
    },

    attachSearchRowEvents(searchRow) {
        const updateFocusState = (input) => {
            if (input && input.tagName === "INPUT") {
                this.lastFocusedInputInfo = {
                    fieldName: input.getAttribute("data-field"),
                    dateType: input.getAttribute("data-type"),
                    selectionStart: input.selectionStart,
                    selectionEnd: input.selectionEnd,
                };
            }
        };

        const allInputs = searchRow.querySelectorAll("input");
        allInputs.forEach((input) => {
            input.addEventListener("focus", () => updateFocusState(input));
            input.addEventListener("keyup", () => updateFocusState(input));
            input.addEventListener("click", () => updateFocusState(input));
            input.addEventListener("blur", () => {
                setTimeout(() => {
                    if (!document.activeElement || !searchRow.contains(document.activeElement)) {
                        this.lastFocusedInputInfo = null;
                    }
                }, 50);
            });
        });

        // Clear All Column Filters Button
        const clearBtn = searchRow.querySelector(".o_clear_all_column_filters_btn");
        if (clearBtn) {
            clearBtn.addEventListener("click", (ev) => {
                ev.stopPropagation();
                ev.preventDefault();
                this.lastFocusedInputInfo = null;
                if (this.env.searchModel) {
                    this.env.searchModel.clearColumnFilters();
                }
            });
        }

        // Text Inputs
        const textInputs = searchRow.querySelectorAll(".o_column_search_input_wrapper input");
        textInputs.forEach((input) => {
            input.addEventListener("input", (ev) => {
                const fieldName = input.getAttribute("data-field");
                const val = ev.target.value;
                if (this.debounceTimers[fieldName]) clearTimeout(this.debounceTimers[fieldName]);
                this.debounceTimers[fieldName] = setTimeout(() => {
                    if (this.env.searchModel) {
                        this.env.searchModel.setColumnFilter(fieldName, val);
                    }
                }, 300);
            });
            input.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") {
                    ev.preventDefault();
                    const fieldName = input.getAttribute("data-field");
                    if (this.debounceTimers[fieldName]) clearTimeout(this.debounceTimers[fieldName]);
                    if (this.env.searchModel) {
                        this.env.searchModel.setColumnFilter(fieldName, ev.target.value);
                    }
                }
            });
        });

        // Date Inputs
        const dateInputs = searchRow.querySelectorAll(".o_column_date_range_wrapper input");
        dateInputs.forEach((input) => {
            input.addEventListener("change", (ev) => {
                const fieldName = input.getAttribute("data-field");
                const dateType = input.getAttribute("data-type");
                const dateVal = ev.target.value;

                const filter = Object.assign({}, this.env.searchModel?.columnFilters?.[fieldName]);
                if (dateType === "start") {
                    if (dateVal) filter.start = `${dateVal} 00:00:00`;
                    else delete filter.start;
                } else if (dateType === "end") {
                    if (dateVal) filter.end = `${dateVal} 23:59:59`;
                    else delete filter.end;
                }

                if (!filter.start && !filter.end) {
                    this.env.searchModel?.setColumnFilter(fieldName, null);
                } else {
                    this.env.searchModel?.setColumnFilter(fieldName, filter);
                }
            });
        });

        // Selection Dropdown Buttons
        const selBtns = searchRow.querySelectorAll(".o_column_search_btn");
        selBtns.forEach((btn) => {
            btn.addEventListener("click", (ev) => {
                ev.stopPropagation();
                const fieldName = btn.getAttribute("data-field");
                if (this.activeSelectionDropdown === fieldName) {
                    this.activeSelectionDropdown = null;
                } else {
                    this.activeSelectionDropdown = fieldName;
                }
                this.renderSearchRow();
            });
        });

        // Selection Checkboxes
        const selItems = searchRow.querySelectorAll(".o_selection_option_item");
        selItems.forEach((item) => {
            item.addEventListener("click", (ev) => {
                ev.stopPropagation();
                const checkbox = item.querySelector("input[type='checkbox']");
                if (checkbox && ev.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                }
                const fieldName = item.getAttribute("data-field");
                const optionVal = item.getAttribute("data-val");
                this.toggleSelectionOption(fieldName, optionVal);
            });
        });
    },

    getColumnSearchValue(fieldName) {
        const filter = this.env.searchModel?.columnFilters?.[fieldName];
        return typeof filter === "string" ? filter : "";
    },

    getColumnDateStart(fieldName) {
        const filter = this.env.searchModel?.columnFilters?.[fieldName];
        return filter?.start ? filter.start.split(" ")[0] : "";
    },

    getColumnDateEnd(fieldName) {
        const filter = this.env.searchModel?.columnFilters?.[fieldName];
        return filter?.end ? filter.end.split(" ")[0] : "";
    },

    getSelectionOptions(column) {
        const colType = this.getColumnType(column);
        if (colType === "boolean") {
            return [
                ["true", "Yes"],
                ["false", "No"],
            ];
        }
        const field = this.getFieldDef(column.name);
        return field?.selection || column.selection || [];
    },

    getColumnSelectionLabel(column) {
        const filter = this.env.searchModel?.columnFilters?.[column.name];
        if (Array.isArray(filter) && filter.length > 0) {
            const options = this.getSelectionOptions(column);
            if (filter.length === 1) {
                const match = options.find((opt) => opt[0] === filter[0]);
                return match ? match[1] : filter[0];
            }
            return `${filter.length} selected`;
        }
        return column.label || column.string || "Filter";
    },

    isOptionSelected(fieldName, optionValue) {
        const filter = this.env.searchModel?.columnFilters?.[fieldName];
        return Array.isArray(filter) && filter.includes(optionValue);
    },

    toggleSelectionOption(fieldName, optionValue) {
        const currentFilter = this.env.searchModel?.columnFilters?.[fieldName] || [];
        let updated = Array.isArray(currentFilter) ? [...currentFilter] : [];
        if (updated.includes(optionValue)) {
            updated = updated.filter((v) => v !== optionValue);
        } else {
            updated.push(optionValue);
        }
        if (this.env.searchModel) {
            this.env.searchModel.setColumnFilter(fieldName, updated);
        }
        this.renderSearchRow();
    },

    onColumnSearchInput(fieldName, value) {
        if (this.debounceTimers[fieldName]) {
            clearTimeout(this.debounceTimers[fieldName]);
        }
        this.debounceTimers[fieldName] = setTimeout(() => {
            if (this.env.searchModel) {
                this.env.searchModel.setColumnFilter(fieldName, value);
            }
        }, 300);
    },

    onColumnSearchKeydown(ev, fieldName) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            if (this.debounceTimers[fieldName]) {
                clearTimeout(this.debounceTimers[fieldName]);
            }
            if (this.env.searchModel) {
                this.env.searchModel.setColumnFilter(fieldName, ev.target.value);
            }
        }
    },

    onColumnDateStartChange(fieldName, startDate) {
        const filter = Object.assign({}, this.env.searchModel?.columnFilters?.[fieldName]);
        if (startDate) {
            filter.start = `${startDate} 00:00:00`;
        } else {
            delete filter.start;
        }
        if (!filter.start && !filter.end) {
            this.env.searchModel?.setColumnFilter(fieldName, null);
        } else {
            this.env.searchModel?.setColumnFilter(fieldName, filter);
        }
    },

    onColumnDateEndChange(fieldName, endDate) {
        const filter = Object.assign({}, this.env.searchModel?.columnFilters?.[fieldName]);
        if (endDate) {
            filter.end = `${endDate} 23:59:59`;
        } else {
            delete filter.end;
        }
        if (!filter.start && !filter.end) {
            this.env.searchModel?.setColumnFilter(fieldName, null);
        } else {
            this.env.searchModel?.setColumnFilter(fieldName, filter);
        }
    },
});
