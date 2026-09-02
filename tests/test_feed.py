from core.feed import extract_slug


def test_extract_slug():
    url1 = "https://www.bemol.com.br/relogio-digital-casio-preto-dbc32-1a-a-bi/p"
    assert extract_slug(url1) == "relogio-digital-casio-preto-dbc32-1a-a-bi"

    url2 = "https://www.bemol.com.br/relogio-digital-casio-preto-dbc32-1a-a-bi/p?idsku=123"
    assert extract_slug(url2) == "relogio-digital-casio-preto-dbc32-1a-a-bi"

    url3 = "/some-random-slug/p"
    assert extract_slug(url3) == "some-random-slug"

    assert extract_slug("") == ""
    assert extract_slug(None) == ""
