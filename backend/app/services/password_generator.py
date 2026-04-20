"""Password generator — ported from Java PasswordGeneratorService."""

import secrets
import string


LOWERCASE = string.ascii_lowercase
UPPERCASE = string.ascii_uppercase
DIGITS = string.digits
SPECIAL = "!@#$%^&*()_+-=[]{}|;:,.<>?"
SIMILAR = "il1Lo0O"
AMBIGUOUS = "{}[]()/\\'\"`~,;:.<>"


def generate_password(
    length: int = 16,
    include_uppercase: bool = True,
    include_digits: bool = True,
    include_special: bool = True,
    exclude_similar: bool = False,
    exclude_ambiguous: bool = False,
) -> str:
    """Generate a cryptographically secure password."""
    charset = LOWERCASE
    required = [secrets.choice(LOWERCASE)]

    if include_uppercase:
        charset += UPPERCASE
        required.append(secrets.choice(UPPERCASE))
    if include_digits:
        charset += DIGITS
        required.append(secrets.choice(DIGITS))
    if include_special:
        charset += SPECIAL
        required.append(secrets.choice(SPECIAL))

    if exclude_similar:
        charset = "".join(c for c in charset if c not in SIMILAR)
        required = [c for c in required if c not in SIMILAR]
    if exclude_ambiguous:
        charset = "".join(c for c in charset if c not in AMBIGUOUS)
        required = [c for c in required if c not in AMBIGUOUS]

    if not charset:
        charset = LOWERCASE

    # Fill remaining length
    remaining = length - len(required)
    if remaining < 0:
        required = required[:length]
        remaining = 0

    password_chars = required + [secrets.choice(charset) for _ in range(remaining)]

    # Shuffle using Fisher-Yates
    for i in range(len(password_chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password_chars[i], password_chars[j] = password_chars[j], password_chars[i]

    return "".join(password_chars)


def generate_batch(count: int = 1, **kwargs) -> list[str]:
    return [generate_password(**kwargs) for _ in range(count)]
