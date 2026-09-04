from core.text_utils import clean_text


def test_clean_text_fixes_known_mojibake():
    assert clean_text("100Âº") == "100º"
    assert clean_text("SÃ£o Paulo") == "São Paulo"
    assert clean_text("AÃ§o inox") == "Aço inox"


def test_clean_text_url_unquotes():
    assert clean_text("/produto%20teste") == "/produto teste"


def test_clean_text_leaves_clean_text_untouched():
    assert clean_text("/produto-normal/p") == "/produto-normal/p"


def test_clean_text_resolves_double_encoded_urls():
    """Google Search Console sometimes reports 404 paths double-encoded
    (e.g. '%25C2%25B0' for '°'), which a single unquote() only half-resolves,
    leaving a literal '%C2%B0' in the output that breaks the VTEX CSV import."""
    assert clean_text("n%25C2%25B039") == "n°39"
    assert clean_text("n%25C2%25BA38") == "nº38"


def test_clean_text_does_not_over_decode_a_literal_percent_sign():
    # A real, single-encoded literal '%' (e.g. "50% off") must not be decoded further.
    assert clean_text("50%25-off") == "50%-off"
