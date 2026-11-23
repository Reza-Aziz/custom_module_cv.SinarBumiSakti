import json

from odoo import http
from odoo.addons.survey.controllers.main import Survey
from odoo.http import request

STAFF_SALES_SEARCH_LIMIT = 5
CUSTOMER_SEARCH_LIMIT = 10
PRODUCT_SEARCH_LIMIT = 10
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
        args = request.httprequest.args
        if not self._has_survey_access(args):
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

    @http.route(
        '/dynamic_sales_request/product/search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def search_product(self, **kwargs):
        args = request.httprequest.args
        if not self._has_survey_access(args):
            return self._json_response({'results': []}, status=403)

        query = (args.get('q') or '').strip()[:MAX_QUERY_LENGTH]
        Question = request.env['survey.question']
        products = request.env['product.product'].sudo().search(
            Question._get_product_domain(query),
            limit=PRODUCT_SEARCH_LIMIT,
        )
        results = []
        for product in products:
            label = product.display_name
            sku = product.default_code or ''
            uom = ''
            if 'uom_id' in product._fields and product.uom_id:
                uom = product.uom_id.display_name
            detail_parts = []
            if sku and '[%s]' % sku not in label:
                detail_parts.append('SKU: %s' % sku)
            if uom:
                detail_parts.append('UoM: %s' % uom)
            results.append({
                'id': product.id,
                'name': product.name,
                'label': label,
                'value': Question._format_product_answer(product),
                'detail': ' · '.join(detail_parts),
            })
        return self._json_response({'results': results})

    @staticmethod
    def _has_survey_access(args):
        """Customer/product data is sensitive: the caller must hold a valid
        survey/answer token pair, checked with the same logic the core Survey
        applies before accepting a submission."""
        survey_token = args.get('survey_token')
        answer_token = args.get('answer_token')
        if not survey_token or not answer_token:
            return False
        access_data = Survey()._get_access_data(
            survey_token, answer_token, ensure_token=True
        )
        return access_data['validity_code'] is True

    @staticmethod
    def _json_response(payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )