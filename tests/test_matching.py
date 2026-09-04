from core.matching import is_linx_legacy, is_same_product_variant, is_same_url, numeric_tokens


def test_is_linx_legacy():
    assert is_linx_legacy("https://www.bemol.com.br/produto-teste-p12345") is True
    assert is_linx_legacy("/outro-produto-p98765") is True
    assert is_linx_legacy("/produto-normal/p?idsku=123") is False
    assert is_linx_legacy("https://www.bemol.com.br/slug/p") is False
    assert is_linx_legacy("") is False


def test_is_same_url():
    assert is_same_url("/produto/p", "/produto/p") is True
    assert is_same_url("/produto/p/", "/produto/p") is True
    assert is_same_url("/produto-antigo/p", "/produto-novo/p") is False
    assert is_same_url("", "/produto/p") is False


def test_numeric_tokens():
    assert numeric_tokens("smart-tv-lg-55-polegadas") == {"55"}
    assert numeric_tokens("iphone-13-pro-256gb") == {"13", "256"}
    assert numeric_tokens("produto-sem-numero") == set()
    assert numeric_tokens("") == set()


def test_is_same_product_variant():
    # Same numbers (or none at all) -> plausibly the same product.
    assert is_same_product_variant("smart-tv-lg-55-polegadas", "smart-tv-lg-55-polegadas-nova") is True
    assert is_same_product_variant("produto-sem-numero", "produto-sem-numero-novo") is True

    # Different model/size/storage numbers -> different product, even if text is very similar.
    assert is_same_product_variant("smart-tv-lg-50-polegadas", "smart-tv-lg-55-polegadas") is False
    assert is_same_product_variant("iphone-13-pro-256gb", "iphone-13-pro-128gb") is False
    assert is_same_product_variant("iphone-13", "iphone-14") is False
