#!/usr/bin/env python3
"""
Web Scraping Module for Citation Analysis v2
Extracts article numbers and citation counts from journal web pages
Simplified version without dotenv dependency
"""

import re
import time
import logging
from typing import Optional, Dict, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys
import os

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SCRAPER_DELAY, SCRAPER_MAX_RETRIES

class ArticleNumberScraper:
    """Scraper for extracting article numbers and citation counts from journal pages"""
    
    def __init__(self, delay: float = None, max_retries: int = None):
        """Initialize the scraper"""
        self.delay = delay if delay is not None else SCRAPER_DELAY
        self.max_retries = max_retries if max_retries is not None else SCRAPER_MAX_RETRIES
        self.logger = logging.getLogger(__name__)
        
        # Setup session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set user agent to avoid blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_article_number(self, doi_url: str) -> Optional[str]:
        """Extract article number from a DOI URL"""
        try:
            self.logger.debug(f"Fetching article number from: {doi_url}")
            
            response = self.session.get(doi_url, timeout=30)
            response.raise_for_status()
            
            article_number = self._parse_article_number(response.text, doi_url)
            
            if article_number:
                self.logger.debug(f"Found article number: {article_number} for {doi_url}")
            else:
                self.logger.warning(f"No article number found for {doi_url}")
            
            time.sleep(self.delay)
            return article_number
            
        except Exception as e:
            self.logger.error(f"Error fetching article number from {doi_url}: {e}")
            return None
    
    def _parse_article_number(self, html_content: str, url: str) -> Optional[str]:
        """Parse article number from HTML content"""
        try:
            # Try BeautifulSoup if available, otherwise use raw HTML
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                text_content = soup.get_text()
            except ImportError:
                # BeautifulSoup not available, use raw HTML
                text_content = html_content
        except Exception:
            text_content = html_content
        
        # Patterns to match article numbers
        patterns = [
            r'Article number:\s*(\d+)',
            r'article number:\s*(\d+)',
            r'Article\s+number:\s*(\d+)',
            r'Article\s+number\s*:\s*(\d+)',
            r'Article\s+Number:\s*(\d+)',
            r'ARTICLE\s+NUMBER:\s*(\d+)',
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                article_number = match.group(1)
                self.logger.debug(f"Found article number with pattern {i+1}: {article_number}")
                return article_number
        
        # Try other patterns
        year_pattern = r'(\d+)\s*\(20\d{2}\)'
        matches = re.findall(year_pattern, text_content)
        if matches:
            for potential_number in matches:
                if 1 <= int(potential_number) <= 50000:
                    self.logger.debug(f"Found potential article number from year pattern: {potential_number}")
                    return potential_number
        
        # Look in structured data
        if '"articleNumber"' in html_content:
            article_num_pattern = r'"articleNumber"[:\s]*"?(\d+)"?'
            match = re.search(article_num_pattern, html_content)
            if match:
                article_number = match.group(1)
                self.logger.debug(f"Found in JSON metadata: {article_number}")
                return article_number
        
        return None
    
    def extract_citation_count(self, doi_url: str) -> Optional[int]:
        """Extract citation count from a DOI URL"""
        try:
            self.logger.debug(f"Fetching citation count from: {doi_url}")
            
            response = self.session.get(doi_url, timeout=30)
            response.raise_for_status()
            
            citation_count = self._parse_citation_count(response.text, doi_url)
            
            if citation_count is not None:
                self.logger.debug(f"Found citation count: {citation_count} for {doi_url}")
            else:
                self.logger.warning(f"No citation count found for {doi_url}")
            
            time.sleep(self.delay)
            return citation_count
            
        except Exception as e:
            self.logger.error(f"Error fetching citation count from {doi_url}: {e}")
            return None
    
    def _parse_citation_count(self, html_content: str, url: str) -> Optional[int]:
        """Parse citation count from HTML content"""
        try:
            # Try BeautifulSoup if available, otherwise use raw HTML
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                text_content = soup.get_text()
            except ImportError:
                # BeautifulSoup not available, use raw HTML
                text_content = html_content
        except Exception:
            text_content = html_content
        
        # Patterns to match citation counts
        patterns = [
            r'(\d+)\s+citations?',  # Moved this pattern first as it's most reliable
            r'(\d{1,3}(?:,\d{3})*)\s+citations?',
            r'(\d+)\s+citation[s]?\b',
            r'cited\s+by\s+(\d{1,3}(?:,\d{3})*)',
            r'citations?:\s*(\d{1,3}(?:,\d{3})*)',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                citation_str = match.group(1)
                try:
                    citation_count = int(citation_str.replace(',', ''))
                    if 0 <= citation_count <= 100000:  # Reasonable range
                        self.logger.debug(f"Found citation count with pattern {i+1}: {citation_count}")
                        return citation_count
                except ValueError:
                    continue
        
        # Look in structured data
        if '"citationCount"' in html_content:
            citation_pattern = r'"citationCount"[:\s]*"?(\d+)"?'
            match = re.search(citation_pattern, html_content)
            if match:
                try:
                    citation_count = int(match.group(1))
                    self.logger.debug(f"Found citation count in JSON metadata: {citation_count}")
                    return citation_count
                except ValueError:
                    pass
        
        return None
    
    def extract_multiple_citation_counts(self, doi_urls: List[str], show_progress: bool = True) -> Dict[str, Optional[int]]:
        """Extract citation counts from multiple DOI URLs"""
        results = {}
        total = len(doi_urls)
        
        if show_progress:
            print(f"🔍 Extracting citation counts from {total} DOI links...")
        
        for i, doi_url in enumerate(doi_urls, 1):
            if show_progress and i % 10 == 0:
                print(f"  Progress: {i}/{total} ({i/total*100:.1f}%)")
            
            citation_count = self.extract_citation_count(doi_url)
            results[doi_url] = citation_count
        
        if show_progress:
            found_count = sum(1 for v in results.values() if v is not None)
            print(f"✅ Extracted {found_count}/{total} citation counts")
        
        return results

    def __del__(self):
        """Cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()
