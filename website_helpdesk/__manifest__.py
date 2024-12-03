# Part of odoo See LICENSE file for full copyright and licensing details.

{
    'name': 'Website Helpdesk',
    'version': '1.0',
    'summary': '''Website Helpdesk''',
    'category': 'Human Resources',
    'author': 'OdooHQ',
    'website': 'www.odoo.com',
    # 'depends': ['helpdesk_basic', 'website', 'portal', 'rating'],
    'depends': ['helpdesk_basic', 'portal', 'rating', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/pages/helpdesk_register_website_view.xml',
        'views/pages/helpdesk_website_view.xml',
        'views/views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_helpdesk/static/src/css/helpdesk_attachment.css',
            'website_helpdesk/static/src/js/helpdesk.js'
        ],
    },
    'installable': True,
    'auto_install': False,
}
