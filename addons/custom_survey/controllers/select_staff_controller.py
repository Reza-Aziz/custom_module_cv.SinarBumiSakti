import json
from odoo import http
from odoo.http import request


class DynamicStaffController(http.Controller):

    @http.route(
        '/dynamic_sales_request/staff/search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def search_staff(self, **kwargs):
        query = (request.httprequest.args.get('q') or '').strip()

        # Jangan mengembalikan seluruh Staff Sales ketika query kosong.
        if not query:
            return request.make_response(
                json.dumps({'results': []}),
                headers=[('Content-Type', 'application/json')],
            )

        # Batasi panjang input pencarian.
        query = query[:100]

        domain = [
            ('active', '=', True),
            ('name', '=ilike', 'STAFF SALES%'),
            ('name', 'ilike', query),
        ]

        staff_records = request.env['res.partner'].sudo().search_read(
            domain,
            fields=['id', 'name'],
            limit=10,
            order='name asc',
        )

        return request.make_response(
            json.dumps({'results': staff_records}),
            headers=[('Content-Type', 'application/json')],
        )