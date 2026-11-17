from bibaifilter.core import catalog


def test_exact_entry_is_returned_unchanged():
    m = catalog.get("openai", "gpt-5.4")
    assert m.id == "gpt-5.4" and m.price_in == 2.50


def test_dated_snapshot_uses_the_base_entry():
    m = catalog.get("openai", "gpt-5.4-2026-03-05")
    base = catalog.get("openai", "gpt-5.4")
    assert m.id == "gpt-5.4-2026-03-05"
    assert (m.price_in, m.price_out) == (base.price_in, base.price_out)
    assert m.temperature == base.temperature and m.status == base.status
    assert "Dated snapshot of gpt-5.4" in m.note
    assert catalog.cost_usd(m, 1000, 10) is not None


def test_compact_date_suffix():
    m = catalog.get("openai", "gpt-5.4-mini-20260317")
    assert m.price_in == catalog.get("openai", "gpt-5.4-mini").price_in


def test_longest_catalogued_base_wins():
    assert catalog.get("openai", "gpt-5.4-mini-2026-03-17").price_in == 0.75


def test_unknown_identifiers_stay_generic():
    assert catalog.get("openai", "gpt-9-2030-01-01").status == "unknown"
    assert catalog.get("openai", "gpt-5.4-preview").status == "unknown"
    assert catalog.get("anthropic", "gpt-5.4-2026-03-05").status == "unknown"
