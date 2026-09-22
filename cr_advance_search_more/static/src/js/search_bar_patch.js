/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useState, onWillDestroy } from "@odoo/owl";

patch(SearchBar.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            showHistoryDropdown: false,
            showSavedFiltersDropdown: false,
            showSavedGroupByDropdown: false,
            historyVersion: 0,
            editingFilterId: null,
        });

        this.onOutsideClick = (ev) => {
            if (
                (this.state.showHistoryDropdown || this.state.showSavedFiltersDropdown || this.state.showSavedGroupByDropdown) &&
                !ev.target.closest(".o_advance_search_mode_wrapper")
            ) {
                this.state.showHistoryDropdown = false;
                this.state.showSavedFiltersDropdown = false;
                this.state.showSavedGroupByDropdown = false;
                this.state.editingFilterId = null;
            }
        };
        window.addEventListener("click", this.onOutsideClick);
        onWillDestroy(() => {
            window.removeEventListener("click", this.onOutsideClick);
        });
    },

    get resModel() {
        return this.env.searchModel?.resModel || "default";
    },

    get currentSearchMode() {
        if (this.env.searchModel) {
            return this.env.searchModel.searchMode || "default";
        }
        return window.sessionStorage.getItem("cr_advance_search_mode") || "default";
    },

    get recentSearchItems() {
        const _v = this.state.historyVersion;
        try {
            const raw = window.localStorage.getItem(`cr_recent_history_${this.resModel}`);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    },

    get savedFilterItems() {
        const _v = this.state.historyVersion;
        try {
            const raw = window.localStorage.getItem(`cr_saved_filters_${this.resModel}`);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    },

    get savedGroupByItems() {
        const _v = this.state.historyVersion;
        try {
            const raw = window.localStorage.getItem(`cr_saved_groupby_${this.resModel}`);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    },

    onSearchModeChange(ev) {
        const selectedMode = ev.target.value;
        window.sessionStorage.setItem("cr_advance_search_mode", selectedMode);
        if (this.env.searchModel) {
            this.env.searchModel.setSearchMode(selectedMode);
        }
    },

    toggleHistoryDropdown(ev) {
        ev.stopPropagation();
        this.state.showSavedFiltersDropdown = false;
        this.state.showSavedGroupByDropdown = false;
        this.state.showHistoryDropdown = !this.state.showHistoryDropdown;
    },

    toggleSavedFiltersDropdown(ev) {
        ev.stopPropagation();
        this.state.showHistoryDropdown = false;
        this.state.showSavedGroupByDropdown = false;
        this.state.showSavedFiltersDropdown = !this.state.showSavedFiltersDropdown;
    },

    toggleSavedGroupByDropdown(ev) {
        ev.stopPropagation();
        this.state.showHistoryDropdown = false;
        this.state.showSavedFiltersDropdown = false;
        this.state.showSavedGroupByDropdown = !this.state.showSavedGroupByDropdown;
    },

    saveSearchHistory(query, mode) {
        if (!query || !query.trim()) return;
        const cleanQuery = query.trim();
        const key = `cr_recent_history_${this.resModel}`;
        let items = this.recentSearchItems;
        items = items.filter((item) => item.query.toLowerCase() !== cleanQuery.toLowerCase());
        items.unshift({
            id: Date.now() + Math.random(),
            query: cleanQuery,
            mode: mode || this.currentSearchMode,
            timestamp: new Date().toISOString(),
        });
        if (items.length > 15) {
            items = items.slice(0, 15);
        }
        window.localStorage.setItem(key, JSON.stringify(items));
        this.state.historyVersion++;
    },

    selectItem(item) {
        if (item && !item.unselectable) {
            let queryVal = "";
            if (typeof item.value === "string" && item.value.trim()) {
                queryVal = item.value;
            } else if (typeof item.label === "string" && item.label.trim()) {
                queryVal = item.label;
            } else if (typeof this.state.query === "string" && this.state.query.trim()) {
                queryVal = this.state.query;
            }
            if (queryVal) {
                this.saveSearchHistory(queryVal, this.currentSearchMode);
            }
        }
        return super.selectItem(...arguments);
    },

    async onSelectHistoryItem(item) {
        this.state.showHistoryDropdown = false;
        if (this.env.searchModel) {
            this.env.searchModel.setSearchMode(item.mode);
            const searchInput = this.inputRef?.el || document.querySelector(".o_searchview_input");
            if (searchInput) {
                searchInput.value = item.query;
                searchInput.focus();
                searchInput.dispatchEvent(new Event("input", { bubbles: true }));
                await new Promise((resolve) => setTimeout(resolve, 50));
                if (this.items && this.items.length > 0) {
                    const validItem = this.items.find((i) => !i.unselectable && !i.isAddCustomFilterButton) || this.items[0];
                    if (validItem) {
                        this.selectItem(validItem);
                    }
                }
            }
        }
    },

    async onSelectSavedFilter(item) {
        this.state.showSavedFiltersDropdown = false;
        if (this.env.searchModel) {
            this.env.searchModel.setSearchMode(item.mode || "default");
            if (item.domain) {
                try {
                    const parsedDomain = typeof item.domain === "string" ? JSON.parse(item.domain) : item.domain;
                    if (parsedDomain && parsedDomain.length > 0) {
                        await this.env.searchModel.splitAndAddDomain(parsedDomain);
                    }
                } catch (e) {
                    this.env.searchModel.splitAndAddDomain(item.domain);
                }
            }
        }
    },

    async onSelectSavedGroupBy(item) {
        this.state.showSavedGroupByDropdown = false;
        if (this.env.searchModel && item.groupBy) {
            await this.env.searchModel.applyGroupBy(item.groupBy);
        }
    },

    onDeleteHistoryItem(ev, item) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        const key = `cr_recent_history_${this.resModel}`;
        let items = this.recentSearchItems;
        items = items.filter((i) => String(i.id) !== String(item.id));
        window.localStorage.setItem(key, JSON.stringify(items));
        this.state.historyVersion++;
    },

    onStartRenameFilter(ev, item) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.state.editingFilterId = item.id;
        setTimeout(() => {
            const inputEl = document.querySelector(`.o_saved_filter_dropdown .o_rename_filter_input`);
            if (inputEl) {
                inputEl.focus();
                inputEl.select();
            }
        }, 50);
    },

    onSaveRenameFilter(ev, item) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
        }
        if (this.state.editingFilterId !== item.id) return;

        const rowEl = ev?.target?.closest(".o_recent_search_item");
        const inputEl = rowEl ? rowEl.querySelector(".o_rename_filter_input") : document.querySelector(".o_saved_filter_dropdown .o_rename_filter_input");
        const newTitle = inputEl ? inputEl.value.trim() : "";

        if (newTitle && newTitle !== item.name) {
            const key = `cr_saved_filters_${this.resModel}`;
            let items = this.savedFilterItems;
            const targetIndex = items.findIndex((i) => String(i.id) === String(item.id));
            if (targetIndex >= 0) {
                items[targetIndex].name = newTitle;
                window.localStorage.setItem(key, JSON.stringify(items));
            }
        }
        this.state.editingFilterId = null;
        this.state.historyVersion++;
    },

    onKeydownRenameFilter(ev, item) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.onSaveRenameFilter(ev, item);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.state.editingFilterId = null;
        }
    },

    onDeleteSavedFilter(ev, item) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        const key = `cr_saved_filters_${this.resModel}`;
        let items = this.savedFilterItems;
        items = items.filter((i) => String(i.id) !== String(item.id));
        window.localStorage.setItem(key, JSON.stringify(items));
        this.state.historyVersion++;
    },

    onStartRenameGroupBy(ev, item) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        this.state.editingFilterId = item.id;
        setTimeout(() => {
            const inputEl = document.querySelector(`.o_saved_groupby_dropdown .o_rename_filter_input`);
            if (inputEl) {
                inputEl.focus();
                inputEl.select();
            }
        }, 50);
    },

    onSaveRenameGroupBy(ev, item) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
        }
        if (this.state.editingFilterId !== item.id) return;

        const rowEl = ev?.target?.closest(".o_recent_search_item");
        const inputEl = rowEl ? rowEl.querySelector(".o_rename_filter_input") : document.querySelector(".o_saved_groupby_dropdown .o_rename_filter_input");
        const newTitle = inputEl ? inputEl.value.trim() : "";

        if (newTitle && newTitle !== item.name) {
            const key = `cr_saved_groupby_${this.resModel}`;
            let items = this.savedGroupByItems;
            const targetIndex = items.findIndex((i) => String(i.id) === String(item.id));
            if (targetIndex >= 0) {
                items[targetIndex].name = newTitle;
                window.localStorage.setItem(key, JSON.stringify(items));
            }
        }
        this.state.editingFilterId = null;
        this.state.historyVersion++;
    },

    onKeydownRenameGroupBy(ev, item) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.onSaveRenameGroupBy(ev, item);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.state.editingFilterId = null;
        }
    },

    onDeleteSavedGroupBy(ev, item) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        const key = `cr_saved_groupby_${this.resModel}`;
        let items = this.savedGroupByItems;
        items = items.filter((i) => String(i.id) !== String(item.id));
        window.localStorage.setItem(key, JSON.stringify(items));
        this.state.historyVersion++;
    },

    onClearHistory(ev) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        const key = `cr_recent_history_${this.resModel}`;
        window.localStorage.removeItem(key);
        this.state.historyVersion++;
        this.state.showHistoryDropdown = false;
    },

    onClearSavedFilters(ev) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        const key = `cr_saved_filters_${this.resModel}`;
        window.localStorage.removeItem(key);
        this.state.historyVersion++;
        this.state.showSavedFiltersDropdown = false;
    },

    onClearSavedGroupBy(ev) {
        if (ev && typeof ev.stopPropagation === "function") {
            ev.stopPropagation();
            ev.preventDefault();
        }
        const key = `cr_saved_groupby_${this.resModel}`;
        window.localStorage.removeItem(key);
        this.state.historyVersion++;
        this.state.showSavedGroupByDropdown = false;
    },
});
