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
    dsr_result_status = fields.Selection(
        [('success', 'Success'), ('failed', 'Failed')],
        string='Result Status',
        copy=False,
    )
    dsr_quotation_name = fields.Char(string='Quotation Number', copy=False)
    dsr_staff_name = fields.Char(string='Staff Sales Name', copy=False)
    dsr_customer_name = fields.Char(string='Customer Name', copy=False)
    dsr_error_code = fields.Char(string='Error Code', copy=False)
    dsr_result_message = fields.Char(string='Result Message', copy=False)