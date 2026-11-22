from odoo import _, api, fields, models


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    is_staff_sales_search = fields.Boolean(
        string='Staff Sales Search',
        default=False,
        help="If checked, this text box question becomes a searchable dropdown "
             "of active Contacts whose name starts with 'STAFF SALES'. "
             "Only a value selected from that list is accepted.",
    )

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

    def _validate_char_box(self, answer):
        errors = super()._validate_char_box(answer)
        if errors or not self.is_staff_sales_search:
            return errors
        # Never trust the frontend: the answer must be the exact name of an
        # active STAFF SALES contact.
        domain = self._get_staff_sales_domain() + [('name', '=', answer)]
        if not self.env['res.partner'].sudo().search_count(domain, limit=1):
            return {self.id: _(
                "Staff Sales tidak valid. Pilih Staff Sales dari hasil pencarian."
            )}
        return {}