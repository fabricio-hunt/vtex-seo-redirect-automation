import pytest
import pandas as pd
import os
from url_recovery import URLRecoveryManager

def test_extract_slug():
    manager = URLRecoveryManager()
    
    url1 = "https://www.bemol.com.br/relogio-digital-casio-preto-dbc32-1a-a-bi/p"
    assert manager.extract_slug(url1) == "relogio-digital-casio-preto-dbc32-1a-a-bi"
    
    url2 = "https://www.bemol.com.br/relogio-digital-casio-preto-dbc32-1a-a-bi/p?idsku=123"
    assert manager.extract_slug(url2) == "relogio-digital-casio-preto-dbc32-1a-a-bi"
    
    url3 = "/some-random-slug/p"
    assert manager.extract_slug(url3) == "some-random-slug"

def test_is_linx_legacy():
    manager = URLRecoveryManager()
    
    assert manager.is_linx_legacy("https://www.bemol.com.br/produto-teste-p12345") == True
    assert manager.is_linx_legacy("/outro-produto-p98765") == True
    assert manager.is_linx_legacy("/produto-normal/p?idsku=123") == False
    assert manager.is_linx_legacy("https://www.bemol.com.br/slug/p") == False

def test_process_404_list(tmpdir):
    manager = URLRecoveryManager()
    # Mocking the active URLs
    manager.active_urls = [
        "https://www.bemol.com.br/smartphone-samsung-galaxy-s23/p",
        "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p?idsku=999"
    ]
    manager.slug_to_url = {
        "smartphone-samsung-galaxy-s23": "https://www.bemol.com.br/smartphone-samsung-galaxy-s23/p",
        "smart-tv-lg-55-polegadas": "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p?idsku=999"
    }
    
    # Create a dummy input CSV
    input_file = tmpdir.join("input.csv")
    input_data = pd.DataFrame({
        "URL": [
            "https://www.bemol.com.br/produto-antigo-p444", # Linx legacy
            "https://www.bemol.com.br/smartphone-samsung-galaxy-s23/p", # Exact match
            "https://www.bemol.com.br/smart-tv-lg-55-polegada/p", # Fuzzy match (missing 's')
            "https://www.bemol.com.br/produto-inexistente/p" # No match
        ]
    })
    input_data.to_csv(input_file, index=False)
    
    output_file = tmpdir.join("output.csv")
    
    manager.process_404_list(str(input_file), str(output_file), threshold=90)
    
    assert os.path.exists(str(output_file))
    
    result_df = pd.read_csv(str(output_file), sep=';')
    
    assert len(result_df) == 4
    
    # Check Linx Legacy rule
    assert result_df.iloc[0]['to'] == '/superoferta'
    assert result_df.iloc[0]['type'] == 'PERMANENT'
    
    # Check Exact Match
    assert result_df.iloc[1]['to'] == '/smartphone-samsung-galaxy-s23/p'
    
    # Check Fuzzy Match (90% threshold should match smart-tv-lg-55-polegadas)
    assert result_df.iloc[2]['to'] == '/smart-tv-lg-55-polegadas/p?idsku=999'
    
    # Check No Match
    assert pd.isna(result_df.iloc[3]['to']) or result_df.iloc[3]['to'] == ''
