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

    def _save_lines(self, question, answer, comment=None, overwrite_existing=True):
        # The core saves every valid answer even when another question of the
        # same page fails validation. Without "Users can go back", sending the
        # corrected page again then raises "This answer cannot be overwritten".
        # Allow the overwrite for non-scored surveys that use our dynamic
        # questions; quizzes and other surveys keep the core guard.
        if not overwrite_existing and self._dsr_allow_overwrite():
            overwrite_existing = True
        return super()._save_lines(
            question, answer, comment, overwrite_existing=overwrite_existing
        )

    def _dsr_allow_overwrite(self):
        self.ensure_one()
        survey = self.survey_id
        if survey.scoring_type != 'no_scoring':
            return False
        return any(
            question.is_staff_sales_search
            or question.is_customer_search
            or question.is_product_search
            or question.is_product_lines
            for question in survey.question_ids
        )