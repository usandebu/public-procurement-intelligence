from datetime import datetime


def format_euros(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", ".") + " €"


def format_deadline(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if "T" in value or " " in value:
        return parsed.strftime("%d/%m/%Y %H:%M")
    return parsed.strftime("%d/%m/%Y")
