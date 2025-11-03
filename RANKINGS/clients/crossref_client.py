#!/usr/bin/env python3
"""
Crossref API Client for Citation Analysis v7
Specialized for complete article metadata collection from journals
Starting from current year moving backward chronologically
"""

import time
import logging
import requests
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CROSSREF_EMAIL, CROSSREF_BASE_URL, CROSSREF_REQUEST_DELAY,
    CROSSREF_TIMEOUT, CROSSREF_ROWS_PER_REQUEST, CROSSREF_MAX_RETRIES,
    RAW_DATA_DIR, SAVE_RAW_RESPONSES
)

class CrossrefJournalClient:
    """
    Crossref client specialized for collecting complete journal article metadata
    """
    
    def __init__(self):
        self.base_url = CROSSREF_BASE_URL
        self.request_delay = CROSSREF_REQUEST_DELAY
        self.timeout = CROSSREF_TIMEOUT
        self.max_retries = CROSSREF_MAX_RETRIES
        
        self.logger = logging.getLogger(__name__)
        
        # Setup session for connection pooling
        self.session = requests.Session()
        user_agent = f'Citation-Analysis-v7/1.0 (mailto:{CROSSREF_EMAIL})'
        self.session.headers.update({
            'User-Agent': user_agent
        })
        
        self.logger.info("Crossref Journal Client v7 initialized")
    
    def _make_request(self, url: str, params: dict = None) -> Optional[dict]:
        """Make a request to Crossref API with retries and error handling"""
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Making request (attempt {attempt + 1}): {url}")
                if params:
                    self.logger.debug(f"Parameters: {params}")
                
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Save raw response if configured
                    if SAVE_RAW_RESPONSES:
                        self._save_raw_response(url, params, data)
                    
                    # Rate limiting
                    time.sleep(self.request_delay)
                    return data
                    
                elif response.status_code == 429:  # Rate limited
                    wait_time = 5 * (attempt + 1)
                    self.logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    self.logger.error(f"HTTP {response.status_code}: {response.text}")
                    if attempt == self.max_retries - 1:
                        return None
                    time.sleep(2 * (attempt + 1))
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(2 * (attempt + 1))
                
        return None
    
    def _save_raw_response(self, url: str, params: dict, data: dict):
        """Save raw API response for debugging and analysis"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crossref_response_{timestamp}.json"
            filepath = RAW_DATA_DIR / filename
            
            response_data = {
                'timestamp': timestamp,
                'url': url,
                'params': params,
                'response': data
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Error saving raw response: {e}")
    
    def _extract_article_metadata(self, work: dict) -> dict:
        """Extract comprehensive article metadata from Crossref work data"""
        try:
            # Basic information
            doi = work.get('DOI', '')
            title = work.get('title', [''])[0] if work.get('title') else ''
            
            # Authors - comprehensive extraction
            authors = []
            author_details = []
            for author in work.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                orcid = author.get('ORCID', '')
                
                # Full name
                if given and family:
                    full_name = f"{given} {family}"
                elif family:
                    full_name = family
                else:
                    full_name = given
                
                if full_name:
                    authors.append(full_name)
                    author_details.append({
                        'given': given,
                        'family': family,
                        'orcid': orcid,
                        'full_name': full_name
                    })
            
            # Publication date - comprehensive extraction
            published_date = None
            publication_year = None
            
            for date_type in ['published-print', 'published-online', 'published']:
                if date_type in work:
                    date_parts = work[date_type].get('date-parts', [[]])[0]
                    if date_parts and len(date_parts) >= 1:
                        try:
                            year = date_parts[0]
                            month = date_parts[1] if len(date_parts) > 1 else 1
                            day = date_parts[2] if len(date_parts) > 2 else 1
                            published_date = datetime(year, month, day).isoformat()[:10]
                            publication_year = year
                            break
                        except (ValueError, IndexError):
                            continue
            
            # Volume, issue, and page information
            volume = work.get('volume', '')
            issue = work.get('issue', '')
            page_info = work.get('page', '')
            
            # Article number extraction
            article_number = None
            if 'article-number' in work:
                article_number = work['article-number']
            elif page_info and '-' not in page_info:
                # Sometimes article numbers are in the page field
                try:
                    article_number = int(page_info)
                except (ValueError, TypeError):
                    pass
            
            # Page range extraction
            first_page = None
            last_page = None
            if page_info:
                if '-' in page_info:
                    parts = page_info.split('-')
                    first_page = parts[0].strip()
                    last_page = parts[1].strip() if len(parts) > 1 else None
                else:
                    first_page = page_info.strip()
            
            # Citation count
            citation_count = work.get('is-referenced-by-count', 0)
            
            # Publisher information
            publisher = work.get('publisher', '')
            container_title = work.get('container-title', [''])[0] if work.get('container-title') else ''
            
            # Additional metadata
            abstract = work.get('abstract', '')
            language = work.get('language', '')
            subject_areas = work.get('subject', [])
            
            # License information
            license_info = []
            for license_item in work.get('license', []):
                license_info.append({
                    'url': license_item.get('URL', ''),
                    'start': license_item.get('start', {})
                })
            
            # ISSN information
            issn_list = work.get('ISSN', [])
            
            return {
                # Required fields
                'doi': doi,
                'title': title,
                'authors': authors,
                'published_date': published_date,
                'publication_year': publication_year,
                'volume': volume,
                'issue': issue,
                'page': page_info,
                'first_page': first_page,
                'last_page': last_page,
                'article_number': article_number,
                'citation_count': citation_count,
                'publisher': publisher,
                'journal': container_title,
                
                # Additional metadata
                'author_details': author_details,
                'abstract': abstract,
                'language': language,
                'subject_areas': subject_areas,
                'license_info': license_info,
                'issn_list': issn_list,
                
                # Technical metadata
                'crossref_type': work.get('type', ''),
                'crossref_subtype': work.get('subtype', ''),
                'created_date': work.get('created', {}).get('date-time', ''),
                'updated_date': work.get('deposited', {}).get('date-time', ''),
                
                # Source information
                'data_source': 'crossref',
                'collection_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting article metadata: {e}")
            return None
    
    def get_journal_articles_by_year(self, issn: str, year: int, journal_name: str = None) -> List[dict]:
        """
        Get all articles for a specific journal and year
        Uses multiple strategies to handle Crossref pagination limitations
        """
        self.logger.info(f"Collecting articles for ISSN {issn}, year {year}")
        
        # Try different approaches to get all articles
        all_articles = []
        
        # Strategy 1: Try cursor-based pagination first
        articles_cursor = self._collect_with_cursor_pagination(issn, year)
        if articles_cursor:
            all_articles.extend(articles_cursor)
            self.logger.info(f"Cursor pagination collected {len(articles_cursor)} articles")
        
        # Strategy 2: If cursor didn't get everything, try date-based chunking
        if len(all_articles) < 30000:  # Reasonable limit before trying chunking
            articles_chunked = self._collect_with_date_chunking(issn, year)
            if len(articles_chunked) > len(all_articles):
                self.logger.info(f"Date chunking found more articles: {len(articles_chunked)} vs {len(all_articles)}")
                all_articles = articles_chunked
        
        # Remove duplicates based on DOI
        unique_articles = {}
        for article in all_articles:
            doi = article.get('doi', '')
            if doi and doi not in unique_articles:
                unique_articles[doi] = article
        
        final_articles = list(unique_articles.values())
        self.logger.info(f"Collected {len(final_articles)} unique articles for year {year}")
        return final_articles
    
    def _collect_with_cursor_pagination(self, issn: str, year: int) -> List[dict]:
        """Collect articles using cursor pagination"""
        articles = []
        cursor = "*"  # Start with wildcard cursor
        processed_count = 0
        
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        batch_size = 1000
        
        while True:
            params = {
                'filter': f'issn:{issn},from-pub-date:{start_date},until-pub-date:{end_date}',
                'rows': batch_size,
                'cursor': cursor,
                'sort': 'published',
                'order': 'asc'
            }
            
            data = self._make_request(f"{self.base_url}/works", params)
            
            if not data or 'message' not in data:
                break
            
            message = data['message']
            works = message.get('items', [])
            
            if not works:
                break
            
            # Process articles
            for work in works:
                article_metadata = self._extract_article_metadata(work)
                if article_metadata:
                    articles.append(article_metadata)
            
            processed_count += len(works)
            
            # Get next cursor
            next_cursor = message.get('next-cursor')
            if not next_cursor or next_cursor == cursor:
                break
            
            cursor = next_cursor
            
            # Progress logging
            if processed_count % 5000 == 0:
                self.logger.info(f"Cursor pagination: processed {processed_count} articles")
        
        return articles
    
    def _collect_with_date_chunking(self, issn: str, year: int) -> List[dict]:
        """Collect articles by breaking the year into smaller date chunks"""
        articles = []
        
        # Break year into monthly chunks
        for month in range(1, 13):
            if month == 12:
                start_date = f"{year}-{month:02d}-01"
                end_date = f"{year}-12-31"
            else:
                start_date = f"{year}-{month:02d}-01"
                # Calculate last day of month
                if month in [1, 3, 5, 7, 8, 10, 12]:
                    last_day = 31
                elif month in [4, 6, 9, 11]:
                    last_day = 30
                else:  # February
                    last_day = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
                end_date = f"{year}-{month:02d}-{last_day}"
            
            month_articles = self._collect_date_range(issn, start_date, end_date)
            articles.extend(month_articles)
            
            if month_articles:
                self.logger.info(f"Month {month}: collected {len(month_articles)} articles")
        
        return articles
    
    def _collect_date_range(self, issn: str, start_date: str, end_date: str) -> List[dict]:
        """Collect articles for a specific date range using offset pagination"""
        articles = []
        offset = 0
        batch_size = 1000
        
        while offset < 9000:  # Stay within Crossref offset limits
            params = {
                'filter': f'issn:{issn},from-pub-date:{start_date},until-pub-date:{end_date}',
                'rows': batch_size,
                'offset': offset,
                'sort': 'published',
                'order': 'asc'
            }
            
            data = self._make_request(f"{self.base_url}/works", params)
            
            if not data or 'message' not in data:
                break
            
            message = data['message']
            works = message.get('items', [])
            
            if not works:
                break
            
            # Process articles
            for work in works:
                article_metadata = self._extract_article_metadata(work)
                if article_metadata:
                    articles.append(article_metadata)
            
            offset += len(works)
            
            # If we got fewer results than requested, we've reached the end
            if len(works) < batch_size:
                break
        
        return articles
    
    def get_journal_info(self, issn: str) -> Optional[dict]:
        """Get journal information from Crossref"""
        params = {'filter': f'issn:{issn}'}
        
        data = self._make_request(f"{self.base_url}/journals", params)
        
        if data and 'message' in data:
            items = data['message'].get('items', [])
            if items:
                return items[0]
        
        return None