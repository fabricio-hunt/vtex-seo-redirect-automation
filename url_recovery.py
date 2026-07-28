import pandas as pd
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from rapidfuzz import process, fuzz
import re
import os
from concurrent.futures import ThreadPoolExecutor

class URLRecoveryManager:
    def __init__(self, xml_url="http://www.bemol.com.br/XMLData/googleshopping.xml"):
        self.xml_url = xml_url
        self.active_urls = []
        self.slug_to_url = {}
        self.url_status_cache = {}
        
    def download_and_parse_xml(self, max_items=None):
        """Downloads the XML feed and extracts active URLs and slugs."""
        print(f"Downloading XML feed from {self.xml_url}...")
        response = requests.get(self.xml_url, stream=True)
        response.raise_for_status()
        response.raw.decode_content = True
        
        # We use iterparse for memory efficiency
        context = ET.iterparse(response.raw, events=("end",))
        
        count = 0
        namespace = ""
        
        for event, elem in context:
            if event == "end":
                # Handle namespaces if present (e.g. {http://www.w3.org/2005/Atom}entry)
                tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if not namespace and '}' in elem.tag:
                    namespace = elem.tag.split('}')[0] + '}'
                    
                if tag_name == 'entry' or tag_name == 'item':
                    # Find link
                    link_elem = elem.find(f'{namespace}link') if namespace else elem.find('link')
                    if link_elem is not None:
                        url = link_elem.text
                        if url:
                            self.active_urls.append(url)
                            slug = self.extract_slug(url)
                            if slug:
                                self.slug_to_url[slug] = url
                    
                    count += 1
                    elem.clear() # Free memory
                    if max_items and count >= max_items:
                        break
        
        print(f"Parsed {len(self.active_urls)} active URLs from the feed.")
        
    def extract_slug(self, url):
        """Extracts the product slug from a Bemol URL."""
        if not url or not isinstance(url, str):
            return ""
        try:
            # Clean url
            url = self.clean_text(url)
            path = urlparse(url).path
            parts = path.strip('/').split('/')
            if len(parts) >= 2 and parts[-1] == 'p':
                return parts[-2]
            return parts[0] if parts else ""
        except:
            return ""

    def clean_text(self, text):
        from urllib.parse import unquote
        text = unquote(text)
        
        # Explicit replacements for common encoding artifacts (UTF-8 read as Latin-1)
        replacements = {
            'Âº': 'º', 'Â°': '°', 'Ã£': 'ã', 'Ã§': 'ç', 'Ã¡': 'á', 
            'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú', 'Ã¢': 'â', 
            'Ãª': 'ê', 'Ã´': 'ô', 'Ãµ': 'õ', 'Ã': 'í', 'Â': ''
        }
        for bad, good in replacements.items():
            text = text.replace(bad, good)
            
        try:
            # Fallback if there are other latin-1 artifacts
            if 'Ã' in text or 'Â' in text:
                text = text.encode('latin1').decode('utf-8')
        except:
            pass
        return text

    def is_linx_legacy(self, url):
        """Checks if URL is a legacy Linx URL containing '-p12345'."""
        if not url or not isinstance(url, str):
            return False
        # Matches -p followed by numbers, e.g., -p1086695
        return bool(re.search(r'-p\d+', url))

    def is_same_url(self, path1, path2):
        """Checks if source path and target path point to the exact same URL."""
        if not path1 or not path2:
            return False
        p1 = path1.strip('/').lower()
        p2 = path2.strip('/').lower()
        return p1 == p2

    def check_url_status(self, url_path):
        """Checks HTTP status code for a given URL or path, with caching."""
        if not url_path:
            return None
        if url_path in self.url_status_cache:
            return self.url_status_cache[url_path]
            
        full_url = url_path if url_path.startswith('http') else f"https://www.bemol.com.br{url_path if url_path.startswith('/') else '/' + url_path}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        try:
            response = requests.get(full_url, headers=headers, stream=True, timeout=10, allow_redirects=True)
            status = response.status_code
            response.close()
        except Exception as e:
            status = None
            
        self.url_status_cache[url_path] = status
        return status

    def process_404_list(self, input_file, output_file, threshold=90, check_http_status=True):
        """Processes the input Excel/CSV of 404s and outputs the redirects CSV."""
        print(f"Processing 404 file: {input_file}")
        if input_file.endswith('.xlsx'):
            df = pd.read_excel(input_file)
        else:
            df = pd.read_csv(input_file)
            
        # Assuming the URL column is named 'URL' or it's the first column
        url_col = 'URL' if 'URL' in df.columns else df.columns[0]
        
        results = []
        
        active_slugs = list(self.slug_to_url.keys())
        
        for index, row in df.iterrows():
            url_404 = str(row[url_col]).strip()
            url_404 = self.clean_text(url_404)
            
            # Ensure it's a valid URL format for path extraction
            if not url_404.startswith('http'):
                url_404 = 'https://www.bemol.com.br' + (url_404 if url_404.startswith('/') else '/' + url_404)
                
            path_404 = urlparse(url_404).path
            
            # Rule 1: Linx Legacy (-p12345) -> /superoferta
            if self.is_linx_legacy(path_404):
                dest_path = '/superoferta'
                if self.is_same_url(path_404, dest_path):
                    results.append({
                        'from': path_404,
                        'to': '',
                        'type': 'PERMANENT',
                        'endDate': '',
                        'match_type': 'Same_URL_Ignored'
                    })
                else:
                    results.append({
                        'from': path_404,
                        'to': dest_path,
                        'type': 'PERMANENT',
                        'endDate': '',
                        'match_type': 'Legacy_Linx'
                    })
                continue
                
            # Rule 2: Exact Slug Match
            slug_404 = self.extract_slug(url_404)
            if slug_404 in self.slug_to_url:
                dest_url = self.clean_text(self.slug_to_url[slug_404])
                dest_path = urlparse(dest_url).path
                
                if self.is_same_url(path_404, dest_path):
                    results.append({
                        'from': path_404,
                        'to': '',
                        'type': 'PERMANENT',
                        'endDate': '',
                        'match_type': 'Same_URL_Ignored'
                    })
                else:
                    results.append({
                        'from': path_404,
                        'to': dest_path,
                        'type': 'PERMANENT',
                        'endDate': '',
                        'match_type': 'Exact_Slug'
                    })
                continue
                
            # Rule 3: Fuzzy Slug Match
            if slug_404 and active_slugs:
                match = process.extractOne(slug_404, active_slugs, scorer=fuzz.ratio)
                best_match, score = match[0], match[1]
                if score >= threshold:
                    dest_url = self.clean_text(self.slug_to_url[best_match])
                    dest_path = urlparse(dest_url).path
                    
                    if self.is_same_url(path_404, dest_path):
                        results.append({
                            'from': path_404,
                            'to': '',
                            'type': 'PERMANENT',
                            'endDate': '',
                            'match_type': 'Same_URL_Ignored'
                        })
                    else:
                        results.append({
                            'from': path_404,
                            'to': dest_path,
                            'type': 'PERMANENT',
                            'endDate': '',
                            'match_type': f'Fuzzy_{score}%'
                        })
                    continue
            
            # No match found
            results.append({
                'from': path_404,
                'to': '',
                'type': 'PERMANENT',
                'endDate': '',
                'match_type': 'No_Match'
            })

        # Coleta URLs únicas de destino para verificação de status HTTP
        unique_to_urls = list({r['to'] for r in results if r['to']})
        if check_http_status and unique_to_urls:
            print(f"Verificando status HTTP para {len(unique_to_urls)} URLs de destino únicas...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                list(executor.map(self.check_url_status, unique_to_urls))

        for r in results:
            if r['to']:
                r['status_code'] = self.url_status_cache.get(r['to'], '') if check_http_status else 200
            else:
                r['status_code'] = ''

        # Save to CSV using the template format (from;to;type;endDate)
        out_df = pd.DataFrame(results)
        
        # Apenas URLs com destino preenchido, que não sejam DE -> PARA para a mesma URL, 
        # e com status HTTP 200 (se verificação ativada)
        valid_mask = (
            (out_df['to'] != '') & 
            (out_df['to'].notna()) & 
            (out_df['match_type'] != 'Same_URL_Ignored')
        )
        if check_http_status:
            valid_mask = valid_mask & (out_df['status_code'].astype(str) == '200')

        final_df = out_df.loc[valid_mask, ['from', 'to', 'type', 'endDate']]
        
        # Write to csv with utf-8-sig so Excel opens it correctly without Â artifacts
        final_df.to_csv(output_file, sep=';', index=False, encoding='utf-8-sig')
        print(f"Saved {len(final_df)} valid redirects (HTTP 200 & no same-URL loop) to {output_file}")
        
        # Write an extended version for review
        review_file = output_file.replace('.csv', '_review.csv')
        out_df.to_csv(review_file, sep=';', index=False, encoding='utf-8-sig')
        print(f"Saved detailed review file to {review_file}")

if __name__ == "__main__":
    manager = URLRecoveryManager()
    manager.download_and_parse_xml()
    
    input_file = "404-gsc/Tabela.csv"
    if os.path.exists(input_file):
        manager.process_404_list(input_file, "redirects.csv", threshold=90, check_http_status=True)
    else:
        print(f"Arquivo não encontrado: {input_file}")
