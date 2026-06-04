import re
import unicodedata

NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = NON_ALNUM.sub("-", normalized.lower()).strip("-")
    return slug or "poi"


COMMON_AFFIXES = {
    "the",
    "of",
    "and",
    "de",
    "la",
    "las",
    "los",
    "san",
    "santa",
    "fe",
    "saint",
    "st",
    "historic",
    "historical",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_name_tokens(value: str) -> set[str]:
    tokens = set()
    for token in TOKEN_RE.findall(value.casefold()):
        if token in COMMON_AFFIXES:
            continue
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        tokens.add(token)
    return tokens
