#!/usr/bin/env python3
"""
Semantic Scholar API Client for Citation Analysis v2
Simplified version without dotenv dependency
"""

import time
import logging
from typing import Dict, List, Optional
from semanticscholar import SemanticScholar
import sys
import os

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SEMANTIC_SCHOLAR_API_KEY

class SemanticScholarClient:
    """Client for interacting with Semantic Scholar API"""
    
    def __init__(self, request_delay=1.0, batch_size=100):
        """Initialize the client"""
        self.api_key = SEMANTIC_SCHOLAR_API_KEY
        self.request_delay = request_delay
        self.batch_size = batch_size
        
        if self.api_key:
            self.sch = SemanticScholar(api_key=self.api_key)
            print("✅ Using Semantic Scholar API with authentication")
        else:
            self.sch = SemanticScholar()
            print("⚠️  Using Semantic Scholar API without authentication (rate limited)")
        
        self.logger = logging.getLogger(__name__)
        self.requests_made = 0
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.request_delay:
            sleep_time = self.request_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.requests_made += 1
    
    def get_paper_by_doi(self, doi: str, fields=None):
        """Get paper information by DOI"""
        if fields is None:
            fields = ['citationCount', 'title', 'year', 'paperId', 'externalIds']
        
        try:
            self._rate_limit()
            clean_doi = doi.replace('DOI:', '').strip()
            paper = self.sch.get_paper(f'DOI:{clean_doi}', fields=fields)
            
            if paper and hasattr(paper, 'paperId'):
                return {
                    'paperId': paper.paperId,
                    'doi': clean_doi,
                    'title': getattr(paper, 'title', ''),
                    'year': getattr(paper, 'year', None),
                    'citationCount': getattr(paper, 'citationCount', 0),
                    'externalIds': getattr(paper, 'externalIds', {})
                }
            else:
                self.logger.warning(f"Paper not found for DOI: {clean_doi}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching paper {doi}: {e}")
            return None
    
    def get_papers_by_dois(self, dois, fields=None):
        """Get multiple papers by DOIs using batch processing"""
        if fields is None:
            fields = ['citationCount', 'title', 'year', 'paperId', 'externalIds']
        
        results = {}
        
        # Process in batches to respect rate limits
        for i in range(0, len(dois), self.batch_size):
            batch = dois[i:i + self.batch_size]
            
            self.logger.debug(f"Processing batch {i//self.batch_size + 1}: {len(batch)} DOIs")
            
            try:
                # Prepare DOI identifiers for the API
                batch_identifiers = []
                for doi in batch:
                    clean_doi = doi.replace('DOI:', '').strip()
                    batch_identifiers.append(clean_doi)
                
                # Get papers for this batch
                papers = self.sch.get_papers(batch_identifiers, fields=fields)
                
                # Map results back to original DOIs
                for j, paper in enumerate(papers):
                    original_doi = batch[j]
                    if paper and hasattr(paper, 'paperId'):
                        result = {
                            'paperId': paper.paperId,
                            'doi': original_doi,
                            'title': getattr(paper, 'title', ''),
                            'year': getattr(paper, 'year', None),
                            'citationCount': getattr(paper, 'citationCount', 0),
                            'externalIds': getattr(paper, 'externalIds', {})
                        }
                        results[original_doi] = result
                    else:
                        results[original_doi] = None
                
                # Rate limit between batches
                if i + self.batch_size < len(dois):
                    time.sleep(self.request_delay)
                    
            except Exception as e:
                self.logger.error(f"Error fetching batch {i//self.batch_size + 1}: {e}")
                # Set all papers in this batch to None
                for doi in batch:
                    results[doi] = None
        
        return results
    
    def get_citation_counts_for_dois(self, dois):
        """Get citation counts for multiple DOIs"""
        self.logger.info(f"Fetching citation counts for {len(dois)} DOIs using Semantic Scholar")
        
        # Get paper details with citation counts
        paper_details = self.get_papers_by_dois(dois, fields=['citationCount', 'externalIds'])
        
        # Extract citation counts
        citation_counts = {}
        found_count = 0
        
        for doi in dois:
            paper_data = paper_details.get(doi)
            if paper_data and paper_data.get('citationCount') is not None:
                citation_counts[doi] = paper_data['citationCount']
                found_count += 1
            else:
                citation_counts[doi] = None
        
        self.logger.info(f"Found citation counts for {found_count}/{len(dois)} papers")
        return citation_counts
