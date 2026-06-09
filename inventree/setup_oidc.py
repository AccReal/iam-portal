"""
One-shot script: configure OIDC social app in InvenTree and link IAM users.
Run via: python manage.py shell < setup_oidc.py
"""
from allauth.socialaccount.models import SocialApp, SocialAccount
from django.contrib.auth.models import User

PROVIDER = "openid_connect"
PROVIDER_ID = "iam-portal"   # Used in the callback URL: /accounts/iam-portal/login/callback/
NAME = "IAM Portal"
CLIENT_ID = "inventree"
SECRET = "InvenTreeSecret2024"
SERVER_URL = "http://backend:8000"

# IAM user UUID -> email mapping (must match IAM DB)
IAM_USERS = [
    ("30000000-0000-0000-0000-000000000001", "admin@company.ru"),
    ("30000000-0000-0000-0000-000000000002", "marina@company.ru"),
    ("30000000-0000-0000-0000-000000000003", "petr@company.ru"),
    ("30000000-0000-0000-0000-000000000004", "olga@company.ru"),
]

existing = SocialApp.objects.filter(provider=PROVIDER, name=NAME).first()
if existing:
    existing.client_id = CLIENT_ID
    existing.secret = SECRET
    existing.provider_id = PROVIDER_ID
    existing.settings = {"server_url": SERVER_URL, "token_auth_method": "client_secret_post"}
    existing.save()
    print(f"[InvenTree OIDC] Updated existing SocialApp: {NAME} (provider_id={PROVIDER_ID})")
else:
    app = SocialApp.objects.create(
        provider=PROVIDER,
        provider_id=PROVIDER_ID,
        name=NAME,
        client_id=CLIENT_ID,
        secret=SECRET,
        settings={"server_url": SERVER_URL, "token_auth_method": "client_secret_post"},
    )
    try:
        from django.contrib.sites.models import Site
        site, _ = Site.objects.get_or_create(id=1, defaults={"domain": "localhost:8092", "name": "InvenTree"})
        app.sites.add(site)
        print(f"[InvenTree OIDC] Linked to site: {site.domain}")
    except Exception as e:
        print(f"[InvenTree OIDC] Sites framework skipped: {e}")
    print(f"[InvenTree OIDC] Created SocialApp: {NAME}")
    print(f"[InvenTree OIDC] Redirect URI: http://localhost:8092/accounts/iam-portal/login/callback/")

# Link existing InvenTree users to IAM Portal via SocialAccount records.
# This prevents allauth from trying to create new users (which is blocked).
for uid, email in IAM_USERS:
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Create the user if missing
        username = email.split("@")[0]
        user = User.objects.create_user(username=username, email=email, password=None)
        user.set_unusable_password()
        user.save()
        print(f"[InvenTree OIDC] Created InvenTree user: {email}")

    if not SocialAccount.objects.filter(provider=PROVIDER_ID, uid=uid).exists():
        SocialAccount.objects.create(
            user=user,
            provider=PROVIDER_ID,
            uid=uid,
            extra_data={"sub": uid, "email": email},
        )
        print(f"[InvenTree OIDC] Linked SocialAccount: {email} -> {uid}")
    else:
        print(f"[InvenTree OIDC] SocialAccount already linked: {email}")
