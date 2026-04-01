import re
import unicodedata

NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = NON_ALNUM.sub("-", normalized.lower()).strip("-")
    return slug or "poi"
