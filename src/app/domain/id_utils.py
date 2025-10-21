from __future__ import annotations

import random
import re
import string
from typing import Final


POSTAL_ID_PATTERN_TEMPLATE: Final[str] = r"^{prefix}[A-Z]\d[A-Z]\d[A-Z]\d$"


def _postal_regex(prefix: str) -> re.Pattern[str]:
    pattern = POSTAL_ID_PATTERN_TEMPLATE.format(prefix=re.escape(prefix))
    return re.compile(pattern)


def validate_postal_id(value: str, prefix: str = "QUES") -> bool:
    if not value:
        return False
    matcher = _postal_regex(prefix)
    return bool(matcher.fullmatch(value))


def generate_postal_id(prefix: str = "QUES") -> str:
    letters = string.ascii_uppercase
    digits = string.digits
    rng = random.SystemRandom()
    body_chars = []
    for idx in range(6):
        if idx % 2 == 0:
            body_chars.append(rng.choice(letters))
        else:
            body_chars.append(rng.choice(digits))
    return f"{prefix}{''.join(body_chars)}"
