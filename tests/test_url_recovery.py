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

def test_is_same_url():
    manager = URLRecoveryManager()
    assert manager.is_same_url("/produto/p", "/produto/p") == True
    assert manager.is_same_url("/produto/p/", "/produto/p") == True
    assert manager.is_same_url("/produto-antigo/p", "/produto-novo/p") == False

def test_same_url_ignored(tmpdir):
    manager = URLRecoveryManager()
    manager.active_urls = ["https://www.bemol.com.br/produto-teste/p"]
    manager.slug_to_url = {"produto-teste": "https://www.bemol.com.br/produto-teste/p"}
    
    input_file = tmpdir.join("input.csv")
    input_data = pd.DataFrame({
        "URL": ["https://www.bemol.com.br/produto-teste/p"]
    })
    input_data.to_csv(input_file, index=False)
    
    output_file = tmpdir.join("output.csv")
    manager.process_404_list(str(input_file), str(output_file), threshold=90, check_http_status=False)
    
    # Exclude from final output because from == to
    assert not os.path.exists(str(output_file)) or len(pd.read_csv(str(output_file), sep=';')) == 0
    
    review_df = pd.read_csv(str(output_file).replace('.csv', '_review.csv'), sep=';')
    assert len(review_df) == 1
    assert review_df.iloc[0]['match_type'] == 'Same_URL_Ignored'

def test_process_404_list(tmpdir):
    manager = URLRecoveryManager()
    # Mocking the active URLs
    manager.active_urls = [
        "https://www.bemol.com.br/smartphone-samsung-galaxy-s23-novo/p",
        "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p?idsku=999"
    ]
    manager.slug_to_url = {
        "smartphone-samsung-galaxy-s23": "https://www.bemol.com.br/smartphone-samsung-galaxy-s23-novo/p",
        "smart-tv-lg-55-polegadas": "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p?idsku=999"
    }
    
    # Create a dummy input CSV
    input_file = tmpdir.join("input.csv")
    input_data = pd.DataFrame({
        "URL": [
            "https://www.bemol.com.br/produto-antigo-p444", # Linx legacy -> /superoferta
            "https://www.bemol.com.br/smartphone-samsung-galaxy-s23/p", # Exact match
            "https://www.bemol.com.br/smart-tv-lg-55-polegada/p", # Fuzzy match (missing 's')
            "https://www.bemol.com.br/produto-inexistente/p" # No match -> should be filtered from final CSV
        ]
    })
    input_data.to_csv(input_file, index=False)
    
    output_file = tmpdir.join("output.csv")
    
    manager.process_404_list(str(input_file), str(output_file), threshold=90, check_http_status=False)
    
    assert os.path.exists(str(output_file))
    
    result_df = pd.read_csv(str(output_file), sep=';')
    
    # Apenas os 3 que tiveram match válido (No_Match não vai pro arquivo final)
    assert len(result_df) == 3
    
    # Check Linx Legacy rule
    assert result_df.iloc[0]['to'] == '/superoferta'
    assert result_df.iloc[0]['type'] == 'PERMANENT'
    
    # Check Exact Match
    assert result_df.iloc[1]['to'] == '/smartphone-samsung-galaxy-s23-novo/p'
    
    # Check Fuzzy Match (90% threshold should match smart-tv-lg-55-polegadas)
    assert result_df.iloc[2]['to'] == '/smart-tv-lg-55-polegadas/p'
    
    # Verifica que o arquivo de review contém todos os 4 registros, inclusive o No_Match
    review_df = pd.read_csv(str(output_file).replace('.csv', '_review.csv'), sep=';')
    assert len(review_df) == 4
    assert review_df.iloc[3]['match_type'] == 'No_Match'
