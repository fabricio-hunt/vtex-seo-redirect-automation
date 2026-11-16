from core.config import RecoveryConfig
from core.feed import FeedIndex
from core.matching import (
    is_linx_legacy,
    is_same_product_variant,
    is_same_url,
    match_single_url,
    numeric_tokens,
)


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
    assert is_same_product_variant("smart-tv-lg-55-polegadas", "smart-tv-lg-55-polegadas-nova") is True
    assert is_same_product_variant("produto-sem-numero", "produto-sem-numero-novo") is True

    assert is_same_product_variant("smart-tv-lg-50-polegadas", "smart-tv-lg-55-polegadas") is False
    assert is_same_product_variant("iphone-13-pro-256gb", "iphone-13-pro-128gb") is False
    assert is_same_product_variant("iphone-13", "iphone-14") is False


def test_match_single_url_rules():
    feed = FeedIndex(
        active_urls=[
            "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p",
            "https://www.bemol.com.br/fralda-pampers-confort-sec/p",
            "https://www.bemol.com.br/jogo-de-cama-casal-algodao/p",
        ],
        slug_to_url={
            "smart-tv-lg-55-polegadas": "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p",
            "fralda-pampers-confort-sec": "https://www.bemol.com.br/fralda-pampers-confort-sec/p",
            "jogo-de-cama-casal-algodao": "https://www.bemol.com.br/jogo-de-cama-casal-algodao/p",
        },
        slug_to_category={
            "smart-tv-lg-55-polegadas": "/tv-e-video/smart-tv",
            "fralda-pampers-confort-sec": "/bebes/fraldas",
            "jogo-de-cama-casal-algodao": "/cama-mesa-e-banho/cama",
        },
    )
    config = RecoveryConfig(threshold=85, check_http_status=False)

    # 1. Same URL loop protection
    same_res = match_single_url("https://www.bemol.com.br/smart-tv-lg-55-polegadas/p", feed, config)
    assert same_res["match_type"] == "Same_URL_Ignored"
    assert same_res["to"] == ""

    # 2. Legacy Linx
    linx_res = match_single_url("https://www.bemol.com.br/smart-tv-lg-50-p999", feed, config)
    assert linx_res["match_type"].startswith("Legacy_Category_")
    assert linx_res["to"] == "/tv-e-video/smart-tv"

    # 3. WCS store auth
    wcs_res = match_single_url("/webapp/wcs/stores/servlet/Logon", feed, config)
    assert wcs_res["to"] == "/login"
    assert wcs_res["match_type"] == "Legacy_WCS_Auth"

    # 4. Typo comma
    typo_res = match_single_url("/cama,-mesa-e-banho/lencol", feed, config)
    assert typo_res["to"] == "/cama-mesa-e-banho/lencol"
    assert typo_res["match_type"] == "URL_Typo_Fixed"

    # 5. Brand vendor suffix
    vendor_res = match_single_url("/pampers-prg-", feed, config)
    assert vendor_res["to"] == "/pampers"
    assert vendor_res["match_type"] == "Brand_Vendor_Suffix_Stripped"

    # 6. Legacy /p/ prefix with 18-digit ID
    legacy_p_res = match_single_url("/p/smart-tv-lg-55-polegadas-000000000000123456", feed, config)
    assert legacy_p_res["to"] == "/tv-e-video/smart-tv"
    assert legacy_p_res["match_type"].startswith("Legacy_P_Category_")

    # 7. Exact slug
    exact_res = match_single_url("/smart-tv-lg-55-polegadas/p", feed, config)
    assert exact_res["match_type"] == "Same_URL_Ignored"  # because destination is same

    # 8. Trailing dash without direct product match -> fallback to category
    dash_res = match_single_url("/jogo-de-cama-casal-", feed, config)
    assert dash_res["to"] == "/cama-mesa-e-banho/cama"
    assert dash_res["match_type"].startswith("Category_Fuzzy_")
