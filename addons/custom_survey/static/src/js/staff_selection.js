import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const SEARCH_URL = "/dynamic_sales_request/staff/search";
const DEBOUNCE_MS = 300;
const MAX_RESULTS = 5;

/**
 * Turns the standard char_box input of a question flagged as
 * "Staff Sales Search" into a searchable dropdown.
 *
 * The input keeps its standard name / data-question-type, so the core
 * SurveyForm validates and submits it and the core controller saves it as a
 * survey.user_input.line. This interaction only guarantees that the input
 * value is either empty or a value picked from the dropdown.
 */
export class StaffSalesSearch extends Interaction {
    static selector = "input[data-dsr-staff-sales]";

    dynamicContent = {
        _root: {
            "t-on-input": this.onInput,
            "t-on-keydown": this.onKeyDown,
            "t-on-focusout": this.onFocusOut,
        },
    };

    setup() {
        // A value restored from a previous answer counts as already selected.
        this.selectedName = this.el.value.trim();
        this.searchTimer = null;
        this.searchSequence = 0;
        this.activeIndex = -1;

        this.resultsEl = document.createElement("ul");
        this.resultsEl.className = "o_dsr_staff_sales_results list-group d-none";
        this.resultsEl.setAttribute("role", "listbox");

        this.el.setAttribute("role", "combobox");
        this.el.setAttribute("aria-autocomplete", "list");
        this.el.setAttribute("aria-expanded", "false");
    }

    start() {
        this.insert(this.resultsEl, this.el.parentElement);
        // Keep the focus on the input so focusout does not fire (and clear the
        // value) before the click selects an option.
        this.addListener(this.resultsEl, "mousedown", (ev) => this.onResultsMouseDown(ev));
    }

    destroy() {
        window.clearTimeout(this.searchTimer);
    }

    // Handlers
    // -------------------------------------------------------------------------

    onInput() {
        const value = this.el.value.trim();
        if (value !== this.selectedName) {
            this.selectedName = "";
        }
        window.clearTimeout(this.searchTimer);
        this.hideResults();
        if (!value) {
            this.searchSequence++;
            return;
        }
        this.searchTimer = window.setTimeout(() => this.search(value), DEBOUNCE_MS);
    }

    onKeyDown(ev) {
        const options = this.getOptionEls();
        switch (ev.key) {
            case "ArrowDown":
            case "ArrowUp": {
                if (!options.length || this.resultsEl.classList.contains("d-none")) {
                    return;
                }
                ev.preventDefault();
                const step = ev.key === "ArrowDown" ? 1 : -1;
                this.setActiveIndex((this.activeIndex + step + options.length) % options.length);
                break;
            }
            case "Enter":
                if (this.activeIndex >= 0 && options[this.activeIndex]) {
                    ev.preventDefault();
                    this.selectName(options[this.activeIndex].dataset.name);
                }
                break;
            case "Escape":
                this.hideResults();
                break;
        }
    }

    onFocusOut() {
        window.clearTimeout(this.searchTimer);
        this.searchSequence++;
        this.hideResults();
        // Free text is not an answer: only a selected value is kept.
        if (this.el.value.trim() !== this.selectedName) {
            this.el.value = "";
            this.selectedName = "";
        }
    }

    onResultsMouseDown(ev) {
        ev.preventDefault();
        const optionEl = ev.target.closest("button[data-name]");
        if (optionEl) {
            this.selectName(optionEl.dataset.name);
        }
    }

    // Search
    // -------------------------------------------------------------------------

    async search(query) {
        const sequence = ++this.searchSequence;
        let records = [];
        let failed = false;
        try {
            const response = await this.waitFor(
                fetch(`${SEARCH_URL}?q=${encodeURIComponent(query)}`, {
                    method: "GET",
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                })
            );
            if (!response.ok) {
                throw new Error(`Staff search failed (${response.status})`);
            }
            const payload = await this.waitFor(response.json());
            records = (payload.results || []).slice(0, MAX_RESULTS);
        } catch {
            failed = true;
        }
        if (sequence !== this.searchSequence) {
            return; // A newer search (or a focusout) superseded this one.
        }
        this.renderResults(records, failed);
    }

    renderResults(records, failed) {
        this.resultsEl.replaceChildren();
        this.activeIndex = -1;

        if (failed || !records.length) {
            const emptyEl = document.createElement("li");
            emptyEl.className = "list-group-item text-muted";
            emptyEl.textContent = failed
                ? _t("Pencarian Staff Sales gagal. Silakan coba lagi.")
                : _t("Staff Sales tidak ditemukan.");
            this.resultsEl.appendChild(emptyEl);
        } else {
            for (const record of records) {
                const itemEl = document.createElement("li");
                itemEl.className = "list-group-item p-0";
                itemEl.setAttribute("role", "option");

                const buttonEl = document.createElement("button");
                buttonEl.type = "button";
                buttonEl.className = "o_dsr_staff_sales_option btn btn-link w-100 text-start";
                buttonEl.dataset.name = record.name;
                buttonEl.textContent = record.name;

                itemEl.appendChild(buttonEl);
                this.resultsEl.appendChild(itemEl);
            }
        }
        this.resultsEl.classList.remove("d-none");
        this.el.setAttribute("aria-expanded", "true");
    }

    // Selection helpers
    // -------------------------------------------------------------------------

    selectName(name) {
        this.el.value = name;
        this.selectedName = name;
        this.searchSequence++;
        this.hideResults();
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

    hideResults() {
        this.resultsEl.classList.add("d-none");
        this.resultsEl.replaceChildren();
        this.activeIndex = -1;
        this.el.setAttribute("aria-expanded", "false");
    }
}

registry
    .category("public.interactions")
    .add("custom_survey.StaffSalesSearch", StaffSalesSearch);