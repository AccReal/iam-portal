"""HTML email template builders for the three security notification scenarios."""

from datetime import datetime


def _base(title: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f4f6f9; margin: 0; padding: 0; color: #1a1a2e; }}
  .wrap {{ max-width: 560px; margin: 40px auto; background: #ffffff;
           border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08); overflow: hidden; }}
  .header {{ background: #1a1a2e; padding: 24px 32px; }}
  .header h1 {{ color: #e0e0ff; font-size: 18px; margin: 0; letter-spacing: .5px; }}
  .body {{ padding: 32px; }}
  .body h2 {{ margin-top: 0; font-size: 20px; }}
  .meta {{ background: #f0f2f5; border-radius: 6px; padding: 12px 16px;
           font-size: 13px; line-height: 1.8; margin: 20px 0; }}
  .btn {{ display: inline-block; margin-top: 24px; padding: 12px 28px;
          background: #4f46e5; color: #ffffff !important; border-radius: 6px;
          text-decoration: none; font-weight: 600; font-size: 14px; }}
  .warn {{ color: #b91c1c; font-weight: 600; }}
  .footer {{ padding: 16px 32px; font-size: 11px; color: #888; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header"><h1>Единый портал доступа — IAM</h1></div>
  <div class="body">{content}</div>
  <div class="footer">
    Это автоматическое письмо, не отвечайте на него.<br>
    © {datetime.utcnow().year} IAM Portal
  </div>
</div>
</body>
</html>"""


def new_device_email(full_name: str, ip: str, user_agent: str, login_time: str) -> tuple[str, str]:
    """Return (subject, html) for a new-device login alert."""
    subject = "Вход в аккаунт с нового устройства"
    content = f"""
<h2>Обнаружен вход с нового устройства</h2>
<p>Здравствуйте, <strong>{full_name}</strong>!</p>
<p>В ваш аккаунт был выполнен вход с устройства, которое ранее не использовалось.</p>
<div class="meta">
  <strong>IP-адрес:</strong> {ip}<br>
  <strong>Устройство / браузер:</strong> {user_agent or "неизвестно"}<br>
  <strong>Время:</strong> {login_time} UTC
</div>
<p>Если это были вы — ничего делать не нужно.</p>
<p class="warn">Если вы не выполняли этот вход — немедленно смените пароль и обратитесь к администратору.</p>
"""
    return subject, _base(subject, content)


def suspicious_login_email(full_name: str, ip: str, attempts: int, locked_until: str) -> tuple[str, str]:
    """Return (subject, html) for a suspicious-login / account-lockout alert."""
    subject = "Подозрительная активность — аккаунт заблокирован"
    content = f"""
<h2 class="warn">Аккаунт временно заблокирован</h2>
<p>Здравствуйте, <strong>{full_name}</strong>!</p>
<p>Зафиксировано <strong>{attempts} неудачных попытки</strong> входа в ваш аккаунт подряд.</p>
<div class="meta">
  <strong>IP-адрес атакующего:</strong> {ip}<br>
  <strong>Заблокирован до:</strong> {locked_until} UTC
</div>
<p>Ваш аккаунт временно заблокирован в целях безопасности. Через 30 минут блокировка снимется автоматически.</p>
<p class="warn">Если это были не вы — рекомендуем сменить пароль сразу после разблокировки.</p>
"""
    return subject, _base(subject, content)


def password_reset_email(full_name: str, reset_url: str) -> tuple[str, str]:
    """Return (subject, html) for a password-reset request."""
    subject = "Сброс пароля"
    content = f"""
<h2>Запрос на сброс пароля</h2>
<p>Здравствуйте, <strong>{full_name}</strong>!</p>
<p>Мы получили запрос на сброс пароля для вашего аккаунта.
   Нажмите на кнопку ниже, чтобы задать новый пароль.</p>
<a class="btn" href="{reset_url}">Сбросить пароль</a>
<p style="margin-top:24px; font-size:13px; color:#555;">
  Ссылка действительна <strong>1 час</strong>.<br>
  Если вы не запрашивали сброс пароля — просто проигнорируйте это письмо.
</p>
"""
    return subject, _base(subject, content)


def password_changed_email(full_name: str, changed_at: str) -> tuple[str, str]:
    """Return (subject, html) confirming a successful password change."""
    subject = "Пароль успешно изменён"
    content = f"""
<h2>Пароль изменён</h2>
<p>Здравствуйте, <strong>{full_name}</strong>!</p>
<p>Пароль вашего аккаунта был успешно изменён.</p>
<div class="meta">
  <strong>Время изменения:</strong> {changed_at} UTC
</div>
<p class="warn">Если вы не меняли пароль — немедленно обратитесь к администратору.</p>
"""
    return subject, _base(subject, content)
