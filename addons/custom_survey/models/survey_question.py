import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Customer and product answers are stored as "<label> (ID: <record id>)" so the
# exact record can be resolved later even when several records share a name.
ID_ANSWER_RE = re.compile(r'^(?P<name>.+) \(ID: (?P<id>\d+)\)$')
SEARCH_MAX_TOKENS = 5


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

    @api.constrains('is_staff_sales_search', 'is_customer_search', 'is_product_search')
    def _check_dynamic_search_exclusive(self):
        for question in self:
            flags = (
                question.is_staff_sales_search,
                question.is_customer_search,
                question.is_product_search,
            )
            if sum(bool(flag) for flag in flags) > 1:
                raise ValidationError(_(
                    "A question can use only one dynamic search type "
                    "(Staff Sales, Customer or Product)."
                ))

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