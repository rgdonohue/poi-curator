import logging


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    parts = [f"event={event}"]
    for key in sorted(fields):
        value = fields[key]
        if value is None:
            continue
        parts.append(f"{key}={value}")
    logger.info(" ".join(parts))
