from core.category import category_path_from_product_type, legacy_product_slug, slugify_segment


def test_slugify_segment_strips_accents_and_collapses_separators():
    assert slugify_segment("Cama, Mesa e Banho") == "cama-mesa-e-banho"
    assert slugify_segment("Material de Construção") == "material-de-construcao"
    assert slugify_segment("Áudio") == "audio"
    assert slugify_segment("") == ""


def test_category_path_from_product_type():
    assert category_path_from_product_type("Moda e Acessórios - Calçados - Tênis") == "/moda-e-acessorios/calcados/tenis"
    assert category_path_from_product_type("Brinquedos") == "/brinquedos"
    assert category_path_from_product_type("") == ""
    assert category_path_from_product_type(None) == ""


def test_legacy_product_slug_drops_linx_product_id_and_query():
    assert (
        legacy_product_slug("https://www.bemol.com.br/tinta-acrilica-premium-mp--p1086695?v=1086696")
        == "tinta-acrilica-premium-mp"
    )
    assert legacy_product_slug("/fogao-05-bocas-mueller-p1108735") == "fogao-05-bocas-mueller"
    assert legacy_product_slug("") == ""
