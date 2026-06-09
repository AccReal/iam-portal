import urllib.parse

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.http import Response, request

# HTML bridge page: reads the OAuth2 implicit-flow token from the URL fragment
# (which servers never see) and redirects to Odoo's auth_oauth/signin endpoint.
_SSO_CALLBACK_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>IAM SSO</title></head>
<body>
<p style="font-family:sans-serif;color:#666;padding:2em">Выполняется авторизация через IAM Portal…</p>
<script>
(function () {
    var hash = window.location.hash.substring(1);
    if (!hash) {
        window.location.href = '/web/login?oauth_error=1';
        return;
    }
    // GET redirect — no CSRF token needed, Odoo auth_oauth/signin accepts GET
    window.location.href = '/auth_oauth/signin?' + hash;
})();
</script>
</body></html>"""


class IamSsoController(Home):
    """SSO integration with IAM Portal.

    Flow (implicit / access_token):
      1. /web/login — shows standard Odoo login page with OAuth button.
      2. User clicks "Войти через IAM Portal" → IAM OAuth authorize.
      3. IAM sees refresh_token cookie → auto-approves → redirects to
         /iam/sso/callback#access_token=TOKEN&state=...
      4. /iam/sso/callback — serves HTML+JS that reads the fragment and
         redirects to Odoo's /auth_oauth/signin.
      5. Odoo calls IAM userinfo, finds/creates user, creates session.
    """

    @http.route('/web/login', type='http', auth='none', website=False, sitemap=False)
    def web_login(self, redirect=None, **kw):
        # If already authenticated in Odoo, log out first so the SSO button
        # is always visible. This allows switching between IAM Portal accounts.
        if request.session.uid:
            request.session.logout(keep_db=True)

        # Always show the standard login page with the "Войти через IAM Portal" button.
        return super().web_login(redirect=redirect, **kw)

    @http.route('/iam/sso/callback', type='http', auth='none', website=False, sitemap=False)
    def iam_sso_callback(self, **kw):
        """Bridge: IAM redirects here with token in URL fragment (#).
        Serves JavaScript that reads the fragment and redirects to
        /auth_oauth/signin so the server can process the token.
        """
        return Response(_SSO_CALLBACK_HTML, mimetype='text/html')
