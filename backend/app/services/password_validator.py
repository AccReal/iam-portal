"""Password validator — ported from Java PasswordValidatorService.

100-point scoring system:
- Length:    0-30 points
- Diversity: 0-30 points
- Entropy:   0-25 points
- Patterns:  0 to -15 penalty
- Bonus:     0-15 points
"""

import math
import re
import string

COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "master",
    "dragon", "111111", "baseball", "iloveyou", "trustno1", "sunshine",
    "letmein", "football", "shadow", "superman", "michael", "computer",
    "пароль", "йцукен", "привет", "любовь", "123456789", "password1",
    "qwerty123", "admin", "welcome", "login", "passw0rd",
}

STRENGTH_LABELS = [
    "Очень слабый",
    "Слабый",
    "Средний",
    "Надёжный",
    "Очень надёжный",
]


def validate_password(password: str) -> dict:
    length = len(password)
    has_lower = bool(re.search(r"[a-zа-яё]", password))
    has_upper = bool(re.search(r"[A-ZА-ЯЁ]", password))
    has_digits = bool(re.search(r"\d", password))
    has_special = bool(re.search(r"[^a-zA-Zа-яА-ЯёЁ0-9]", password))

    # Length score (0-30)
    if length >= 16:
        length_score = 30
    elif length >= 12:
        length_score = 25
    elif length >= 8:
        length_score = 15
    elif length >= 6:
        length_score = 10
    else:
        length_score = 5

    # Diversity score (0-30)
    types_count = sum([has_lower, has_upper, has_digits, has_special])
    diversity_score = types_count * 7
    if diversity_score > 30:
        diversity_score = 30

    # Entropy score (0-25)
    charset_size = 0
    if has_lower:
        charset_size += 26
    if has_upper:
        charset_size += 26
    if has_digits:
        charset_size += 10
    if has_special:
        charset_size += 32

    entropy = length * math.log2(charset_size) if charset_size > 0 else 0
    entropy_score = min(25, int(entropy / 4))

    # Pattern penalties (0 to -15)
    penalty = 0
    # Repeating characters
    if re.search(r"(.)\1{2,}", password):
        penalty -= 5
    # Sequential characters (abc, 123)
    for i in range(len(password) - 2):
        if ord(password[i]) + 1 == ord(password[i + 1]) == ord(password[i + 2]) - 1:
            penalty -= 5
            break
    # Common passwords
    if password.lower() in COMMON_PASSWORDS:
        penalty -= 15

    # Bonus (0-15)
    bonus = 0
    if length >= 12 and types_count >= 3:
        bonus += 5
    if length >= 16 and types_count >= 4:
        bonus += 5
    if not re.search(r"(.)\1", password):  # no repeating chars at all
        bonus += 5

    total = max(0, min(100, length_score + diversity_score + entropy_score + penalty + bonus))

    # Strength level
    if total >= 80:
        level = 4
    elif total >= 60:
        level = 3
    elif total >= 40:
        level = 2
    elif total >= 20:
        level = 1
    else:
        level = 0

    # Crack time estimation
    crack_time = _estimate_crack_time(entropy)

    # Feedback
    feedback = []
    if length < 8:
        feedback.append("Увеличьте длину пароля минимум до 8 символов")
    if length < 12:
        feedback.append("Рекомендуемая длина пароля — 12+ символов")
    if not has_upper:
        feedback.append("Добавьте заглавные буквы")
    if not has_lower:
        feedback.append("Добавьте строчные буквы")
    if not has_digits:
        feedback.append("Добавьте цифры")
    if not has_special:
        feedback.append("Добавьте специальные символы (!@#$%)")
    if penalty < 0:
        feedback.append("Избегайте повторяющихся и последовательных символов")
    if password.lower() in COMMON_PASSWORDS:
        feedback.append("Этот пароль входит в список часто используемых")

    return {
        "score": total,
        "strength": STRENGTH_LABELS[level],
        "strength_level": level,
        "feedback": feedback,
        "crack_time": crack_time,
        "length": length,
        "has_uppercase": has_upper,
        "has_lowercase": has_lower,
        "has_digits": has_digits,
        "has_special": has_special,
    }


def _estimate_crack_time(entropy: float) -> str:
    """Estimate brute-force crack time given entropy bits."""
    guesses_per_second = 1e10  # 10 billion (modern GPU)
    total_guesses = 2 ** entropy
    seconds = total_guesses / guesses_per_second

    if seconds < 1:
        return "мгновенно"
    if seconds < 60:
        return f"{int(seconds)} сек."
    if seconds < 3600:
        return f"{int(seconds / 60)} мин."
    if seconds < 86400:
        return f"{int(seconds / 3600)} ч."
    if seconds < 86400 * 365:
        return f"{int(seconds / 86400)} дн."
    if seconds < 86400 * 365 * 1000:
        return f"{int(seconds / (86400 * 365))} лет"
    if seconds < 86400 * 365 * 1e6:
        return f"{int(seconds / (86400 * 365 * 1000))} тыс. лет"
    return "миллионы лет"
