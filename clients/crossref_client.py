#!/usr/bin/env python3
"""
Crossref API Client for Citation Analysis v2
Simplified version without dotenv dependency
"""

import time
import logging
import requests
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CROSSREF_EMAIL

class CrossrefClient:
    """Client for interacting with Crossref API"""
    
    def __init__(self, request_delay=1.0, batch_size=50, timeout=30):
        self.base_url = "https://api.crossref.org"
        self.request_delay = request_delay
        self.batch_size = batch_size
        self.timeout = timeout
        
        self.logger = logging.getLogger(__name__)
        
        # Setup session for connection pooling
        self.session = requests.Session()
        user_agent = f'Citation-Analysis-v2/1.0 (mailto:{CROSSREF_EMAIL})'
        self.session.headers.update({
            'User-Agent': user_agent
        })
        
        self.logger.info("Crossref client initialized")
    
    def get_citation_count_for_doi(self, doi: str) -> Optional[int]:
        """Get citation count for a single DOI"""
        clean_doi = doi.replace('doi:', '').strip()
        
        try:
            self.logger.debug(f"Fetching citation count for DOI: {clean_doi}")
            
            url = f"{self.base_url}/works/{clean_doi}"
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                message = data.get('message', {})
                
                if message:
                    citation_count = message.get('is-referenced-by-count', 0)
                    self.logger.debug(f"Found {citation_count} citations for DOI: {clean_doi}")
                    
                    # Respect rate limits
                    time.sleep(self.request_delay)
                    return citation_count
                else:
                    self.logger.warning(f"Empty message in response for DOI: {clean_doi}")
                    return None
            elif response.status_code == 404:
                self.logger.warning(f"DOI not found in Crossref: {clean_doi}")
                return None
            else:
                self.logger.error(f"HTTP {response.status_code} for DOI {clean_doi}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error for DOI {clean_doi}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error for DOI {clean_doi}: {e}")
            return None
    
    def get_citation_counts_for_dois(self, dois: List[str]) -> Dict[str, Optional[int]]:
        """Get citation counts for multiple DOIs"""
        self.logger.info(f"Fetching citation counts for {len(dois)} DOIs using Crossref")
        
        citation_counts = {}
        found_count = 0
        
        for i, doi in enumerate(dois):
            clean_doi = doi.replace('doi:', '').strip()
            self.logger.debug(f"Processing DOI {i+1}/{len(dois)}: {clean_doi}")
            
            citation_count = self.get_citation_count_for_doi(clean_doi)
            citation_counts[doi] = citation_count
            
            if citation_count is not None:
                found_count += 1
            
            # Rate limiting between requests
            if i < len(dois) - 1:
                time.sleep(self.request_delay)
        
        self.logger.info(f"Found citation counts for {found_count}/{len(dois)} papers")
        return citation_counts
