from odoo import fields, models


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    staff_sales_contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Staff Sales Contact',
        index=True,
        ondelete='restrict',
        copy=False,
    )
