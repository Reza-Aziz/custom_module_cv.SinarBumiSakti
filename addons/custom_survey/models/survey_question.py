import json
import math
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Customer and product answers are stored as "<label> (ID: <record id>)" so the
# exact record can be resolved later even when several records share a name.
ID_ANSWER_RE = re.compile(r'^(?P<name>.+) \(ID: (?P<id>\d+)\)$')
SEARCH_MAX_TOKENS = 5
PRODUCT_LINES_MAX = 50


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    is_staff_sales_search = fields.Boolean(
        string='Staff Sales Search',
        default=False,
        help="If checked, this text box question becomes a searchable dropdown "
             "of active Contacts whose name starts with 'STAFF SALES'. "
             "Only a value selected from that list is accepted.",
    )
    is_customer_search = fields.Boolean(
        string='Customer Search',
        default=False,
        help="If checked, this text box question becomes a searchable dropdown "
             "of active Contacts (res.partner). Only a value selected from "
             "that list is accepted; it is saved as '<name> (ID: <id>)'.",
    )
    is_product_search = fields.Boolean(
        string='Product Search',
        default=False,
        help="If checked, this text box question becomes a searchable dropdown "
             "of active products (product.product), searchable by name or "
             "Internal Reference. Only a value selected from that list is "
             "accepted; it is saved as '<product label> (ID: <id>)'.",
    )
    is_product_lines = fields.Boolean(
        string='Product Lines',
        default=False,
        help="If checked, this text box question becomes a chain of product "
             "lines (product, quantity, UoM). The lines are saved as a JSON "
             "list and validated on the server.",
    )
    product_lines_uoms_json = fields.Char(
        compute='_compute_product_lines_uoms_json',
        help="Active units of measure (JSON) rendered into the survey page "
             "for the product lines UoM dropdown. Not stored: it always "
             "follows the latest master data.",
    )

    product_lines_product_question_id = fields.Many2one(
    'survey.question',
    string='Product Question',
    domain="[('survey_id', '=', survey_id), ('is_product_search', '=', True)]",
    help="Product question that this product lines question refers to.",
    )

    @api.constrains(
        'is_staff_sales_search', 'is_customer_search',
        'is_product_search', 'is_product_lines',
    )
    def _check_dynamic_search_exclusive(self):
        for question in self:
            flags = (
                question.is_staff_sales_search,
                question.is_customer_search,
                question.is_product_search,
                question.is_product_lines,
            )
            if sum(bool(flag) for flag in flags) > 1:
                raise ValidationError(_(
                    "A question can use only one dynamic type "
                    "(Staff Sales, Customer, Product or Product Lines)."
                ))

    @api.depends('is_product_lines')
    def _compute_product_lines_uoms_json(self):
        flagged = self.filtered('is_product_lines')
        options = False
        if flagged:
            uoms = self.env['uom.uom'].sudo().search(self._get_product_lines_uom_domain())
            options = json.dumps(
                [{'id': uom.id, 'name': uom.display_name} for uom in uoms],
                ensure_ascii=False,
            )
        for question in self:
            question.product_lines_uoms_json = options if question in flagged else False

    # Staff Sales
    # -------------------------------------------------------------------------

    @api.model
    def _get_staff_sales_domain(self, query=None):
        """Single source of truth for the Staff Sales Contact filter."""
        domain = [
            ('active', '=', True),
            ('name', '=ilike', 'STAFF SALES%'),
        ]
        if query:
            domain.append(('name', 'ilike', query))
        return domain

    # Customer
    # -------------------------------------------------------------------------

    @api.model
    def _get_customer_domain(self, query=None):
        """Single source of truth for the Customer filter (PRD FR-002).

        Every word of the query must appear in the name (case-insensitive,
        any order). PRD open decision OD-007 (exact customer domain) is still
        unresolved: adjust here only.
        """
        domain = [('active', '=', True)]
        for token in (query or '').split()[:SEARCH_MAX_TOKENS]:
            domain.append(('name', 'ilike', token))
        return domain

    @api.model
    def _format_customer_answer(self, partner_id, name):
        return "%s (ID: %s)" % (name, partner_id)

    # Product
    # -------------------------------------------------------------------------

    @api.model
    def _get_product_domain(self, query=None):
        """Single source of truth for the Product filter (PRD FR-005).

        Active products only. Every word of the query must appear in the name
        or in the Internal Reference (case-insensitive, any order). PRD open
        decision OD-005 (all active products vs sales-only) is unresolved:
        adjust here only.
        """
        domain = [('active', '=', True)]
        for token in (query or '').split()[:SEARCH_MAX_TOKENS]:
            domain += ['|', ('name', 'ilike', token), ('default_code', 'ilike', token)]
        return domain

    @api.model
    def _format_product_answer(self, product):
        return "%s (ID: %s)" % (product.display_name, product.id)

    # Product lines
    # -------------------------------------------------------------------------

    @api.model
    def _get_product_lines_uom_domain(self):
        """Units of measure selectable in a product line (master data uom.uom)."""
        if 'active' in self.env['uom.uom']._fields:
            return [('active', '=', True)]
        return []

    # Validation (backend is authoritative)
    # -------------------------------------------------------------------------

    def _validate_char_box(self, answer):
        errors = super()._validate_char_box(answer)
        if errors:
            return errors
        if self.is_staff_sales_search:
            return self._validate_staff_sales_answer(answer)
        if self.is_customer_search:
            return self._validate_customer_answer(answer)
        if self.is_product_search:
            return self._validate_product_answer(answer)
        if self.is_product_lines:
            return self._validate_product_lines_answer(answer)
        return errors

    def _validate_staff_sales_answer(self, answer):
        # The answer must be the exact name of an active STAFF SALES contact.
        domain = self._get_staff_sales_domain() + [('name', '=', answer)]
        if not self.env['res.partner'].sudo().search_count(domain, limit=1):
            return {self.id: _(
                "Staff Sales tidak valid. Pilih Staff Sales dari hasil pencarian."
            )}
        return {}

    def _validate_customer_answer(self, answer):
        # The answer must be "<name> (ID: <id>)" of an active partner whose
        # name really matches that id.
        error = {self.id: _(
            "Customer tidak valid. Pilih Customer dari hasil pencarian."
        )}
        match = ID_ANSWER_RE.match(answer)
        if not match:
            return error
        domain = self._get_customer_domain() + [
            ('id', '=', int(match.group('id'))),
            ('name', '=', match.group('name')),
        ]
        if not self.env['res.partner'].sudo().search_count(domain, limit=1):
            return error
        return {}

    def _validate_product_answer(self, answer):
        # The answer must be "<label> (ID: <id>)" where <id> is an existing,
        # active product. The id is authoritative; the label is informational
        # (it can legitimately differ by language or after a rename).
        error = {self.id: _(
            "Produk tidak valid. Pilih Produk dari hasil pencarian."
        )}
        match = ID_ANSWER_RE.match(answer)
        if not match:
            return error
        domain = self._get_product_domain() + [('id', '=', int(match.group('id')))]
        if not self.env['product.product'].sudo().search_count(domain, limit=1):
            return error
        return {}

    def _validate_product_lines_answer(self, answer):
        # The answer is a JSON list of {product_id, quantity, uom_id, more, ...}.
        # product_id, quantity, uom_id and more are authoritative; the other
        # keys are informational. The chain must be closed: every line but the
        # last has more="yes" and the last one has more="no".
        error = {self.id: _(
            "Daftar produk tidak valid. Lengkapi semua baris produk."
        )}
        try:
            lines = json.loads(answer)
        except ValueError:
            return error
        if not isinstance(lines, list) or not lines or len(lines) > PRODUCT_LINES_MAX:
            return error

        Product = self.env['product.product'].sudo()
        Uom = self.env['uom.uom'].sudo()
        problems = []
        for index, line in enumerate(lines, start=1):
            if not isinstance(line, dict):
                return error
            problem = self._get_product_line_problem(
                Product, Uom, line, is_last=index == len(lines)
            )
            if problem:
                problems.append(_("Baris %s: %s") % (index, problem))
        if problems:
            return {self.id: " ".join(problems)}
        return {}

    def _get_product_line_problem(self, Product, Uom, line, is_last):
        product_id = line.get('product_id')
        quantity = line.get('quantity')
        uom_id = line.get('uom_id')
        more = line.get('more')

        if not isinstance(product_id, int) or isinstance(product_id, bool):
            return _("produk belum dipilih.")
        if not Product.search_count(
            self._get_product_domain() + [('id', '=', product_id)], limit=1
        ):
            return _("produk tidak valid atau sudah tidak aktif.")
        if (
            not isinstance(quantity, (int, float))
            or isinstance(quantity, bool)
            or not math.isfinite(quantity)
            or quantity <= 0
        ):
            return _("quantity harus lebih dari 0.")
        if (
            not isinstance(uom_id, int)
            or isinstance(uom_id, bool)
            or not Uom.search_count(
                self._get_product_lines_uom_domain() + [('id', '=', uom_id)], limit=1
            )
        ):
            return _("UoM belum dipilih atau tidak valid.")
        if more not in ('yes', 'no'):
            return _("jawab pertanyaan 'Apakah ada produk tambahan?'.")
        if is_last and more != 'no':
            return _("pilih 'Tidak ada lagi' pada baris terakhir untuk menyelesaikan.")
        if not is_last and more != 'yes':
            return _("jawaban harus 'Ya' karena masih ada baris berikutnya.")
        return False