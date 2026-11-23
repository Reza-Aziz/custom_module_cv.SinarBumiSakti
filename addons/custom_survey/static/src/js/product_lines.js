import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

const MAX_LINES = 50;

function parseList(text) {
    try {
        const list = JSON.parse(text || "[]");
        return Array.isArray(list) ? list : [];
    } catch {
        return [];
    }
}

/**
 * Product lines widget for a char_box question flagged "Product Lines".
 *
 * The question input stays the submitted field (same name and
 * data-question-type) but is hidden: its value is a JSON list
 * [{ product_id, quantity, uom_id, more, product, uom }] rebuilt from the rows
 * whenever something changes. The backend
 * (survey.question._validate_product_lines_answer) validates every line
 * again. Rows, radios and selects have no `data-question-type`, so the core
 * Survey never treats them as answers.
 *
 * The first row is created when the page loads (or restored). Rows form a
 * chain and only the LAST row's radio group is active:
 * - "yes"    appends a new row below and locks this row on "yes";
 * - "remove" deletes this (last) row; the previous row is unlocked and its
 *            answer reset; unavailable on the first row;
 * - "no"     closes the chain (required to submit; enforced by the backend).
 *
 * Each row's product field is a plain <input data-dsr-search-type="product">
 * brought to life with the existing DynamicSearchDropdown through the
 * public.interactions service; rows are stopped before being removed.
 */
export class ProductLines extends Interaction {
    static selector = "input[data-dsr-product-lines]";

    setup() {
        const formEl = this.el.closest("form.o_survey-fill-form");
        this.answerToken = formEl?.dataset.answerToken || "";
        this.uoms = parseList(this.el.dataset.dsrUoms);
        this.storageKey = `dsr_lines:${this.answerToken}:${this.el.name}`;
        this.nextUid = 1;

        this.bodyEl = document.createElement("div");
        this.bodyEl.className = "o_dsr_lines mt-2";
    }

    start() {
        this.el.type = "hidden";
        this.insert(this.bodyEl, this.el.parentElement);

        this.addListener(this.bodyEl, "change", (ev) => this.onBodyChange(ev));
        this.addListener(this.bodyEl, "input", (ev) => this.onBodyInput(ev));
        this.addListener(this.bodyEl, "dsr-selection-change", (ev) => this.onLineSelection(ev));

        this.restoreRows();
        if (!this.rowEls.length) {
            this.addRow();
        }
        this.refresh();
    }

    destroy() {
        for (const rowEl of this.rowEls) {
            this.services["public.interactions"].stopInteractions(rowEl);
        }
    }

    get rowEls() {
        return Array.from(this.bodyEl.children);
    }

    // Rows
    // -------------------------------------------------------------------------

    createChoiceEl(uid, value, text) {
        const wrapEl = document.createElement("div");
        wrapEl.className = "form-check";
        const inputEl = document.createElement("input");
        inputEl.type = "radio";
        inputEl.className = "form-check-input";
        inputEl.name = `dsr_more_${uid}`;
        inputEl.id = `dsr_more_${uid}_${value}`;
        inputEl.value = value;
        const labelEl = document.createElement("label");
        labelEl.className = "form-check-label";
        labelEl.htmlFor = inputEl.id;
        labelEl.textContent = text;
        wrapEl.append(inputEl, labelEl);
        return wrapEl;
    }

    addRow(line = null) {
        if (this.rowEls.length >= MAX_LINES) {
            return;
        }
        const uid = this.nextUid++;
        const number = this.rowEls.length + 1;
        const rowEl = document.createElement("div");
        rowEl.className = "o_dsr_line border rounded p-3 mb-3";

        const titleEl = document.createElement("div");
        titleEl.className = "fw-semibold mb-2";
        titleEl.textContent = _t("Baris %s", number);

        // The product input must be the only child of its wrapper: the search
        // dropdown inserts its panel and clear button into the parent.
        const productWrapEl = document.createElement("div");
        productWrapEl.className = "mb-2";
        const productInputEl = document.createElement("input");
        productInputEl.type = "text";
        productInputEl.className = "form-control o_dsr_line_product";
        productInputEl.dataset.dsrSearchType = "product";
        productInputEl.placeholder = _t("Produk baris %s", number);
        productWrapEl.appendChild(productInputEl);

        const amountsEl = document.createElement("div");
        amountsEl.className = "o_dsr_line_amounts d-flex gap-2 mb-2";
        const qtyEl = document.createElement("input");
        qtyEl.type = "number";
        qtyEl.min = "0";
        qtyEl.step = "any";
        qtyEl.inputMode = "decimal";
        qtyEl.className = "form-control o_dsr_line_qty";
        qtyEl.placeholder = _t("Quantity");
        const uomEl = document.createElement("select");
        uomEl.className = "form-select o_dsr_line_uom";
        const emptyOptionEl = document.createElement("option");
        emptyOptionEl.value = "";
        emptyOptionEl.textContent = _t("Pilih UoM");
        uomEl.appendChild(emptyOptionEl);
        for (const uom of this.uoms) {
            const optionEl = document.createElement("option");
            optionEl.value = String(uom.id);
            optionEl.textContent = uom.name;
            uomEl.appendChild(optionEl);
        }
        amountsEl.append(qtyEl, uomEl);

        const moreEl = document.createElement("fieldset");
        moreEl.className = "o_dsr_line_more";
        const legendEl = document.createElement("legend");
        legendEl.className = "fs-6 mb-1";
        legendEl.textContent = _t("Apakah ada produk tambahan?");
        moreEl.append(
            legendEl,
            this.createChoiceEl(uid, "yes", _t("Ya, tambah produk lagi")),
            this.createChoiceEl(uid, "remove", _t("Hapus baris ini")),
            this.createChoiceEl(uid, "no", _t("Tidak ada lagi"))
        );

        rowEl.append(titleEl, productWrapEl, amountsEl, moreEl);

        // Restore a saved line.
        rowEl.dataset.more = line && line.more === "no" ? "no" : "";
        if (rowEl.dataset.more === "no") {
            moreEl.querySelector('input[value="no"]').checked = true;
        }
        if (line && Number.isInteger(line.product_id)) {
            rowEl.dataset.productId = String(line.product_id);
            rowEl.dataset.productLabel = line.product || "";
            productInputEl.value = `${line.product || ""} (ID: ${line.product_id})`;
        }
        if (line && line.quantity !== null && line.quantity !== undefined) {
            qtyEl.value = line.quantity;
        }
        if (line && line.uom_id && this.uoms.some((uom) => uom.id === line.uom_id)) {
            uomEl.value = String(line.uom_id);
        }

        this.bodyEl.appendChild(rowEl);
        // Start the existing Product Search dropdown on the new row.
        this.services["public.interactions"].startInteractions(rowEl);
    }

    removeRow(rowEl) {
        this.services["public.interactions"].stopInteractions(rowEl);
        rowEl.remove();
    }

    restoreRows() {
        // The server value (navigation) wins over the session backup (reload).
        let lines = parseList(this.el.value);
        if (!lines.length) {
            lines = parseList(this.readBackup());
        }
        for (const line of lines.slice(0, MAX_LINES)) {
            if (line && typeof line === "object") {
                this.addRow(line);
            }
        }
    }

    refresh() {
        const rowEls = this.rowEls;
        const lastIndex = rowEls.length - 1;
        rowEls.forEach((rowEl, index) => {
            const isLast = index === lastIndex;
            const moreEl = rowEl.querySelector(".o_dsr_line_more");
            if (!isLast) {
                // A row followed by another row is always answered "yes" and locked.
                rowEl.dataset.more = "yes";
                moreEl.querySelector('input[value="yes"]').checked = true;
            }
            moreEl.disabled = !isLast;
            if (isLast) {
                moreEl.querySelector('input[value="remove"]').disabled = rowEls.length <= 1;
                moreEl.querySelector('input[value="yes"]').disabled = rowEls.length >= MAX_LINES;
            }
        });
        this.syncValue();
    }

    // Handlers
    // -------------------------------------------------------------------------

    onBodyChange(ev) {
        const rowEl = ev.target.closest(".o_dsr_line");
        if (!rowEl) {
            return;
        }
        if (ev.target.matches(".o_dsr_line_more input")) {
            this.onMoreChange(rowEl);
        } else if (ev.target.matches(".o_dsr_line_uom")) {
            this.syncValue();
        }
    }

    onBodyInput(ev) {
        if (ev.target.classList.contains("o_dsr_line_qty")) {
            this.syncValue();
        }
    }

    onMoreChange(rowEl) {
        // The core Survey can also un-check a radio (clicking a selected one):
        // then nothing is checked and the row is simply "not answered".
        const choice = rowEl.querySelector(".o_dsr_line_more input:checked")?.value || "";
        if (choice === "remove") {
            const rowEls = this.rowEls;
            if (rowEls.length > 1 && rowEl === rowEls[rowEls.length - 1]) {
                this.removeRow(rowEl);
                // The previous row becomes the last one again: answer reset.
                const previousEl = this.rowEls[this.rowEls.length - 1];
                previousEl.dataset.more = "";
                previousEl
                    .querySelectorAll(".o_dsr_line_more input")
                    .forEach((inputEl) => (inputEl.checked = false));
            } else {
                rowEl.querySelector('.o_dsr_line_more input[value="remove"]').checked = false;
            }
        } else {
            rowEl.dataset.more = choice;
            if (choice === "yes" && rowEl === this.rowEls[this.rowEls.length - 1]) {
                this.addRow();
            }
        }
        this.refresh();
    }

    onLineSelection(ev) {
        const rowEl = ev.target.closest(".o_dsr_line");
        if (!rowEl) {
            return;
        }
        const record = ev.detail?.record;
        rowEl.dataset.productId = record ? String(record.id) : "";
        rowEl.dataset.productLabel = record ? record.label || record.name || "" : "";
        this.syncValue();
    }

    // Answer value and session backup
    // -------------------------------------------------------------------------

    collectLines() {
        return this.rowEls.map((rowEl) => {
            const qty = rowEl.querySelector(".o_dsr_line_qty").value;
            const uomEl = rowEl.querySelector(".o_dsr_line_uom");
            return {
                product_id: rowEl.dataset.productId ? Number(rowEl.dataset.productId) : null,
                quantity: qty === "" ? null : Number(qty),
                uom_id: uomEl.value ? Number(uomEl.value) : null,
                more: rowEl.dataset.more || null,
                product: rowEl.dataset.productLabel || "",
                uom: uomEl.value ? uomEl.selectedOptions[0].textContent : "",
            };
        });
    }

    syncValue() {
        const lines = this.collectLines();
        const text = lines.length ? JSON.stringify(lines) : "";
        if (text) {
            this.saveBackup(text);
        }
        this.el.value = text;
    }

    saveBackup(text) {
        try {
            window.sessionStorage.setItem(this.storageKey, text);
        } catch {
            // Storage unavailable: the server value remains the only source.
        }
    }

    readBackup() {
        try {
            return window.sessionStorage.getItem(this.storageKey);
        } catch {
            return null;
        }
    }
}

registry.category("public.interactions").add("custom_survey.ProductLines", ProductLines);