from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
import json


class UserIntegrationController(http.Controller):

    @http.route('/api/create_portal_user', type='json', auth='public', methods=['POST'], csrf=False)
    def create_portal_user(self, **kwargs):
        """
        Create a new portal user in Odoo.
        :param kwargs: Dictionary containing the user details.
        :return: JSON response with the created user's ID or an error message.
        """
        response = {}

        try:
            data = json.loads(request.httprequest.data)
            username = data.get('username')
            password = data.get('password')
            email = data.get('email')

            if not username or not password or not email:
                return {'status': 'False', 'statusCode': 400, 'message': 'Missing required fields'}
            
            existing_user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
            if existing_user:
                return {'status': 'False', 'statusCode': 400, 'message': 'User already exists'}

            new_user = request.env['res.users'].sudo().create({
                'name': username,
                'login': email,
                'email': email,
                'password': password,
                'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])],  # Assign to portal group
            })

            response.update({
                'status': True,
                'statusCode': 200,
                'message': ("User created successfully"),
                'user_id': new_user.id,
            })

            return response

        except Exception as e:
            response.update({
                'status': False,
                'statusCode': 400,
                'message': str(e),
            })
            return response
