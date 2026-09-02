from core.matching import is_linx_legacy, is_same_url


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
