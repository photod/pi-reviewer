#!/usr/bin/env python3
"""pi-mask — best-effort redaction of high-value secrets before review.

Rules are selected from JSON configuration before text is scanned. An opt-in
group therefore does no regex work unless it is enabled. See
``pi-mask.config.example.json`` for the complete valid JSON schema.
"""
import json
import math
import os
import re
import sys
from datetime import date


DEFAULT_GROUPS = {
    "llm-keys": True, "cloud-keys": True, "regional-cloud": False,
    "git-tokens": True, "private-keys": True, "db-uris": True,
    "payments": True, "monitoring": False, "messaging": False,
    "registrars-hosting": False, "regional-services": False,
    "generic-entropy": False,
}
NATIONAL_ID_COUNTRIES = (
    "US", "PAN", "CA", "GB", "DE", "FR", "ES", "IT", "PL", "NL", "EU-IBAN",
    "RU", "KZ", "IN", "JP", "SG", "TH", "ID", "MY", "BR", "AR", "CL",
    "MX", "CO", "PE", "UY", "VE",
)


def default_config():
    return {"groups": dict(DEFAULT_GROUPS), "national_ids": {c: False for c in NATIONAL_ID_COUNTRIES}}


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(config_path=None, cwd=None):
    """Load JSON config; search explicit path, cwd, then repository root."""
    cwd = os.path.abspath(cwd or os.getcwd())
    if config_path:
        paths = [config_path]
    else:
        paths = [os.path.join(cwd, "pi-mask.config.json")]
        root_path = os.path.join(_repo_root(), "pi-mask.config.json")
        if os.path.abspath(paths[0]) != root_path:
            paths.append(root_path)
    chosen = next((path for path in paths if os.path.isfile(path)), None)
    config = default_config()
    if chosen is None:
        if config_path:
            raise OSError("config file not found: " + config_path)
        return config
    with open(chosen, "r", encoding="utf-8") as f:
        supplied = json.load(f)
    if not isinstance(supplied, dict):
        raise ValueError("config must be a JSON object")
    for section in ("groups", "national_ids"):
        values = supplied.get(section, {})
        if not isinstance(values, dict):
            raise ValueError(section + " must be a JSON object")
        for name, enabled in values.items():
            if name in config[section]:
                if not isinstance(enabled, bool):
                    raise ValueError(section + "." + name + " must be true or false")
                config[section][name] = enabled
    return config


def _rx(pattern, flags=0):
    return re.compile(pattern, flags)


def _gate(pattern):
    return re.compile(pattern, re.IGNORECASE)


def luhn(digits):
    """Return whether digits has a valid Luhn check digit."""
    values = [int(char) for char in digits if char.isdigit()]
    if not values:
        return False
    total = 0
    parity = len(values) % 2
    for index, value in enumerate(values):
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff(digits):
    """Validate digits with the canonical Verhoeff D5 tables."""
    if not digits or not digits.isdigit():
        return False
    checksum = 0
    for index, char in enumerate(reversed(digits)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[index % 8][int(char)]]
    return _VERHOEFF_INV[checksum] == 0


def mod11_weighted(digits, weights, modulus=11):
    """Return the weighted remainder used by country-specific mod-11 rules."""
    if len(digits) != len(weights) or not digits.isdigit():
        raise ValueError("digits and weights must have equal lengths")
    return sum(int(char) * weight for char, weight in zip(digits, weights)) % modulus


def mod97(value):
    """Validate an IBAN-like string with ISO 7064 MOD 97-10."""
    compact = re.sub(r"\s+", "", value).upper()
    if len(compact) < 5 or re.fullmatch(r"[A-Z0-9]+", compact) is None:
        return False
    rearranged = compact[4:] + compact[:4]
    remainder = 0
    for char in rearranged:
        expansion = char if char.isdigit() else str(ord(char) - ord("A") + 10)
        for digit in expansion:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder == 1


def _digits(value):
    return "".join(char for char in value if char.isdigit())


def _valid_aba(value):
    digits = _digits(value)
    return len(digits) == 9 and (
        3 * sum(int(digits[i]) for i in (0, 3, 6))
        + 7 * sum(int(digits[i]) for i in (1, 4, 7))
        + sum(int(digits[i]) for i in (2, 5, 8))
    ) % 10 == 0


def _valid_npi(value):
    digits = _digits(value)
    return len(digits) == 10 and luhn("80840" + digits)


def _valid_steuer_id(value):
    digits = _digits(value)
    if len(digits) != 11:
        return False
    counts = sorted(digits[:10].count(str(number)) for number in range(10))
    if counts != [0] + [1] * 8 + [2]:
        return False
    product = 10
    for char in digits[:10]:
        intermediate = (int(char) + product) % 10
        if intermediate == 0:
            intermediate = 10
        product = (2 * intermediate) % 11
    return (11 - product) % 10 == int(digits[-1])


def _valid_nir(value):
    digits = _digits(value)
    return len(digits) == 15 and 97 - (int(digits[:13]) % 97) == int(digits[13:])


_DNI_TABLE = "TRWAGMYFPDXBNJZSQVHLCKE"


def _valid_dni(value):
    value = value.upper()
    return len(value) == 9 and value[:8].isdigit() and _DNI_TABLE[int(value[:8]) % 23] == value[-1]


def _valid_nie(value):
    value = value.upper()
    if len(value) != 9 or value[0] not in "XYZ" or not value[1:8].isdigit():
        return False
    number = "XYZ".index(value[0]) * 10_000_000 + int(value[1:8])
    return _DNI_TABLE[number % 23] == value[-1]


_CF_ODD = {
    **dict(zip("0123456789", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21))),
    **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23))),
}


def _valid_codice_fiscale(value):
    value = value.upper()
    if len(value) != 16 or any(char not in _CF_ODD for char in value[:15]):
        return False
    total = 0
    for index, char in enumerate(value[:15]):
        total += _CF_ODD[char] if index % 2 == 0 else (int(char) if char.isdigit() else ord(char) - ord("A"))
    return chr(ord("A") + total % 26) == value[-1]


def _valid_pesel(value):
    digits = _digits(value)
    if len(digits) != 11:
        return False
    year, encoded_month, day = int(digits[:2]), int(digits[2:4]), int(digits[4:6])
    century_months = ((80, 1800), (0, 1900), (20, 2000), (40, 2100), (60, 2200))
    try:
        offset, century = next((offset, century) for offset, century in century_months if 1 <= encoded_month - offset <= 12)
        date(century + year, encoded_month - offset, day)
    except (StopIteration, ValueError):
        return False
    remainder = mod11_weighted(digits[:10], (1, 3, 7, 9, 1, 3, 7, 9, 1, 3), modulus=10)
    return (10 - remainder) % 10 == int(digits[-1])


def _valid_bsn(value):
    digits = _digits(value).zfill(9)
    return len(digits) == 9 and int(digits) != 0 and mod11_weighted(digits, (9, 8, 7, 6, 5, 4, 3, 2, -1)) == 0


_IBAN_LENGTHS = {
    "AL": 28, "AD": 24, "AT": 20, "AZ": 28, "BH": 22, "BE": 16, "BA": 20,
    "BR": 29, "BG": 22, "CR": 22, "HR": 21, "CY": 28, "CZ": 24, "DK": 18,
    "DO": 28, "EE": 20, "FO": 18, "FI": 18, "FR": 27, "GE": 22, "DE": 22,
    "GI": 23, "GR": 27, "GL": 18, "GT": 28, "HU": 28, "IS": 26, "IE": 22,
    "IL": 23, "IT": 27, "JO": 30, "KZ": 20, "XK": 20, "KW": 30, "LV": 21,
    "LB": 28, "LI": 21, "LT": 20, "LU": 20, "MT": 31, "MR": 27, "MU": 30,
    "MC": 27, "MD": 24, "ME": 22, "NL": 18, "MK": 19, "NO": 15, "PK": 24,
    "PS": 29, "PL": 28, "PT": 25, "QA": 29, "RO": 24, "LC": 32, "SM": 27,
    "ST": 25, "SA": 24, "RS": 22, "SC": 31, "SK": 24, "SI": 19, "ES": 24,
    "SE": 24, "CH": 21, "TL": 23, "TN": 24, "TR": 26, "UA": 29, "AE": 23,
    "GB": 22, "VA": 22, "VG": 24,
}


def _valid_iban(value):
    value = value.replace(" ", "").upper()
    return _IBAN_LENGTHS.get(value[:2]) == len(value) and mod97(value)


def _br_check_digit(base, weights):
    remainder = sum((ord(char) - 48) * weight for char, weight in zip(base, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def _valid_cpf(value):
    digits = _digits(value)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    first = _br_check_digit(digits[:9], tuple(range(10, 1, -1)))
    second = _br_check_digit(digits[:9] + str(first), tuple(range(11, 1, -1)))
    return digits[-2:] == str(first) + str(second)


def _valid_cnpj(value):
    compact = re.sub(r"[.\-/]", "", value.upper())
    if len(compact) != 14 or not compact[:12].isalnum() or not compact[-2:].isdigit() or len(set(compact[:12])) == 1:
        return False
    first = _br_check_digit(compact[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = _br_check_digit(compact[:12] + str(first), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return compact[-2:] == str(first) + str(second)


def validate_curp(value):
    """Validate the RENAPO mod-10 check digit (used by the phase-3b MX rule)."""
    alphabet = "0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"
    value = value.upper()
    return len(value) == 18 and value[-1].isdigit() and all(char in alphabet for char in value[:17]) and (
        10 - sum(alphabet.index(char) * (18 - index) for index, char in enumerate(value[:17])) % 10
    ) % 10 == int(value[-1])


def validate_rfc(value):
    """Validate the SAT mod-11 check character (used by the phase-3b MX rule)."""
    values = {char: index for index, char in enumerate("0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ Ñ")}
    value = value.upper()
    if len(value) not in (12, 13) or any(char not in values for char in value[:-1]):
        return False
    base = value[:-1].rjust(12)
    remainder = sum(values[char] * weight for char, weight in zip(base, range(13, 1, -1))) % 11
    expected = 11 - remainder
    expected_char = "0" if expected == 11 else "A" if expected == 10 else str(expected)
    return value[-1] == expected_char


def validate_jp_corp_number(value):
    """Validate the Japanese corporate-number mod-9 leading check digit."""
    if len(value) != 13 or not value.isdigit():
        return False
    base = value[1:]
    total = sum(int(char) * (1 if index % 2 == 0 else 2) for index, char in enumerate(reversed(base)))
    return int(value[0]) == 9 - total % 9


def _valid_inn10(value):
    digits = _digits(value)
    return len(digits) == 10 and mod11_weighted(digits[:9], (2, 4, 10, 3, 5, 9, 4, 6, 8)) % 10 == int(digits[-1])


def _valid_inn12(value):
    digits = _digits(value)
    if len(digits) != 12:
        return False
    check11 = mod11_weighted(digits[:10], (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)) % 10
    check12 = mod11_weighted(digits[:11], (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)) % 10
    return int(digits[10]) == check11 and int(digits[11]) == check12


def _valid_snils(value):
    digits = _digits(value)
    if len(digits) != 11:
        return False
    total = sum(int(char) * weight for char, weight in zip(digits[:9], range(9, 0, -1)))
    if total < 100:
        check = total
    elif total in (100, 101):
        check = 0
    else:
        check = total % 101
        if check == 100:
            check = 0
    return int(digits[-2:]) == check


def _valid_ogrn(value):
    digits = _digits(value)
    return len(digits) == 13 and int(digits[:12]) % 11 % 10 == int(digits[-1])


def _valid_ogrnip(value):
    digits = _digits(value)
    return len(digits) == 15 and int(digits[:14]) % 13 % 10 == int(digits[-1])


def _kz_check_digit(base):
    remainder = mod11_weighted(base, tuple(range(1, 12)))
    if remainder == 10:
        remainder = mod11_weighted(base, (3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2))
    return None if remainder == 10 else remainder


def _valid_iin(value):
    digits = _digits(value)
    if len(digits) != 12:
        return False
    century_code = int(digits[6])
    if century_code not in range(1, 7):
        return False
    century = {1: 1800, 2: 1800, 3: 1900, 4: 1900, 5: 2000, 6: 2000}[century_code]
    try:
        date(century + int(digits[:2]), int(digits[2:4]), int(digits[4:6]))
    except ValueError:
        return False
    return _kz_check_digit(digits[:11]) == int(digits[-1])


def _valid_bin(value):
    digits = _digits(value)
    return (
        len(digits) == 12 and 1 <= int(digits[2:4]) <= 12
        and _kz_check_digit(digits[:11]) == int(digits[-1])
    )


def _valid_mynumber(value):
    digits = _digits(value)
    if len(digits) != 12:
        return False
    remainder = mod11_weighted(digits[:11], (6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2))
    check = 11 - remainder
    if check >= 10:
        check = 0
    return int(digits[-1]) == check


def _valid_aadhaar(value):
    return verhoeff(_digits(value))


def _valid_nric(value):
    value = value.upper()
    if len(value) != 9 or value[0] not in "STFG" or not value[1:8].isdigit():
        return False
    total = sum(int(char) * weight for char, weight in zip(value[1:8], (2, 7, 6, 5, 4, 3, 2)))
    if value[0] in "TG":
        total += 4
    tables = {"S": "JZIHGFEDCBA", "T": "GFJZIHEDCBA", "F": "XWUTRQPNMLK", "G": "RQPWUTMLKJ"}
    return value[-1] == tables[value[0]][total % 11]


def _valid_nik(value):
    digits = _digits(value)
    if len(digits) != 16 or "00" in (digits[:2], digits[2:4], digits[4:6]):
        return False
    day, month, year = int(digits[6:8]), int(digits[8:10]), int(digits[10:12])
    if day > 40:
        day -= 40
    try:
        date(2000 + year if year <= date.today().year % 100 else 1900 + year, month, day)
    except ValueError:
        return False
    return True


def _valid_thai_id(value):
    digits = _digits(value)
    if len(digits) != 13:
        return False
    total = sum(int(digits[index]) * (13 - index) for index in range(12))
    return (11 - total % 11) % 10 == int(digits[-1])


def _valid_mykad(value):
    digits = _digits(value)
    if len(digits) != 12 or digits[6:8] == "00":
        return False
    year, month, day = int(digits[:2]), int(digits[2:4]), int(digits[4:6])
    try:
        date(2000 + year if year <= date.today().year % 100 else 1900 + year, month, day)
    except ValueError:
        return False
    return True


def _valid_cuit(value):
    digits = _digits(value)
    if len(digits) != 11:
        return False
    remainder = mod11_weighted(digits[:10], (5, 4, 3, 2, 7, 6, 5, 4, 3, 2))
    check = 11 - remainder
    if check == 11:
        check = 0
    elif check == 10:
        check = 9
    return int(digits[-1]) == check


def _valid_rut(value):
    compact = re.sub(r"[.\-]", "", value.upper())
    if len(compact) < 2 or not compact[:-1].isdigit():
        return False
    total = sum(int(char) * (2 + index % 6) for index, char in enumerate(reversed(compact[:-1])))
    check = 11 - total % 11
    expected = "0" if check == 11 else "K" if check == 10 else str(check)
    return compact[-1] == expected


def _valid_ci_uy(value):
    """Validate Uruguay CI's mod-10 check digit after left-padding to 8 digits."""
    digits = _digits(value)
    if not 7 <= len(digits) <= 8:
        return False
    digits = digits.zfill(8)
    total = sum(int(char) * weight for char, weight in zip(digits[:7], (2, 9, 8, 7, 6, 3, 4)))
    return (-total) % 10 == int(digits[-1])


def _valid_card_pan(value):
    digits = _digits(value)
    if len(digits) not in range(13, 20) or len(set(digits)) == 1 or not luhn(digits):
        return False
    length = len(digits)
    first2, first4, first6 = int(digits[:2]), int(digits[:4]), int(digits[:6])
    return any((
        digits[0] == "4" and length in (13, 16, 19),
        (51 <= first2 <= 55 or 2221 <= first4 <= 2720) and length == 16,
        first2 in (34, 37) and length == 15,
        (digits.startswith("6011") or first2 == 65 or 644 <= int(digits[:3]) <= 649 or 622126 <= first6 <= 622925) and length in (16, 19),
        3528 <= first4 <= 3589 and 16 <= length <= 19,
        (300 <= int(digits[:3]) <= 305 or first2 in (36, 38, 39)) and length == 14,
        digits.startswith("62") and 16 <= length <= 19,
    ))


def _national(validator=None, keywords=None, keyword_mode=None):
    return validator, _gate(keywords) if keywords else None, keyword_mode


# Rule tuple: name, group (or enabled-group tuple), country, regex, kind, optional same-line keyword gate.
# Prefix/db/block rules expose retained prefix as group 1 and secret body as group 2.
RULES = [
    # llm-keys
    ("openai", "llm-keys", None, _rx(r"(sk-(?:proj|svcacct|admin)-)([A-Za-z0-9_-]{40,200}T3BlbkFJ[A-Za-z0-9_-]{40,200})"), "prefix", None),
    ("openai-legacy", "llm-keys", None, _rx(r"(sk-)([A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20})"), "prefix", None),
    ("anthropic", "llm-keys", None, _rx(r"(sk-ant-(?:api03|admin01)-)([A-Za-z0-9_-]{93}AA)"), "prefix", None),
    ("google-ai", "llm-keys", None, _rx(r"(AIza)([A-Za-z0-9_-]{35})"), "prefix", None),
    ("openrouter", "llm-keys", None, _rx(r"(sk-or-v1-)([a-f0-9]{64})"), "prefix", None),
    ("kimi-coding", "llm-keys", None, _rx(r"(sk-kimi-)([A-Za-z0-9]{20,})"), "prefix", None),
    ("minimax", "llm-keys", None, _rx(r"(sk-cp-)([A-Za-z0-9._-]{80,200})"), "prefix", None),
    ("huggingface", "llm-keys", None, _rx(r"(hf_)([A-Za-z0-9]{34})"), "prefix", None),
    ("groq", "llm-keys", None, _rx(r"(gsk_)([A-Za-z0-9]{52})"), "prefix", None),
    ("replicate", "llm-keys", None, _rx(r"(r8_)([A-Za-z0-9]{37})"), "prefix", None),
    # cloud-keys
    ("aws-akid", "cloud-keys", None, _rx(r"((?:AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9]))([A-Z2-7]{16})"), "prefix", None),
    ("gcp-oauth", "cloud-keys", None, _rx(r"(GOCSPX-)([A-Za-z0-9_-]{28})"), "prefix", None),
    ("azure-storage", "cloud-keys", None, _rx(r"(AccountKey=)([A-Za-z0-9+/]{86}==)"), "prefix", None),
    # regional-cloud
    ("yandex-apikey", "regional-cloud", None, _rx(r"(AQVN)([A-Za-z0-9_-]{35,38})"), "prefix", None),
    ("yandex-iam", "regional-cloud", None, _rx(r"(t1\.)([A-Za-z0-9_-]+=*\.[A-Za-z0-9_-]{86}=*)"), "prefix", None),
    ("yandex-static", "regional-cloud", None, _rx(r"(YC)([A-Za-z0-9_-]{38})"), "prefix", None),
    ("yandex-oauth", "regional-services", None, _rx(r"(y0_)([A-Za-z0-9_-]{35,60})"), "prefix", None),
    ("alibaba-akid", "regional-cloud", None, _rx(r"(LTAI)([A-Za-z0-9]{20})"), "prefix", None),
    ("tencent-secretid", "regional-cloud", None, _rx(r"(AKID)([A-Za-z0-9]{13,32})"), "prefix", None),
    ("scaleway-akey", "regional-cloud", None, _rx(r"(SCW)([A-Z0-9]{17})"), "prefix", None),
    ("exoscale", "regional-cloud", None, _rx(r"(EXO)([A-Za-z0-9]{20,32})"), "prefix", None),
    ("digitalocean", "regional-cloud", None, _rx(r"(do[pour]_v1_)([a-f0-9]{64})"), "prefix", None),
    # git-tokens
    ("github-pat", "git-tokens", None, _rx(r"(gh[posur]_)([0-9A-Za-z]{36})"), "prefix", None),
    ("github-fine", "git-tokens", None, _rx(r"(github_pat_)(\w{82})"), "prefix", None),
    ("gitlab", "git-tokens", None, _rx(r"(gl(?:pat|dt)-)([\w-]{20,50})"), "prefix", None),
    # registrars-hosting
    ("porkbun", "registrars-hosting", None, _rx(r"((?:pk1|sk1)_)([0-9a-z]{58,64})"), "prefix", None),
    ("cloudflare-token", "registrars-hosting", None, _rx(r"(cf(?:ut|at)_)([A-Za-z0-9_-]{40,45})"), "prefix", None),
    ("cloudflare-key", "registrars-hosting", None, _rx(r"(cfk_)([A-Za-z0-9]{40,45})"), "prefix", None),
    ("netlify", "registrars-hosting", None, _rx(r"(nf[pcoub]_)([A-Za-z0-9_-]{36})"), "prefix", None),
    ("vercel", "registrars-hosting", None, _rx(r"(vcp_)([A-Za-z0-9]{20,40})"), "prefix", None),
    ("ionos", "registrars-hosting", None, _rx(r"([0-9a-f]{32})(\.[A-Za-z0-9_-]{80,90})"), "prefix", None),
    ("godaddy", "registrars-hosting", None, _rx(r"(sso-key )([A-Za-z0-9_]{10,30}:[A-Za-z0-9_]{10,50})"), "prefix", None),
    # payments
    ("stripe", "payments", None, _rx(r"((?:sk|rk)_(?:live|test|prod)_)([A-Za-z0-9]{10,99})"), "prefix", None),
    ("stripe-whsec", "payments", None, _rx(r"(whsec_)([A-Za-z0-9]{32,64})"), "prefix", None),
    ("square", "payments", None, _rx(r"(sq0atp-)([A-Za-z0-9_-]{22,60})"), "prefix", None),
    ("square", "payments", None, _rx(r"(EAAA)([A-Za-z0-9_-]{22,60})"), "prefix", _gate(r"\bsquare\b")),
    ("braintree", "payments", None, _rx(r"(access_token\$(?:production|sandbox)\$)([a-f0-9]{16}\$[a-f0-9]{32})"), "prefix", None),
    ("mollie", "payments", None, _rx(r"((?:test|live)_)([A-Za-z0-9]{30,31})"), "prefix", _gate(r"mollie")),
    ("toss", "payments", None, _rx(r"((?:test|live)_g?sk_)([A-Za-z0-9]{20,40})"), "prefix", None),
    ("razorpay", "payments", None, _rx(r"(rzp_(?:test|live)_)([A-Za-z0-9]{14})"), "prefix", None),
    ("yookassa", ("payments", "regional-services"), None, _rx(r"((?:live|test)_)([A-Za-z0-9]{20,50})"), "prefix", _gate(r"(?:yookassa|shopId)")),
    ("plaid", "payments", None, _rx(r"(access-(?:sandbox|development|production)-)([0-9a-f-]{36})"), "prefix", None),
    ("shopify", "payments", None, _rx(r"(shp(?:at|ss|ca|pa)_)([a-fA-F0-9]{32,64})"), "prefix", None),
    # monitoring
    ("sentry-dsn", "monitoring", None, _rx(r"(https?://[a-f0-9]{32}(?::[a-f0-9]{32})?@(?:o\d+\.)?ingest(?:\.[a-z]+)?\.sentry\.io/)(\d+)"), "prefix", None),
    ("sentry-token", "monitoring", None, _rx(r"(sntry[us]_)([A-Za-z0-9+/=_-]{40,})"), "prefix", None),
    ("grafana-sa", "monitoring", None, _rx(r"(glsa_)([A-Za-z0-9]{32}_[A-Fa-f0-9]{8})"), "prefix", None),
    ("grafana-cloud", "monitoring", None, _rx(r"(glc_)(eyJ[A-Za-z0-9+/=]{32,})"), "prefix", None),
    ("newrelic-user", "monitoring", None, _rx(r"(NRAK-)([A-Z0-9]{27})"), "prefix", None),
    ("newrelic-ingest", "monitoring", None, _rx(r"(NRII-)([a-z0-9-]{32})"), "prefix", None),
    ("datadog", "monitoring", None, _rx(r"(?i)(\bdd_api_key\s*[:=]\s*['\"]?)([a-f0-9]{32})"), "prefix", None),
    ("mailgun", "monitoring", None, _rx(r"(key-)([a-f0-9]{32})"), "prefix", None),
    ("mailchimp", "monitoring", None, _rx(r"([0-9a-f]{32})(-us\d{1,2})"), "prefix", None),
    ("circleci", "monitoring", None, _rx(r"(?i)(\bcircle_token\s*[:=]\s*['\"]?)([a-f0-9]{40})"), "prefix", None),
    # messaging
    ("twilio-sid", "messaging", None, _rx(r"(AC)([0-9a-fA-F]{32})"), "prefix", _gate(r"(?:twilio|sid)")),
    ("twilio-apikey", "messaging", None, _rx(r"(SK)([0-9a-fA-F]{32})"), "prefix", _gate(r"(?:twilio|api[_ -]?key)")),
    ("telegram-bot", "messaging", None, _rx(r"(\d{8,10}:AA)([0-9A-Za-z_-]{33})"), "prefix", None),
    ("discord-bot", "messaging", None, _rx(r"([MN][A-Za-z0-9_-]{23,25}\.[\w-]{6}\.)([\w-]{27,38})"), "prefix", None),
    ("slack-bot", "messaging", None, _rx(r"(xoxb-)([0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9-]{24,34})"), "prefix", None),
    ("slack-user", "messaging", None, _rx(r"(xox[pe]-)((?:[0-9]{10,13}-){2,3}[a-zA-Z0-9-]{28,34})"), "prefix", None),
    ("slack-app", "messaging", None, _rx(r"(xapp-)(\d-[A-Z0-9]+-\d+-[0-9a-f]{40,80})"), "prefix", None),
    ("slack-webhook", "messaging", None, _rx(r"(hooks\.slack\.com/(?:services|workflows|triggers)/)([A-Za-z0-9+/]{43,56})"), "prefix", None),
    ("sendgrid", "messaging", None, _rx(r"(SG\.)([A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})"), "prefix", None),
    ("npm", "messaging", None, _rx(r"(npm_)([0-9A-Za-z]{36})"), "prefix", None),
    ("pypi", "messaging", None, _rx(r"(pypi-AgEIcHlwaS5vcmc)([A-Za-z0-9_-]{50,1000})"), "prefix", None),
    # db-uris
    ("db-uri-creds", "db-uris", None, _rx(r"((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:\s\"']+:)([^\s\"'/]+)(@)"), "db", None),
    ("basic-auth-url", "db-uris", None, _rx(r"([a-z][a-z0-9+.-]*://[^:\s\"'/]+:)([^\s\"'/]+)(@)", re.IGNORECASE), "db", None),
    # private-key blocks; line separators sit outside group 2 so formatting is kept.
    ("gcp-sa-json", "private-keys", None, _rx(r"(\"private_key\"\s*:\s*\"-----BEGIN[^\"]*PRIVATE KEY-----(?:\\n|\r?\n))([\s\S]+?)((?:\\n|\r?\n)-----END[^\"]+\")"), "block", None),
    ("pem-privkey", "private-keys", None, _rx(r"(-----BEGIN[ A-Z0-9]{0,40}PRIVATE KEY-----\r?\n)([\s\S]+?)(\r?\n-----END[ A-Z0-9]{0,40}PRIVATE KEY-----)"), "block", None),
    ("pgp-privkey", "private-keys", None, _rx(r"(-----BEGIN PGP PRIVATE KEY BLOCK-----\r?\n)([\s\S]+?)(\r?\n-----END PGP PRIVATE KEY BLOCK-----)"), "block", None),
    ("putty-ppk", "private-keys", None, _rx(r"(PuTTY-User-Key-File-[23]:[\s\S]+?Private-Lines:\s*\d+\r?\n)([\s\S]+?)(\r?\nPrivate-MAC:)"), "block", None),
    ("ssh2-privkey", "private-keys", None, _rx(r"(---- BEGIN SSH2 (?:ENCRYPTED )?PRIVATE KEY ----\r?\n)([\s\S]+?)(\r?\n---- END SSH2 (?:ENCRYPTED )?PRIVATE KEY ----)"), "block", None),
    # national IDs. Empty group 1 means the complete candidate in group 2 is redacted.
    ("ssn", "national_ids", "US", _rx(r"(?<!\d)()((?!000|666|9\d\d)\d{3}-?(?!00)\d{2}-?(?!0000)\d{4})(?!\d)"), "national", _national(None, r"(?:\bssn\b|social[\s_-]+security)", "always")),
    ("aba-routing", "national_ids", "US", _rx(r"(?<!\d)()(\d{9})(?!\d)"), "national", _national(_valid_aba, r"(?:\baba\b|routing)", "always")),
    ("npi", "national_ids", "US", _rx(r"(?<!\d)()(\d{10})(?!\d)"), "national", _national(_valid_npi, r"\bnpi\b", "always")),
    ("mbi", "national_ids", "US", _rx(r"(?<![A-Z0-9])()([0-9][A-HJ-KM-NPQ-RT-VWXY][0-9]{2}[A-HJ-KM-NPQ-RT-VWXY][0-9]{2}[A-HJ-KM-NPQ-RT-VWXY]{2}[0-9]{2})(?![A-Z0-9])"), "national", _national()),
    ("sin", "national_ids", "CA", _rx(r"(?<!\d)()(\d{3}[- ]?\d{3}[- ]?\d{3})(?!\d)"), "national", _national(luhn, r"\bsin\b", "unformatted")),
    ("bn", "national_ids", "CA", _rx(r"(?<![A-Z0-9])()(\d{9}[A-Z]{2}\d{4})(?![A-Z0-9])"), "national", _national()),
    ("nino", "national_ids", "GB", _rx(r"(?<![A-Z0-9])()((?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\d{6}[A-D])(?![A-Z0-9])"), "national", _national()),
    ("steuer-id", "national_ids", "DE", _rx(r"(?<!\d)()([1-9]\d{10})(?!\d)"), "national", _national(_valid_steuer_id, r"(?:steuer[\s_-]*(?:id|identifikationsnummer)|identifikationsnummer)", "always")),
    ("nir", "national_ids", "FR", _rx(r"(?<!\d)()([12]\d{2}(?:0[1-9]|1[0-2]|20)\d{2}\d{3}\d{3}\d{2})(?!\d)"), "national", _national(_valid_nir)),
    ("dni", "national_ids", "ES", _rx(r"(?<![A-Z0-9])()(\d{8}[A-Z])(?![A-Z0-9])"), "national", _national(_valid_dni)),
    ("nie", "national_ids", "ES", _rx(r"(?<![A-Z0-9])()([XYZ]\d{7}[A-Z])(?![A-Z0-9])"), "national", _national(_valid_nie)),
    ("codice-fiscale", "national_ids", "IT", _rx(r"(?<![A-Z0-9])()([A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z])(?![A-Z0-9])"), "national", _national(_valid_codice_fiscale)),
    ("pesel", "national_ids", "PL", _rx(r"(?<!\d)()(\d{11})(?!\d)"), "national", _national(_valid_pesel, r"\bpesel\b", "always")),
    ("bsn", "national_ids", "NL", _rx(r"(?<!\d)()(\d{8,9})(?!\d)"), "national", _national(_valid_bsn, r"\bbsn\b", "always")),
    ("iban", "national_ids", "EU-IBAN", _rx(r"(?<![A-Z0-9])()([A-Z]{2}\d{2}[A-Z0-9]{11,30})(?![A-Z0-9])"), "national", _national(_valid_iban)),
    ("cpf", "national_ids", "BR", _rx(r"(?<!\d)()(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)"), "national", _national(_valid_cpf)),
    ("cnpj", "national_ids", "BR", _rx(r"(?<![A-Z0-9])()([A-Z0-9]{2}\.?[A-Z0-9]{3}\.?[A-Z0-9]{3}/?[A-Z0-9]{4}-?\d{2})(?![A-Z0-9])"), "national", _national(_valid_cnpj)),
    ("card-pan", "national_ids", "PAN", _rx(r"(?<!\d)()((?:\d[ -]?){12,18}\d)(?!\d)"), "national", _national(_valid_card_pan)),
    ("inn-10", "national_ids", "RU", _rx(r"(?<!\d)()(\d{10})(?!\d)"), "national", _national(_valid_inn10, r"\bинн\b", "always")),
    ("inn-12", "national_ids", "RU", _rx(r"(?<!\d)()(\d{12})(?!\d)"), "national", _national(_valid_inn12, r"\bинн\b", "always")),
    ("snils", "national_ids", "RU", _rx(r"(?<!\d)()(\d{3}-?\d{3}-?\d{3}\s?\d{2})(?!\d)"), "national", _national(_valid_snils, r"(?:\bснилс\b|\bsnils\b)", "always")),
    ("ogrn", "national_ids", "RU", _rx(r"(?<!\d)()(\d{13})(?!\d)"), "national", _national(_valid_ogrn)),
    ("ogrnip", "national_ids", "RU", _rx(r"(?<!\d)()(\d{15})(?!\d)"), "national", _national(_valid_ogrnip)),
    ("iin", "national_ids", "KZ", _rx(r"(?<!\d)()(\d{12})(?!\d)"), "national", _national(_valid_iin, r"\bиин\b", "always")),
    ("bin", "national_ids", "KZ", _rx(r"(?<!\d)()(\d{12})(?!\d)"), "national", _national(_valid_bin, r"\bбин\b", "always")),
    ("aadhaar", "national_ids", "IN", _rx(r"(?<!\d)()([2-9]\d{3}\s?\d{4}\s?\d{4})(?!\d)"), "national", _national(_valid_aadhaar, r"(?:\baadhaar\b|\buid\b)", "always")),
    ("pan-in", "national_ids", "IN", _rx(r"(?<![A-Z0-9])()([A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z])(?![A-Z0-9])"), "national", _national()),
    ("gstin", "national_ids", "IN", _rx(r"(?<![A-Z0-9])()(\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Za-z]Z[0-9A-Za-z])(?![A-Z0-9])"), "national", _national()),
    ("ifsc", "national_ids", "IN", _rx(r"(?<![A-Z0-9])()([A-Z]{4}0[A-Z0-9]{6})(?![A-Z0-9])"), "national", _national()),
    ("my-number", "national_ids", "JP", _rx(r"(?<!\d)()(\d{12})(?!\d)"), "national", _national(_valid_mynumber, r"(?:マイナンバー|個人番号)", "always")),
    ("corp-number", "national_ids", "JP", _rx(r"(?<!\d)()(\d{13})(?!\d)"), "national", _national(validate_jp_corp_number, r"法人番号", "always")),
    ("nric-fin", "national_ids", "SG", _rx(r"(?<![A-Z0-9])()([STFG]\d{7}[A-Z])(?![A-Z0-9])"), "national", _national(_valid_nric)),
    ("nik", "national_ids", "ID", _rx(r"(?<!\d)()(\d{16})(?!\d)"), "national", _national(_valid_nik, r"(?:\bnik\b|\bktp\b)", "always")),
    ("thai-id", "national_ids", "TH", _rx(r"(?<!\d)()(\d{13})(?!\d)"), "national", _national(_valid_thai_id, r"(?:thai[\s_-]*id|เลขประจำตัว)", "always")),
    ("mykad", "national_ids", "MY", _rx(r"(?<!\d)()(\d{6}-?\d{2}-?\d{4})(?!\d)"), "national", _national(_valid_mykad, r"\bmykad\b", "always")),
    ("cuit", "national_ids", "AR", _rx(r"(?<!\d)()(\d{2}-?\d{8}-?\d)(?!\d)"), "national", _national(_valid_cuit)),
    ("dni-ar", "national_ids", "AR", _rx(r"(?<!\d)()(\d{7,8})(?!\d)"), "national", _national(None, r"(?:\bdni\b|documento)", "always")),
    ("rut", "national_ids", "CL", _rx(r"(?<!\d)()(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])(?!\d)"), "national", _national(_valid_rut)),
    ("curp", "national_ids", "MX", _rx(r"(?<![A-Z0-9])()([A-Z]{4}\d{6}[HM][A-Z]{2}[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d)(?![A-Z0-9])"), "national", _national(validate_curp)),
    ("rfc", "national_ids", "MX", _rx(r"(?<![A-Z0-9])()([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3})(?![A-Z0-9])"), "national", _national(validate_rfc)),
    ("cedula-co", "national_ids", "CO", _rx(r"(?<!\d)()(\d{6,10})(?!\d)"), "national", _national(None, r"(?:cédula|cedula|\bcc\b|\bnuip\b)", "always")),
    ("dni-pe", "national_ids", "PE", _rx(r"(?<!\d)()(\d{8})(?!\d)"), "national", _national(None, r"(?:\bdni\b|documento)", "always")),
    ("ci-uy", "national_ids", "UY", _rx(r"(?<!\d)()(\d{1,2}\.?\d{3}\.?\d{3}-?\d)(?!\d)"), "national", _national(_valid_ci_uy, r"(?:cédula|cedula|\bci\b)", "always")),
    ("cedula-ve", "national_ids", "VE", _rx(r"(?<![A-Z0-9])()([VEve]-\d{6,8})(?!\d)"), "national", _national()),
    # generic fallback runs last.
    ("generic", "generic-entropy", None, _rx(
        r"(?i)(api[_-]?key|secret|token|password|passwd|client[_-]?secret|access[_-]?key|auth)"
        r"(\s*[:=]\s*['\"]?)([A-Za-z0-9+/_-]{24,})"), "generic", None),
]


def build_active_rules(config):
    groups = config["groups"]
    countries = config["national_ids"]
    return [
        rule for rule in RULES
        if (
            countries.get(rule[2], False) if rule[1] == "national_ids"
            else any(groups.get(group, False) for group in (rule[1] if isinstance(rule[1], tuple) else (rule[1],)))
        )
    ]


def _entropy(s):
    if not s:
        return 0.0
    freq = {c: s.count(c) for c in set(s)}
    n = len(s)
    return -sum((count / n) * math.log2(count / n) for count in freq.values())


def _redact(name, body):
    return f"‹REDACTED:{name}:{len(body)}ch›"


def _line_at(text, start, end):
    return text[text.rfind("\n", 0, start) + 1:text.find("\n", end) if text.find("\n", end) >= 0 else len(text)]


def _placeholder(body):
    lowered = body.lower()
    return (
        lowered in {
            "password", "changeme", "xxx", "replace_me", "your_password",
            "your-password", "placeholder", "example", "redacted", "****", "...", "....",
        }
        or lowered.startswith(("replace_me", "your_password", "your-password"))
        or re.fullmatch(r"<[^>]+>", body) is not None
    )


def _keyword_context(text, start, end):
    """Return the candidate and approximately two word tokens on either side."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    before = list(re.finditer(r"\w+", text[line_start:start], re.UNICODE))
    after = list(re.finditer(r"\w+", text[end:line_end], re.UNICODE))
    context_start = line_start + (before[-2].start() if len(before) >= 2 else before[0].start() if before else start - line_start)
    context_end = end + (after[1].end() if len(after) >= 2 else after[0].end() if after else 0)
    return text[context_start:context_end]


def _national_valid(text, match, metadata):
    validator, keyword, keyword_mode = metadata
    body = match.group(2)
    needs_keyword = keyword_mode == "always" or (keyword_mode == "unformatted" and body.isdigit())
    if needs_keyword and (keyword is None or keyword.search(_keyword_context(text, match.start(2), match.end(2))) is None):
        return False
    if validator is None:
        return True
    try:
        return bool(validator(body))
    except (ArithmeticError, LookupError, TypeError, ValueError):
        return False


class SecretMatch:
    """Four-item tuple-compatible match plus full-span metadata for blocks."""
    __slots__ = ("start", "end", "name", "body", "match_start", "match_end", "kind")

    def __init__(self, start, end, name, body, match_start, match_end, kind):
        self.start, self.end, self.name, self.body = start, end, name, body
        self.match_start, self.match_end, self.kind = match_start, match_end, kind

    def _public(self):
        return self.start, self.end, self.name, self.body

    def __iter__(self):
        return iter(self._public())

    def __getitem__(self, item):
        return self._public()[item]

    def __len__(self):
        return 4


def find_matches(text, active_rules=None):
    """Return non-overlapping tuple-compatible (start, end, name, body) matches."""
    if active_rules is None:
        active_rules = build_active_rules(default_config())
    candidates = []
    generic_rules = []
    for name, _group, _country, rx, kind, gate in active_rules:
        if kind == "generic":
            generic_rules.append((name, rx, kind))
            continue
        for match in rx.finditer(text):
            if kind == "national" and not _national_valid(text, match, gate):
                continue
            if kind != "national" and gate is not None and gate.search(_line_at(text, match.start(), match.end())) is None:
                continue
            body = match.group(2)
            if kind == "db" and _placeholder(body):
                continue
            candidates.append(SecretMatch(match.start(2), match.end(2), name, body, match.start(), match.end(), kind))
    taken = [(m.match_start, m.match_end) for m in candidates]
    for name, rx, kind in generic_rules:
        for match in rx.finditer(text):
            start, end = match.start(3), match.end(3)
            if any(s < end and start < e for s, e in taken):
                continue
            body = match.group(3)
            if _entropy(body) >= 3.5:
                candidates.append(SecretMatch(start, end, name, body, match.start(), match.end(), kind))
    candidates.sort(key=lambda m: m.match_start)
    kept = []
    last_end = None
    for match in candidates:
        if last_end is None or match.match_start >= last_end:
            kept.append(match)
            last_end = match.match_end
    return kept


def mask_text(text, active_rules=None):
    out = text
    for match in sorted(find_matches(text, active_rules), key=lambda item: item.start, reverse=True):
        out = out[:match.start] + _redact(match.name, match.body) + out[match.end:]
    return out


def _preview_body(body):
    if len(body) <= 8:
        return "…"
    if len(body) <= 12:
        return body[:2] + "…" + body[-1:]
    return body[:4] + "…" + body[-3:]


def _preview_path(path, cwd):
    resolved = os.path.abspath(path)
    try:
        return os.path.relpath(resolved, cwd) if os.path.commonpath([resolved, cwd]) == cwd else path
    except ValueError:
        return path


def _preview_line(text, match, matches):
    line_start = text.rfind("\n", 0, match.start) + 1
    line_end = text.find("\n", match.end)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end]
    replacements = []
    for other in matches:
        if other.kind != "block" and line_start <= other.start and other.end <= line_end:
            replacements.append((other.start - line_start, other.end - line_start, _preview_body(other.body)))
    for start, end, replacement in sorted(replacements, reverse=True):
        line = line[:start] + replacement + line[end:]
    return line


def _preview_block(text, match):
    snippet = text[match.match_start:match.start] + "…" + text[match.end:match.match_end]
    return re.sub(r"\s+", " ", snippet).strip()


def preview_paths(paths, active_rules=None):
    cwd = os.getcwd()
    secret_count = matched_files = 0
    for original_path in paths:
        if os.path.isdir(original_path):
            file_paths = []
            for root, dirs, files in os.walk(original_path):
                dirs[:] = [d for d in dirs if d != ".git"]
                file_paths.extend(os.path.join(root, name) for name in files)
        else:
            file_paths = [original_path]
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            matches = find_matches(text, active_rules)
            if not matches:
                continue
            matched_files += 1
            secret_count += len(matches)
            displayed_path = _preview_path(path, cwd)
            for match in matches:
                line_no = text.count("\n", 0, match.match_start) + 1
                preview = _preview_block(text, match) if match.kind == "block" else _preview_line(text, match, matches)
                print(f"{displayed_path}:{line_no}: {preview} — would redact [{match.name}]")
    print(f"{secret_count} secrets in {matched_files} files across {len(paths)} paths" if secret_count else "no secrets found")
    return 0


def _parse_args(argv):
    config_path = None
    args = []
    i = 1
    while i < len(argv):
        if argv[i] == "--config":
            if i + 1 >= len(argv):
                raise ValueError("--config requires a path")
            config_path = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    return config_path, args


def main(argv):
    try:
        config_path, args = _parse_args(argv)
        active_rules = build_active_rules(load_config(config_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"pi-mask: invalid config: {exc}\n")
        return 1
    if not args:
        sys.stderr.write("usage: pi-mask.py [--config path] <file>... | -\n")
        return 2
    if args[0] in ("--preview", "-n", "--dry-run"):
        if len(args) < 2:
            sys.stderr.write("usage: pi-mask.py [--config path] --preview <path>...\n")
            return 2
        return preview_paths(args[1:], active_rules)
    if args == ["-"]:
        sys.stdout.write(mask_text(sys.stdin.read(), active_rules))
        return 0
    for path in args:
        try:
            with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
                data = f.read()
            if "\x00" in data:
                # Binary or non-UTF-8 (e.g. UTF-16, where ASCII bytes interleave with NULs): the text
                # regexes cannot reliably find secrets here, so OMIT the content rather than stage it
                # unmasked. Denylisting excludes known binary extensions before this; this is the backstop.
                masked = "[pi-mask: binary or non-UTF-8 content omitted from review]\n"
            else:
                masked = mask_text(data, active_rules)
            with open(path, "w", encoding="utf-8", errors="surrogateescape") as f:
                f.write(masked)
        except Exception as exc:
            sys.stderr.write(f"pi-mask: FAILED on {path}: {exc}\n")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
