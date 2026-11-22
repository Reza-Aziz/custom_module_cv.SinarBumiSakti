import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const DEBOUNCE_MS = 300;

/**
 * Per-type configuration, keyed by the value of data-dsr-search-type set by
 * the question template. To add another searchable dropdown, add an entry here
 * (plus its flag, template value and endpoint on the Python side).
 *
 * Endpoint results are [{ name, value? }]: `value` (when present) is the text
 * shown and saved as the answer, otherwise `name` is used.
 * `clearable` adds a "×" button that empties the selected value.
 */
function getSearchConfig(type) {
    const configs = {
        staff: {
            url: "/dynamic_sales_request/staff/search",
            maxResults: 5,
            needsTokens: false,
            clearable: false,
            placeholder: _t("Pilih Staff Sales"),
            searchPlaceholder: _t("Cari Staff Sales..."),
            emptyText: _t("Staff Sales tidak ditemukan."),
            failText: _t("Pencarian Staff Sales gagal. Silakan coba lagi."),
        },
        customer: {
            url: "/dynamic_sales_request/customer/search",
            maxResults: 10,
            needsTokens: true,
            clearable: true,
            placeholder: _t("Pilih Customer"),
            searchPlaceholder: _t("Cari Customer..."),
            emptyText: _t("Customer tidak ditemukan."),
            failText: _t("Pencarian Customer gagal. Silakan coba lagi."),
        },
    };
    return configs[type];
}

/**
 * Turns the standard char_box input of a flagged question (Staff Sales or
 * Customer Search) into a select-like searchable dropdown.
 *
 * The original input stays the submitted field (same name and
 * data-question-type), so the core SurveyForm validates and submits it and the
 * core controller saves it as a survey.user_input.line. It becomes readonly:
 * its value can only be set by picking an option. The search box lives in a
 * separate panel and has no name, so it is never submitted.
 *
 * The input value is the only selection state: clearing it (the "×" button)
 * fully resets the selection, and the standard required validation then
 * applies again on the empty input.
 */
export class DynamicSearchDropdown extends Interaction {
    static selector = "input[data-dsr-search-type]";

    dynamicContent = {
        _root: {
            "t-on-click": this.onTriggerClick,
            "t-on-keydown": this.onTriggerKeyDown,
        },
        _document: {
            "t-on-click": this.onDocumentClick,
        },
    };

    setup() {
        this.config = getSearchConfig(this.el.dataset.dsrSearchType);
        const formDataset = this.el.closest("form.o_survey-fill-form")?.dataset || {};
        this.surveyToken = formDataset.surveyToken || "";
        this.answerToken = formDataset.answerToken || "";

        this.isOpen = false;
        this.searchTimer = null;
        this.searchSequence = 0;
        this.activeIndex = -1;

        this.panelEl = document.createElement("div");
        this.panelEl.className =
            "o_dsr_staff_sales_panel bg-body border rounded shadow-sm d-none";

        const searchWrapEl = document.createElement("div");
        searchWrapEl.className = "p-2 border-bottom";
        this.searchEl = document.createElement("input");
        this.searchEl.type = "search";
        this.searchEl.className = "form-control form-control-sm o_dsr_staff_sales_search";
        this.searchEl.placeholder = this.config.searchPlaceholder;
        this.searchEl.autocomplete = "off";
        searchWrapEl.appendChild(this.searchEl);

        this.resultsEl = document.createElement("ul");
        this.resultsEl.className = "o_dsr_staff_sales_results list-group list-group-flush";
        this.resultsEl.setAttribute("role", "listbox");

        this.panelEl.append(searchWrapEl, this.resultsEl);

        // Clear ("×") button, only for configurations flagged `clearable`.
        this.clearEl = null;
        if (this.config.clearable) {
            this.clearEl = document.createElement("button");
            this.clearEl.type = "button";
            this.clearEl.className = "o_dsr_staff_sales_clear d-none";
            this.clearEl.textContent = "×";
            this.clearEl.title = _t("Hapus pilihan");
            this.clearEl.setAttribute("aria-label", _t("Hapus pilihan"));
        }
    }

    start() {
        // Select-box look; value can only come from the dropdown.
        this.el.readOnly = true;
        this.el.classList.remove("form-control");
        this.el.classList.add("form-select", "o_dsr_staff_sales_trigger");
        if (!this.el.placeholder) {
            this.el.placeholder = this.config.placeholder;
        }
        this.el.setAttribute("role", "combobox");
        this.el.setAttribute("aria-haspopup", "listbox");
        this.el.setAttribute("aria-expanded", "false");

        this.el.parentElement.classList.add("position-relative");
        this.insert(this.panelEl, this.el.parentElement);

        if (this.clearEl) {
            this.el.classList.add("o_dsr_staff_sales_clearable");
            this.insert(this.clearEl, this.el.parentElement);
            this.addListener(this.clearEl, "click", (ev) => this.onClearClick(ev));
            this.updateClearButton(); // A restored answer shows the "×" at once.
        }

        this.addListener(this.searchEl, "input", () => this.onSearchInput());
        this.addListener(this.searchEl, "keydown", (ev) => this.onSearchKeyDown(ev));
        this.addListener(this.resultsEl, "click", (ev) => this.onResultsClick(ev));
    }

    destroy() {
        window.clearTimeout(this.searchTimer);
    }

    // Open / close
    // -------------------------------------------------------------------------

    open() {
        if (this.isOpen) {
            return;
        }
        this.isOpen = true;
        this.panelEl.classList.remove("d-none");
        this.el.setAttribute("aria-expanded", "true");
        this.searchEl.value = "";
        this.search("");
        this.searchEl.focus();
    }

    close({ refocus = false } = {}) {
        if (!this.isOpen) {
            return;
        }
        this.isOpen = false;
        window.clearTimeout(this.searchTimer);
        this.searchSequence++; // Ignore any response still in flight.
        this.panelEl.classList.add("d-none");
        this.resultsEl.replaceChildren();
        this.activeIndex = -1;
        this.el.setAttribute("aria-expanded", "false");
        if (refocus) {
            this.el.focus();
        }
    }

    // Handlers
    // -------------------------------------------------------------------------

    onTriggerClick() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    onTriggerKeyDown(ev) {
        if (ev.ctrlKey || ev.metaKey) {
            return; // Leave Ctrl/Cmd+Enter to the survey (force submit).
        }
        if (ev.key === "Enter" || ev.key === " " || ev.key === "ArrowDown") {
            ev.preventDefault();
            this.open();
        } else if (ev.key === "Escape") {
            this.close();
        }
    }

    onDocumentClick(ev) {
        if (this.isOpen && ev.target !== this.el && !this.panelEl.contains(ev.target)) {
            this.close();
        }
    }

    onClearClick(ev) {
        ev.preventDefault();
        // Keep the document click handler from closing the dropdown reopened below.
        ev.stopPropagation();
        this.el.value = "";
        this.updateClearButton();
        // Restart with an empty search so another selection can be made at once.
        this.close();
        this.open();
    }

    onSearchInput() {
        window.clearTimeout(this.searchTimer);
        this.searchTimer = window.setTimeout(
            () => this.search(this.searchEl.value.trim()),
            DEBOUNCE_MS
        );
    }

    onSearchKeyDown(ev) {
        const options = this.getOptionEls();
        switch (ev.key) {
            case "ArrowDown":
            case "ArrowUp": {
                if (!options.length) {
                    return;
                }
                ev.preventDefault();
                const step = ev.key === "ArrowDown" ? 1 : -1;
                this.setActiveIndex((this.activeIndex + step + options.length) % options.length);
                break;
            }
            case "Enter": {
                // Never let Enter submit the survey from the search box.
                ev.preventDefault();
                const index = this.activeIndex >= 0 ? this.activeIndex : options.length === 1 ? 0 : -1;
                if (options[index]) {
                    this.selectName(options[index].dataset.name);
                }
                break;
            }
            case "Escape":
                ev.preventDefault();
                this.close({ refocus: true });
                break;
        }
    }

    onResultsClick(ev) {
        const optionEl = ev.target.closest("button[data-name]");
        if (optionEl) {
            this.selectName(optionEl.dataset.name);
        }
    }

    // Search
    // -------------------------------------------------------------------------

    async search(query) {
        const sequence = ++this.searchSequence;
        if (!this.resultsEl.children.length) {
            this.renderMessage(_t("Memuat..."));
        }
        let records = [];
        let failed = false;
        try {
            const params = new URLSearchParams({ q: query });
            if (this.config.needsTokens) {
                params.set("survey_token", this.surveyToken);
                params.set("answer_token", this.answerToken);
            }
            const response = await this.waitFor(
                fetch(`${this.config.url}?${params.toString()}`, {
                    method: "GET",
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                })
            );
            if (!response.ok) {
                throw new Error(`Search failed (${response.status})`);
            }
            const payload = await this.waitFor(response.json());
            records = (payload.results || []).slice(0, this.config.maxResults);
        } catch {
            failed = true;
        }
        if (sequence !== this.searchSequence) {
            return; // Superseded by a newer search, or the dropdown was closed.
        }
        if (failed) {
            this.renderMessage(this.config.failText);
        } else if (!records.length) {
            this.renderMessage(this.config.emptyText);
        } else {
            this.renderResults(records);
        }
    }

    renderMessage(text) {
        this.resultsEl.replaceChildren();
        this.activeIndex = -1;
        const messageEl = document.createElement("li");
        messageEl.className = "list-group-item text-muted";
        messageEl.textContent = text;
        this.resultsEl.appendChild(messageEl);
    }

    renderResults(records) {
        this.resultsEl.replaceChildren();
        this.activeIndex = -1;
        for (const record of records) {
            const text = record.value || record.name;
            const itemEl = document.createElement("li");
            itemEl.className = "list-group-item p-0";
            itemEl.setAttribute("role", "option");

            const buttonEl = document.createElement("button");
            buttonEl.type = "button";
            buttonEl.className = "o_dsr_staff_sales_option btn btn-link w-100 text-start";
            buttonEl.dataset.name = text;
            buttonEl.textContent = text;
            const isSelected = text === this.el.value;
            buttonEl.classList.toggle("fw-bold", isSelected);
            itemEl.setAttribute("aria-selected", String(isSelected));

            itemEl.appendChild(buttonEl);
            this.resultsEl.appendChild(itemEl);
        }
    }

    // Selection helpers
    // -------------------------------------------------------------------------

    selectName(name) {
        this.el.value = name;
        this.updateClearButton();
        this.close({ refocus: true });
    }

    updateClearButton() {
        if (!this.clearEl) {
            return;
        }
        const hasValue = Boolean(this.el.value);
        this.clearEl.classList.toggle("d-none", !hasValue);
        if (hasValue && this.el.offsetHeight) {
            // Same height as the input (it is larger in "page per question").
            this.clearEl.style.height = `${this.el.offsetHeight}px`;
        }
    }

    getOptionEls() {
        return Array.from(this.resultsEl.querySelectorAll("button[data-name]"));
    }

    setActiveIndex(index) {
        const options = this.getOptionEls();
        options.forEach((el, i) => el.classList.toggle("active", i === index));
        this.activeIndex = index;
        options[index]?.scrollIntoView({ block: "nearest" });
    }
}

registry
    .category("public.interactions")
    .add("custom_survey.DynamicSearchDropdown", DynamicSearchDropdown);