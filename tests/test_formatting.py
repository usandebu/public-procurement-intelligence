from procurement.formatting import format_deadline, format_euros


def test_format_euros_uses_spanish_thousands_separator():
    assert format_euros(63660) == "63.660 €"
    assert format_euros(1507788.32) == "1.507.788 €"
    assert format_euros(500) == "500 €"


def test_format_deadline_renders_date_and_time_in_spanish_order():
    assert format_deadline("2026-10-26T14:00:00") == "26/10/2026 14:00"
    assert format_deadline("2026-09-24") == "24/09/2026"
    assert format_deadline("sin fecha") == "sin fecha"
