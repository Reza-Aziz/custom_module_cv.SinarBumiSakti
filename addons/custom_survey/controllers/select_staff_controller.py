import json

from odoo import http
from odoo.http import request

STAFF_SALES_SEARCH_LIMIT = 5


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
        query = (request.httprequest.args.get('q') or '').strip()[:100]

        domain = request.env['survey.question']._get_staff_sales_domain(query)
        staff_records = request.env['res.partner'].sudo().search_read(
            domain,
            fields=['id', 'name'],
            limit=STAFF_SALES_SEARCH_LIMIT,
            order='name asc',
        )
        return self._json_response({'results': staff_records})

    @staticmethod
    def _json_response(payload):
        return request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json')],
        )