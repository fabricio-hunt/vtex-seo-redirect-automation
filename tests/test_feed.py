import io

from core.feed import extract_slug, parse_feed_xml


def test_extract_slug():
    url1 = "https://www.bemol.com.br/relogio-digital-casio-preto-dbc32-1a-a-bi/p"
    assert extract_slug(url1) == "relogio-digital-casio-preto-dbc32-1a-a-bi"

    url2 = "https://www.bemol.com.br/relogio-digital-casio-preto-dbc32-1a-a-bi/p?idsku=123"
    assert extract_slug(url2) == "relogio-digital-casio-preto-dbc32-1a-a-bi"

    url3 = "/some-random-slug/p"
    assert extract_slug(url3) == "some-random-slug"

    assert extract_slug("") == ""
    assert extract_slug(None) == ""


def test_parse_feed_xml_maps_slugs_to_category_paths():
    xml = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns:g="http://base.google.com/ns/1.0" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <g:product_type><![CDATA[Moda e Acessórios - Calçados - Tênis]]></g:product_type>
    <link><![CDATA[https://www.bemol.com.br/tenis-corrida-azul/p?idsku=1]]></link>
  </entry>
  <entry>
    <link><![CDATA[https://www.bemol.com.br/produto-sem-categoria/p?idsku=2]]></link>
  </entry>
</feed>"""

    index = parse_feed_xml(io.BytesIO(xml.encode("utf-8")))

    assert index.slug_to_url == {
        "tenis-corrida-azul": "https://www.bemol.com.br/tenis-corrida-azul/p?idsku=1",
        "produto-sem-categoria": "https://www.bemol.com.br/produto-sem-categoria/p?idsku=2",
    }
    assert index.slug_to_category == {"tenis-corrida-azul": "/moda-e-acessorios/calcados/tenis"}
