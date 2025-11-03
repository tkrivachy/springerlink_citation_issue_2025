#!/usr/bin/env python3
"""
Springer API Client for Citation Analysis v2
Handles JATS XML format responses and extracts article numbers from elocation-id
"""

import time
import logging
import requests
import json
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom
import sys
import os
from datetime import datetime

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (API_KEY_META, API_KEY_OPENACCESS, SPRINGER_BASE_URL, 
                   SPRINGER_BATCH_SIZE, SPRINGER_REQUEST_DELAY)

class SpringerClient:
    """Client for interacting with Springer Nature API"""
    
    def __init__(self):
        self.base_url = SPRINGER_BASE_URL
        self.api_key_meta = API_KEY_META
        self.api_key_openaccess = API_KEY_OPENACCESS or API_KEY_META
        self.batch_size = SPRINGER_BATCH_SIZE
        self.request_delay = SPRINGER_REQUEST_DELAY
        
        # Rate limiting state: track if we should use openaccess API or fallback to meta
        self.use_openaccess = True  # Start with openaccess when available
        
        self.logger = logging.getLogger(__name__)
        
        # Setup session for connection pooling
        self.session = requests.Session()
        # Note: Using default User-Agent to avoid 403 premium access errors
        
        self.logger.info("Springer API client initialized")
    
    def _make_request(self, endpoint: str, params: Dict, format_type: str = "jats") -> Optional[str]:
        """Make a request to Springer API and return raw response content"""
        try:
            # Debug logging
            self.logger.debug(f"Making request to: {endpoint}")
            self.logger.debug(f"Params: {params}")
            
            response = self.session.get(endpoint, params=params, timeout=30)
            
            if response.status_code == 200:
                time.sleep(self.request_delay)
                return response.text
            elif response.status_code == 404:
                self.logger.warning(f"No content found for query: {params}")
                return None
            elif response.status_code == 429:
                # Rate limit hit - check if we were using openaccess API
                if "/openaccess/" in endpoint and self.use_openaccess:
                    self.logger.warning("Rate limit hit on openaccess API, switching to meta API for future requests")
                    self.use_openaccess = False
                    
                    # Retry with meta API immediately
                    meta_endpoint = endpoint.replace("/openaccess/", "/meta/v2/")
                    params['api_key'] = self.api_key_meta
                    
                    self.logger.info(f"Retrying with meta API: {meta_endpoint}")
                    return self._make_request(meta_endpoint, params, format_type)
                else:
                    self.logger.error(f"Rate limit hit on meta API (HTTP 429): {response.text}")
                    return None
            else:
                self.logger.error(f"HTTP {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return None
    
    def _parse_jats_xml(self, xml_content: str) -> List[Dict]:
        """Parse JATS XML response and extract article metadata including elocation-id"""
        try:
            root = ET.fromstring(xml_content)
            articles = []
            
            # Find all article elements
            for article_elem in root.findall('.//article'):
                article_data = {}
                
                # Extract DOI
                doi_elem = article_elem.find('.//article-id[@pub-id-type="doi"]')
                if doi_elem is not None:
                    article_data['doi'] = doi_elem.text
                
                # Extract title
                title_elem = article_elem.find('.//article-title')
                if title_elem is not None:
                    article_data['title'] = title_elem.text
                
                # Extract elocation-id (this is the article number!)
                elocation_elem = article_elem.find('.//elocation-id')
                if elocation_elem is not None:
                    article_data['article_number'] = elocation_elem.text
                
                # Extract publication date
                pub_date_elem = article_elem.find('.//pub-date[@date-type="pub"][@publication-format="electronic"]')
                if pub_date_elem is not None:
                    day = pub_date_elem.find('day')
                    month = pub_date_elem.find('month') 
                    year = pub_date_elem.find('year')
                    
                    if day is not None and month is not None and year is not None:
                        article_data['publication_date'] = f"{year.text}-{month.text.zfill(2)}-{day.text.zfill(2)}"
                
                # Extract volume and issue
                volume_elem = article_elem.find('.//volume')
                if volume_elem is not None:
                    article_data['volume'] = volume_elem.text
                    
                issue_elem = article_elem.find('.//issue')
                if issue_elem is not None:
                    article_data['issue'] = issue_elem.text
                
                # Extract journal information
                journal_title_elem = article_elem.find('.//journal-title')
                if journal_title_elem is not None:
                    article_data['journal'] = journal_title_elem.text
                
                issn_elem = article_elem.find('.//issn')
                if issn_elem is not None:
                    article_data['issn'] = issn_elem.text
                
                # Extract authors
                authors = []
                for contrib_elem in article_elem.findall('.//contrib[@contrib-type="author"]'):
                    name_elem = contrib_elem.find('.//name')
                    if name_elem is not None:
                        surname_elem = name_elem.find('surname')
                        given_names_elem = name_elem.find('given-names')
                        if surname_elem is not None and given_names_elem is not None:
                            authors.append(f"{given_names_elem.text} {surname_elem.text}")
                
                if authors:
                    article_data['authors'] = authors
                
                # Only add articles with DOI
                if 'doi' in article_data:
                    articles.append(article_data)
            
            return articles
            
        except ET.ParseError as e:
            self.logger.error(f"XML parse error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error parsing JATS XML: {e}")
            return []
    
    def _get_api_endpoint_and_key(self, is_open_access: bool = False) -> Tuple[str, str]:
        """
        Get the appropriate API endpoint and key based on journal configuration and rate limit status
        
        Args:
            is_open_access: Whether the journal is configured as open access
            
        Returns:
            Tuple of (endpoint_url, api_key)
        """
        # Determine which API to use
        should_use_openaccess = (is_open_access and 
                               self.use_openaccess and 
                               self.api_key_openaccess and
                               self.api_key_openaccess != self.api_key_meta)
        
        if should_use_openaccess:
            endpoint = f"{self.base_url}/openaccess/jats"
            api_key = self.api_key_openaccess
            self.logger.debug("Using openaccess API endpoint")
        else:
            endpoint = f"{self.base_url}/meta/v2/jats"
            api_key = self.api_key_meta
            self.logger.debug("Using meta API endpoint")
        
        return endpoint, api_key
    
    def search_articles_by_date(self, issn: str, year: int, month: int, day: int, is_open_access: bool = False) -> List[Dict]:
        """Search for articles published on a specific date using JATS format"""
        query_date = f"{year:04d}-{month:02d}-{day:02d}"
        
        # Get appropriate endpoint and API key
        endpoint, api_key = self._get_api_endpoint_and_key(is_open_access)
        
        # params = {
        #     'api_key': api_key,
        #     'q': f'issn:{issn} AND onlinedatefrom:{query_date} AND onlinedateto:{query_date} AND type:Journal',
        #     's': 1,  # start position
        #     'p': self.batch_size,  # page size
        #     'sort': 'date',
        #     'order': 'desc'
        # }
        
        params = {
            'api_key': api_key,
            'q': f'issn:{issn} AND datefrom:{query_date} AND dateto:{query_date} AND type:Journal',
            's': 1,  # start position
            'p': self.batch_size,  # page size
            'sort': 'date',
            'order': 'desc'
        }

        self.logger.debug(f"Searching for articles on {query_date} in journal {issn}")
        
        all_articles = []
        start_pos = 1
        
        while True:
            params['s'] = start_pos  # start position
            xml_content = self._make_request(endpoint, params)
            
            if xml_content:
                articles = self._parse_jats_xml(xml_content)
                if not articles:  # No more articles
                    break
                all_articles.extend(articles)
                
                # Check if we got fewer articles than batch size (indicates last page)
                if len(articles) < self.batch_size:
                    break
                    
                start_pos += self.batch_size
            else:
                break
        
        self.logger.info(f"Found {len(all_articles)} articles on {query_date}")
        return all_articles
    
    def search_articles_by_month(self, issn: str, year: int, month: int, is_open_access: bool = False) -> List[Dict]:
        """Search for articles published in a specific month using JATS format"""
        # Use date range query for the entire month
        start_date = f"{year:04d}-{month:02d}-01"
        
        # Calculate end date (last day of month)
        if month == 12:
            end_date = f"{year:04d}-12-31"
        else:
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
        
        return self.search_articles_by_date_range_str(issn, start_date, end_date, is_open_access)
    
    def search_articles_by_date_range(self, issn: str, year: int, start_month: int, start_day: int, 
                                     end_month: int, end_day: int, is_open_access: bool = False) -> List[Dict]:
        """Search for articles published in a specific date range using JATS format"""
        start_date = f"{year:04d}-{start_month:02d}-{start_day:02d}"
        end_date = f"{year:04d}-{end_month:02d}-{end_day:02d}"
        
        self.logger.debug(f"Searching for articles from {start_date} to {end_date} in journal {issn}")
        
        return self.search_articles_by_date_range_str(issn, start_date, end_date, is_open_access)
    
    def search_articles_by_date_range_str(self, issn: str, start_date: str, end_date: str, is_open_access: bool = False) -> List[Dict]:
        """Search for articles published between two dates using JATS format"""
        # Get appropriate endpoint and API key
        endpoint, api_key = self._get_api_endpoint_and_key(is_open_access)
        
        params = {
            'api_key': api_key,
            'q': f'issn:{issn} AND onlinedatefrom:{start_date} AND onlinedateto:{end_date} AND type:Journal',
            's': 1,
            'p': self.batch_size,
            'sort': 'date',
            'order': 'desc'
        }
        
        self.logger.debug(f"Searching for articles from {start_date} to {end_date} in journal {issn}")
        
        all_articles = []
        start_pos = 1
        
        while True:
            params['s'] = start_pos
            xml_content = self._make_request(endpoint, params)
            
            if xml_content:
                articles = self._parse_jats_xml(xml_content)
                if not articles:
                    break
                
                all_articles.extend(articles)
                
                # Check if we need to continue (basic check)
                if len(articles) < self.batch_size:
                    break
                    
                start_pos += self.batch_size
            else:
                break
        
        self.logger.info(f"Found {len(all_articles)} articles from {start_date} to {end_date}")
        return all_articles
    
    def find_article_number_1(self, issn: str, year: int, start_month: int = 1, start_day: int = 1, is_open_access: bool = False) -> Optional[Tuple[Dict, str]]:
        """Find Article #1 for a given year by checking dates starting from January"""
        return self.find_article_number_1_with_cache(issn, year, start_month, start_day, is_open_access)[0:2]
    
    def find_article_number_1_with_cache(self, issn: str, year: int, start_month: int = 1, start_day: int = 1, is_open_access: bool = False) -> Tuple[Optional[Dict], Optional[str], List[Dict]]:
        """Find Article #1 and return cached articles for reuse in comparison search"""
        self.logger.info(f"Searching for Article #1 in {year} for journal {issn}")
        
        cached_articles = []
        
        # Special handling for first year of journal
        if start_month != 1 or start_day != 1:
            # Check the journal start date first
            articles = self.search_articles_by_date(issn, year, start_month, start_day, is_open_access)
            cached_articles.extend(articles)
            if articles:
                date_str = f"{year}-{start_month:02d}-{start_day:02d}"
                # Look for article number 1
                for article in articles:
                    if article.get('article_number') == '1':
                        self.logger.info(f"Found Article #1 on {date_str}")
                        return article, date_str, cached_articles
            
            # For first year, fall back to day-by-day search from start date
            result = self._find_article_1_day_by_day(issn, year, start_month, start_day, is_open_access)
            if result:
                return result[0], result[1], cached_articles
            else:
                return None, None, cached_articles
        
        # For regular years, use optimized search strategy
        # Step 1: First check January 2nd
        jan_2_articles = self.search_articles_by_date(issn, year, 1, 2, is_open_access)
        cached_articles.extend(jan_2_articles)
        
        if jan_2_articles:
            for article in jan_2_articles:
                if article.get('article_number') == '1':
                    self.logger.info(f"Found Article #1 on {year}-01-02")
                    return article, f"{year}-01-02", cached_articles
        
        # Step 2: If not found on Jan 2nd, try January 1st
        self.logger.info("Not found on Jan 2nd, trying Jan 1st")
        jan_1_articles = self.search_articles_by_date(issn, year, 1, 1, is_open_access)
        cached_articles.extend(jan_1_articles)
        
        if jan_1_articles:
            for article in jan_1_articles:
                if article.get('article_number') == '1':
                    self.logger.info(f"Found Article #1 on {year}-01-01")
                    return article, f"{year}-01-01", cached_articles
        
        # Step 3: If not found on Jan 1st or 2nd, do week-by-week search for 6 weeks
        self.logger.info("Not found on Jan 1st or 2nd, starting 6-week weekly search")
        
        # Define 6 weeks starting from Jan 3rd
        weekly_searches = [
            (1, 3, 9),    # Week 1: Jan 3-9
            (1, 10, 16),  # Week 2: Jan 10-16
            (1, 17, 23),  # Week 3: Jan 17-23
            (1, 24, 31),  # Week 4: Jan 24-31
            (2, 1, 7),    # Week 5: Feb 1-7
            (2, 8, 14),   # Week 6: Feb 8-14
        ]
        
        for month, start_day, end_day in weekly_searches:
            # Handle month boundaries properly
            import calendar
            days_in_month = calendar.monthrange(year, month)[1]
            actual_end_day = min(end_day, days_in_month)
            
            week_articles = self.search_articles_by_date_range(issn, year, month, start_day, month, actual_end_day, is_open_access)
            cached_articles.extend(week_articles)
            
            # Check if Article #1 is in this week
            for article in week_articles:
                if article.get('article_number') == '1':
                    pub_date = article.get('publication_date')
                    self.logger.info(f"Found Article #1 on {pub_date} during week-by-week search")
                    return article, pub_date, cached_articles
        
        # Step 4: If not found in 6-week search, continue with month-by-month search
        # Start from February 15th (after the 6-week search) and continue month by month
        self.logger.info("Not found in 6-week search, starting month-by-month search from mid-February")
        
        # First, finish February if needed (from Feb 15th onwards)
        try:
            import calendar
            days_in_feb = calendar.monthrange(year, 2)[1]
            if days_in_feb > 14:  # February has more than 14 days
                feb_remainder_articles = self.search_articles_by_date_range(issn, year, 2, 15, 2, days_in_feb, is_open_access)
                cached_articles.extend(feb_remainder_articles)
                
                for article in feb_remainder_articles:
                    if article.get('article_number') == '1':
                        pub_date = article.get('publication_date')
                        self.logger.info(f"Found Article #1 on {pub_date} during February remainder search")
                        return article, pub_date, cached_articles
        except Exception as e:
            self.logger.error(f"Error checking February remainder: {e}")
        
        # Continue with full months from March onwards
        for month in range(3, 13):
            try:
                self.logger.info(f"Searching {year}-{month:02d} (full month) for Article #1")
                
                month_articles = self.search_articles_by_month(issn, year, month, is_open_access)
                cached_articles.extend(month_articles)
                
                for article in month_articles:
                    if article.get('article_number') == '1':
                        pub_date = article.get('publication_date')
                        self.logger.info(f"Found Article #1 on {pub_date} during month-by-month search")
                        return article, pub_date, cached_articles
                            
            except Exception as e:
                self.logger.error(f"Error checking {year}-{month:02d}: {e}")
                continue
        
        self.logger.warning(f"Article #1 not found for year {year}")
        return None, None, cached_articles
    
    def _find_article_1_day_by_day(self, issn: str, year: int, start_month: int = 1, start_day: int = 1, is_open_access: bool = False) -> Optional[Tuple[Dict, str]]:
        """Fallback method: Find Article #1 using day-by-day search"""
        self.logger.info(f"Using day-by-day search for Article #1 starting from {year}-{start_month:02d}-{start_day:02d}")
        
        # Check from start date through January 31st
        current_month = start_month
        current_day = start_day
        
        while current_month <= 12:
            max_day = 31 if current_month == 1 else 28  # Simplified for now
            if current_month == 2:
                import calendar
                max_day = 29 if calendar.isleap(year) else 28
            elif current_month in [4, 6, 9, 11]:
                max_day = 30
            
            while current_day <= max_day:
                try:
                    articles = self.search_articles_by_date(issn, year, current_month, current_day, is_open_access)
                    if articles:
                        date_str = f"{year}-{current_month:02d}-{current_day:02d}"
                        # Look for article number 1
                        for article in articles:
                            if article.get('article_number') == '1':
                                self.logger.info(f"Found Article #1 on {date_str}")
                                return article, date_str
                                
                except Exception as e:
                    self.logger.error(f"Error checking {year}-{current_month:02d}-{current_day:02d}: {e}")
                
                current_day += 1
            
            # Move to next month
            current_month += 1
            current_day = 1
            
            # For regular search, only check January
            if start_month == 1 and start_day == 1 and current_month > 1:
                break
        
        return None, None
    
    def collect_comparison_articles(self, issn: str, year: int, target_date: str, min_articles: int = 15, 
                                   cached_articles: List[Dict] = None, is_open_access: bool = False) -> List[Dict]:
        """Collect articles for comparison, reusing cached data from Article #1 search when possible"""
        self.logger.info(f"Collecting comparison articles for {year}, starting from {target_date}")
        
        # Parse target date
        year_val, month_val, day_val = map(int, target_date.split('-'))
        
        # First, check if we can reuse cached articles from Article #1 search
        if cached_articles:
            # Filter articles published on or after Article #1's date (only newer articles)
            comparison_candidates = [
                article for article in cached_articles 
                if article.get('publication_date', '') >= target_date
            ]
            
            self.logger.info(f"Found {len(comparison_candidates)} articles from cached data on/after {target_date}")
            
            if len(comparison_candidates) >= min_articles:
                # We have enough articles from the cached search, use ALL of them (not just minimum)
                self.logger.info(f"Using all {len(comparison_candidates)} cached articles - no additional API calls needed")
                return comparison_candidates
            else:
                # We have some cached articles but need more
                self.logger.info(f"Only {len(comparison_candidates)} cached articles, need {min_articles - len(comparison_candidates)} more")
                return self._expand_comparison_articles_from_date(
                    issn, year_val, target_date, min_articles, comparison_candidates, is_open_access
                )
        
        # No cached articles available, use traditional search starting from target date
        return self._expand_comparison_articles_from_date(issn, year_val, target_date, min_articles, None, is_open_access)
    
    def _collect_comparison_articles_original(self, issn: str, year: int, target_date: str, min_articles: int = 15, is_open_access: bool = False) -> List[Dict]:
        """Original comparison article collection logic for fallback cases"""
        # Parse target date
        year_val, month_val, day_val = map(int, target_date.split('-'))
        
        # First, get articles from the same day
        articles = self.search_articles_by_date(issn, year_val, month_val, day_val, is_open_access)
        
        if len(articles) >= min_articles:
            self.logger.info(f"Found {len(articles)} articles on same day - continuing to search entire year")
        else:
            self.logger.info(f"Only {len(articles)} articles on same day, expanding to year")
        
        
        # Get all articles from the same month and continue to end of year
        all_articles = articles.copy()  # Start with same-day articles
        current_month = month_val
        
        while current_month <= 12 and len(all_articles) < min_articles:
            if current_month == month_val:
                # For the target month, get the full month (may include same-day articles again, we'll dedupe later)
                month_articles = self.search_articles_by_month(issn, year_val, current_month, is_open_access)
            else:
                month_articles = self.search_articles_by_month(issn, year_val, current_month, is_open_access)
                
            all_articles.extend(month_articles)
            
            self.logger.info(f"Total articles after including {year_val}-{current_month:02d}: {len(all_articles)}")
            
            # Check if we have enough articles now
            if len(all_articles) >= min_articles:
                self.logger.info(f"Reached minimum articles requirement ({len(all_articles)} >= {min_articles}), stopping search")
                break
                
            current_month += 1
        
        self.logger.info(f"Collected {len(all_articles)} articles for comparison")
        return all_articles
    
    def _expand_comparison_articles_from_date(self, issn: str, year: int, target_date: str, 
                                            min_articles: int, existing_articles: List[Dict] = None, is_open_access: bool = False) -> List[Dict]:
        """Expand comparison articles starting from target date using intelligent day estimation"""
        year_val, month_val, day_val = map(int, target_date.split('-'))
        
        # Start with existing articles if provided
        all_articles = existing_articles.copy() if existing_articles else []
        
        # Continue processing regardless of existing article count to search the entire year
        
        # Check if we need articles from the same day as target_date
        same_day_articles = [a for a in all_articles if a.get('publication_date') == target_date]
        articles_on_target_day = len(same_day_articles)
        
        if not same_day_articles:
            # Get articles from the target date itself
            day_articles = self.search_articles_by_date(issn, year_val, month_val, day_val, is_open_access)
            # Only keep articles that are not Article #1 (avoid including Article #1 in comparison)
            day_articles = [a for a in day_articles if a.get('article_number') != '1']
            all_articles.extend(day_articles)
            articles_on_target_day = len(day_articles)
            
            self.logger.info(f"Added {len(day_articles)} articles from {target_date}")
            
            # Continue processing to search entire year regardless of current count
        
        # Calculate how many more articles we would need for minimum (but search entire year anyway)
        articles_needed = max(0, min_articles - len(all_articles))
        
        # Estimate days needed based on articles per day from target date (for initial search strategy)
        if articles_on_target_day > 0:
            estimated_days_needed = max(30, (articles_needed + articles_on_target_day - 1) // articles_on_target_day) if articles_needed > 0 else 30
            estimated_days_needed += 1  # Add buffer day as requested
            
            if articles_needed > 0:
                self.logger.info(f"Need {articles_needed} more articles to reach minimum. Target day had {articles_on_target_day} articles. "
                               f"Estimating {estimated_days_needed} days for initial search")
            else:
                self.logger.info(f"Already have minimum articles, but searching {estimated_days_needed} more days to find all available articles")
            
            # Calculate end date for the estimated period
            from datetime import datetime, timedelta
            start_search_date = datetime(year_val, month_val, day_val + 1)  # Start from next day
            end_search_date = start_search_date + timedelta(days=estimated_days_needed - 1)
            
            # Make sure we don't go beyond the year
            if end_search_date.year > year_val:
                end_search_date = datetime(year_val, 12, 31)
            
            # Search the estimated date range
            estimated_articles = self.search_articles_by_date_range_str(
                issn, 
                start_search_date.strftime("%Y-%m-%d"),
                end_search_date.strftime("%Y-%m-%d"),
                is_open_access
            )
            
            all_articles.extend(estimated_articles)
            total_days_searched = (end_search_date - datetime(year_val, month_val, day_val)).days + 1
            
            self.logger.info(f"Found {len(estimated_articles)} articles in estimated {estimated_days_needed} day period")
            
            # Check if we have enough articles to meet minimum requirement
            if len(all_articles) >= min_articles:
                self.logger.info(f"Already have minimum articles ({len(all_articles)} >= {min_articles}), stopping search to save API quota")
            else:
                articles_still_needed = min_articles - len(all_articles)
                self.logger.info(f"Still need {articles_still_needed} articles to reach minimum. "
                               f"Continuing search until end of year {year_val}")
                
                # Search from next day until end of year
                next_start_date = end_search_date + timedelta(days=1)
                year_end_date = datetime(year_val, 12, 31)
                
                if next_start_date.year == year_val and next_start_date <= year_end_date:
                    remaining_articles = self.search_articles_by_date_range_str(
                        issn,
                        next_start_date.strftime("%Y-%m-%d"),
                        year_end_date.strftime("%Y-%m-%d"),
                        is_open_access
                    )
                    
                    all_articles.extend(remaining_articles)
                    days_searched = (year_end_date - next_start_date).days + 1
                    self.logger.info(f"Found {len(remaining_articles)} additional articles searching until end of year ({days_searched} days)")
        
        else:
            # No articles on target day - fall back to week-by-week search
            self.logger.info("No articles on target day, falling back to week-by-week search")
            current_month = month_val
            current_day = day_val + 1
            
            import calendar
            
            while current_month <= 12 and len(all_articles) < min_articles:
                days_in_month = calendar.monthrange(year_val, current_month)[1]
                
                # Search week by week in current month (stop when we have enough articles)
                while current_day <= days_in_month and len(all_articles) < min_articles:
                    week_end = min(current_day + 6, days_in_month)
                    
                    week_articles = self.search_articles_by_date_range(
                        issn, year_val, current_month, current_day, current_month, week_end
                    )
                    all_articles.extend(week_articles)
                    
                    self.logger.info(f"Added {len(week_articles)} articles from week {current_month:02d}-{current_day:02d} to {current_month:02d}-{week_end:02d} (total: {len(all_articles)})")
                    
                    current_day = week_end + 1
                
                # Move to next month
                current_month += 1
                current_day = 1
        
        self.logger.info(f"Collected {len(all_articles)} total articles for comparison")
        return all_articles
    
    def _get_first_n_days_articles(self, articles: List[Dict], min_articles: int) -> List[Dict]:
        """Get articles from first N days that meet minimum article requirement"""
        # Sort articles by publication date
        sorted_articles = sorted(articles, key=lambda x: x.get('publication_date', ''))
        
        if len(sorted_articles) <= min_articles:
            return sorted_articles
        
        # Find the first N days that give us at least min_articles
        articles_by_date = {}
        for article in sorted_articles:
            pub_date = article.get('publication_date')
            if pub_date:
                if pub_date not in articles_by_date:
                    articles_by_date[pub_date] = []
                articles_by_date[pub_date].append(article)
        
        # Get first N days chronologically
        sorted_dates = sorted(articles_by_date.keys())
        selected_articles = []
        
        for date in sorted_dates:
            selected_articles.extend(articles_by_date[date])
            if len(selected_articles) >= min_articles:
                break
        
        self.logger.info(f"Selected {len(selected_articles)} articles from first {len([d for d in sorted_dates if any(a['publication_date'] == d for a in selected_articles)])} days of January")
        return selected_articles
