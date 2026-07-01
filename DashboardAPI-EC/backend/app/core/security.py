def mask_secret(value: str | None, visible: int = 4) -> str | None:
    if value is None:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * 8}"
