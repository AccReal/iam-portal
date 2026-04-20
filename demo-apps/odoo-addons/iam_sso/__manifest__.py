{
    'name': 'IAM SSO',
    'version': '17.0.1.0.0',
    'summary': 'Single Sign-On через IAM Portal (OAuth2 implicit flow)',
    'category': 'Authentication',
    'depends': ['auth_oauth', 'web'],
    'data': [
        'data/oauth_provider.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
