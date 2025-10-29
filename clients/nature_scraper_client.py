#!/usr/bin/env python3
"""
Nature Scraper Citation Client for Citation Analysis v2
Web scrapes citation counts directly from journal websites
Simplified version without dotenv dependency
"""

import logging
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SCRAPER_DELAY, SCRAPER_MAX_RETRIES
from clients.web_scraper import ArticleNumberScraper

class NatureScraperClient:
    """Client for scraping citation counts from journal websites"""
    
    def __init__(self, delay: float = None, max_retries: int = None):
        """Initialize the client"""
        self.delay = delay if delay is not None else SCRAPER_DELAY
        self.max_retries = max_retries if max_retries is not None else SCRAPER_MAX_RETRIES
        
        # Initialize the web scraper
        self.scraper = ArticleNumberScraper(delay=self.delay, max_retries=self.max_retries)
        
        self.logger = logging.getLogger(__name__)
        
        print("✅ Nature Scraper Client initialized for web scraping citation counts")
        print(f"   Delay between requests: {self.delay}s")
        print(f"   Max retries: {self.max_retries}")
    
    def _doi_to_url(self, doi: str) -> str:
        """Convert DOI string to full URL"""
        # Clean up the DOI
        clean_doi = doi.replace('DOI:', '').strip()
        
        # If it's already a URL, return as is
        if clean_doi.startswith('http'):
            return clean_doi
        
        # Otherwise, construct the URL
        return f"https://doi.org/{clean_doi}"
    
    def get_citation_count_for_doi(self, doi: str) -> Optional[int]:
        """Get citation count for a single DOI by scraping the web page"""
        doi_url = self._doi_to_url(doi)
        self.logger.debug(f"Scraping citation count for DOI: {doi} -> {doi_url}")
        
        citation_count = self.scraper.extract_citation_count(doi_url)
        
        if citation_count is not None:
            self.logger.info(f"Found {citation_count} citations for {doi}")
        else:
            self.logger.warning(f"Could not find citation count for {doi}")
        
        return citation_count
    
    def get_citation_counts_for_dois(self, dois: List[str]) -> Dict[str, Optional[int]]:
        """Get citation counts for multiple DOIs by scraping their web pages"""
        self.logger.info(f"Scraping citation counts for {len(dois)} DOIs using Nature Web Scraper")
        
        results = {}
        found_count = 0
        
        for i, doi in enumerate(dois, 1):
            if i % 10 == 0:
                self.logger.info(f"Progress: {i}/{len(dois)} ({i/len(dois)*100:.1f}%)")
            
            citation_count = self.get_citation_count_for_doi(doi)
            results[doi] = citation_count
            
            if citation_count is not None:
                found_count += 1
        
        self.logger.info(f"Successfully scraped citation counts for {found_count}/{len(dois)} papers")
        return results
    
    def get_papers_by_dois(self, dois: List[str], fields: List[str] = None) -> Dict[str, Optional[Dict]]:
        """Get paper information by scraping DOI pages (for compatibility with other clients)"""
        self.logger.info(f"Scraping paper data for {len(dois)} DOIs")
        
        results = {}
        citation_counts = self.get_citation_counts_for_dois(dois)
        
        for doi in dois:
            citation_count = citation_counts.get(doi)
            if citation_count is not None:
                # Create a paper data structure similar to other clients
                results[doi] = {
                    'doi': doi,
                    'citationCount': citation_count,
                    'title': None,  # Could be scraped if needed
                    'year': None,   # Could be scraped if needed
                    'externalIds': {'DOI': doi},
                    'source': 'web_scraping'
                }
            else:
                results[doi] = None
        
        return results
    
    def __del__(self):
        """Cleanup scraper"""
        if hasattr(self, 'scraper'):
            del self.scraper
