import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Customer answers are stored as "<name> (ID: <res.partner id>)" so the exact
# record can be resolved later even when several partners share the same name.
CUSTOMER_ANSWER_RE = re.compile(r'^(?P<name>.+) \(ID: (?P<id>\d+)\)$')
CUSTOMER_SEARCH_MAX_TOKENS = 5


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

    @api.constrains('is_staff_sales_search', 'is_customer_search')
    def _check_dynamic_search_exclusive(self):
        for question in self:
            if question.is_staff_sales_search and question.is_customer_search:
                raise ValidationError(_(
                    "A question cannot be both a Staff Sales Search and a Customer Search."
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
        for token in (query or '').split()[:CUSTOMER_SEARCH_MAX_TOKENS]:
            domain.append(('name', 'ilike', token))
        return domain

    @api.model
    def _format_customer_answer(self, partner_id, name):
        return "%s (ID: %s)" % (name, partner_id)

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
        match = CUSTOMER_ANSWER_RE.match(answer)
        if not match:
            return error
        domain = self._get_customer_domain() + [
            ('id', '=', int(match.group('id'))),
            ('name', '=', match.group('name')),
        ]
        if not self.env['res.partner'].sudo().search_count(domain, limit=1):
            return error
        return {}