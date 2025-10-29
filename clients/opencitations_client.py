#!/usr/bin/env python3
"""
OpenCitations API Client for Citation Analysis v2
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

class OpenCitationsClient:
    """Client for interacting with Open Citations API"""
    
    def __init__(self, request_delay=1.0, batch_size=50, timeout=30):
        self.base_url = "https://api.opencitations.net/index/v1"
        self.request_delay = request_delay
        self.batch_size = batch_size
        self.timeout = timeout
        
        self.logger = logging.getLogger(__name__)
        
        # Setup session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Citation-Analysis-v2/1.0'
        })
        
        self.logger.info("OpenCitations client initialized")
    
    def get_citation_count_for_doi(self, doi: str) -> Optional[int]:
        """Get citation count for a single DOI"""
        clean_doi = doi.replace('doi:', '').strip()
        
        try:
            self.logger.debug(f"Fetching citation count for DOI: {clean_doi}")
            
            url = f"{self.base_url}/citation-count/{clean_doi}"
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    count_str = data[0].get('count', '0')
                    try:
                        count = int(count_str)
                        self.logger.debug(f"Found {count} citations for DOI: {clean_doi}")
                        
                        # Respect rate limits
                        time.sleep(self.request_delay)
                        return count
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid count format for DOI {clean_doi}: {count_str}")
                        return None
                else:
                    self.logger.warning(f"Empty response for DOI: {clean_doi}")
                    return None
            elif response.status_code == 404:
                self.logger.warning(f"DOI not found in OpenCitations: {clean_doi}")
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
        self.logger.info(f"Fetching citation counts for {len(dois)} DOIs using OpenCitations")
        
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
