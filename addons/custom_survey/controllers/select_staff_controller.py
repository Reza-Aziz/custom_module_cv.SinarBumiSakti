import json

from odoo import http
from odoo.addons.survey.controllers.main import Survey
from odoo.http import request

STAFF_SALES_SEARCH_LIMIT = 5
CUSTOMER_SEARCH_LIMIT = 10
MAX_QUERY_LENGTH = 100


class DynamicStaffController(http.Controller):

    @http.route(
        '/dynamic_sales_request/staff/search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def search_staff(self, **kwargs):
        # Empty query is allowed: it returns the first
        # STAFF_SALES_SEARCH_LIMIT records so the dropdown has content on open.
        query = (request.httprequest.args.get('q') or '').strip()[:MAX_QUERY_LENGTH]

        domain = request.env['survey.question']._get_staff_sales_domain(query)
        staff_records = request.env['res.partner'].sudo().search_read(
            domain,
            fields=['id', 'name'],
            limit=STAFF_SALES_SEARCH_LIMIT,
            order='name asc',
        )
        return self._json_response({'results': staff_records})

    @http.route(
        '/dynamic_sales_request/customer/search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def search_customer(self, **kwargs):
        # Customer data is more sensitive than staff names: the caller must
        # hold a valid survey/answer token pair, checked with the same logic
        # the core Survey applies before accepting a submission.
        args = request.httprequest.args
        survey_token = args.get('survey_token')
        answer_token = args.get('answer_token')
        if not survey_token or not answer_token:
            return self._json_response({'results': []}, status=403)
        access_data = Survey()._get_access_data(
            survey_token, answer_token, ensure_token=True
        )
        if access_data['validity_code'] is not True:
            return self._json_response({'results': []}, status=403)

        query = (args.get('q') or '').strip()[:MAX_QUERY_LENGTH]
        Question = request.env['survey.question']
        partners = request.env['res.partner'].sudo().search_read(
            Question._get_customer_domain(query),
            fields=['id', 'name'],
            limit=CUSTOMER_SEARCH_LIMIT,
            order='name asc',
        )
        results = [{
            'id': partner['id'],
            'name': partner['name'],
            'value': Question._format_customer_answer(partner['id'], partner['name']),
        } for partner in partners]
        return self._json_response({'results': results})

    @staticmethod
    def _json_response(payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )