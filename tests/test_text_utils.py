from core.text_utils import clean_text


def test_clean_text_fixes_known_mojibake():
    assert clean_text("100Âº") == "100º"
    assert clean_text("SÃ£o Paulo") == "São Paulo"
    assert clean_text("AÃ§o inox") == "Aço inox"


def test_clean_text_url_unquotes():
    assert clean_text("/produto%20teste") == "/produto teste"


def test_clean_text_leaves_clean_text_untouched():
    assert clean_text("/produto-normal/p") == "/produto-normal/p"
