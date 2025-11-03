#!/usr/bin/env python3
"""
Main Article Collector for Citation Analysis v7
Collects complete article metadata from journals using only Crossref API
Starting from current year (2025) and moving backward chronologically
"""

import logging
import json
import csv
from datetime import datetime
from pathlib import Path
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_JOURNAL, JOURNALS, START_YEAR, END_YEAR,
    RESULTS_DIR, LOG_LEVEL, LOG_FORMAT, LOG_FILE,
    SAVE_AS_JSON, SAVE_AS_CSV, REQUIRED_FIELDS, ACTIVE_JOURNAL_KEY
)
from clients.crossref_client import CrossrefJournalClient

class ArticleCollector:
    """Main class for collecting article metadata"""
    
    def __init__(self, journal_key: str = None):
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL),
            format=LOG_FORMAT,
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Setup journal
        if journal_key and journal_key in JOURNALS:
            self.journal = JOURNALS[journal_key]
            self.journal_key = journal_key
        else:
            self.journal = DEFAULT_JOURNAL
            self.journal_key = ACTIVE_JOURNAL_KEY
        
        # Initialize Crossref client
        self.crossref_client = CrossrefJournalClient()
        
        self.logger.info(f"Article Collector v7 initialized for {self.journal['name']}")
        self.logger.info(f"ISSN: {self.journal['issn']}")
        self.logger.info(f"Collection period: {START_YEAR} to {END_YEAR}")
    
    def collect_all_articles(self) -> dict:
        """
        Collect all articles for the journal from START_YEAR to END_YEAR
        Moving backward chronologically
        """
        self.logger.info("Starting complete article collection")
        
        all_articles = {}
        total_articles_collected = 0
        
        # Collect year by year, starting from current year
        for year in range(START_YEAR, END_YEAR - 1, -1):
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Collecting articles for year {year}")
            self.logger.info(f"{'='*50}")
            
            try:
                year_articles = self.crossref_client.get_journal_articles_by_year(
                    issn=self.journal['issn'],
                    year=year,
                    journal_name=self.journal['name']
                )
                
                if year_articles:
                    all_articles[str(year)] = year_articles
                    total_articles_collected += len(year_articles)
                    self.logger.info(f"Year {year}: {len(year_articles)} articles collected")
                    
                    # Save intermediate results
                    self._save_year_results(year, year_articles)
                else:
                    self.logger.warning(f"No articles found for year {year}")
                    all_articles[str(year)] = []
                
            except Exception as e:
                self.logger.error(f"Error collecting articles for year {year}: {e}")
                all_articles[str(year)] = []
                continue
        
        self.logger.info(f"\nCollection completed!")
        self.logger.info(f"Total articles collected: {total_articles_collected}")
        self.logger.info(f"Years processed: {START_YEAR} to {END_YEAR}")
        
        # Save final results
        self._save_final_results(all_articles)
        
        return all_articles
    
    def _save_year_results(self, year: int, articles: list):
        """Save results for a specific year"""
        try:
            # Create year-specific directory
            year_dir = RESULTS_DIR / str(year)
            year_dir.mkdir(exist_ok=True)
            
            # Save as JSON
            if SAVE_AS_JSON:
                json_file = year_dir / f"{self.journal_key}_{year}_articles.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(articles, f, indent=2, ensure_ascii=False)
                self.logger.debug(f"Saved {len(articles)} articles to {json_file}")
            
            # Save as CSV
            if SAVE_AS_CSV and articles:
                csv_file = year_dir / f"{self.journal_key}_{year}_articles.csv"
                self._save_articles_to_csv(articles, csv_file)
                self.logger.debug(f"Saved {len(articles)} articles to {csv_file}")
                
        except Exception as e:
            self.logger.error(f"Error saving year {year} results: {e}")
    
    def _save_final_results(self, all_articles: dict):
        """Save final consolidated results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save complete JSON
            if SAVE_AS_JSON:
                json_file = RESULTS_DIR / f"{self.journal_key}_complete_{timestamp}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(all_articles, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Complete results saved to {json_file}")
            
            # Save complete CSV
            if SAVE_AS_CSV:
                csv_file = RESULTS_DIR / f"{self.journal_key}_complete_{timestamp}.csv"
                all_articles_list = []
                for year, articles in all_articles.items():
                    all_articles_list.extend(articles)
                
                if all_articles_list:
                    self._save_articles_to_csv(all_articles_list, csv_file)
                    self.logger.info(f"Complete CSV results saved to {csv_file}")
            
            # Save summary statistics
            self._save_collection_summary(all_articles, timestamp)
            
        except Exception as e:
            self.logger.error(f"Error saving final results: {e}")
    
    def _save_articles_to_csv(self, articles: list, filepath: Path):
        """Save articles to CSV format"""
        if not articles:
            return
        
        # Get all unique fields from all articles
        all_fields = set()
        for article in articles:
            all_fields.update(article.keys())
        
        # Prioritize required fields
        fieldnames = []
        for field in REQUIRED_FIELDS:
            if field in all_fields:
                fieldnames.append(field)
        
        # Add remaining fields
        for field in sorted(all_fields):
            if field not in fieldnames:
                fieldnames.append(field)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for article in articles:
                # Handle list fields by converting to string
                row = {}
                for field in fieldnames:
                    value = article.get(field, '')
                    if isinstance(value, list):
                        row[field] = '; '.join(str(item) for item in value)
                    elif isinstance(value, dict):
                        row[field] = str(value)
                    else:
                        row[field] = value
                writer.writerow(row)
    
    def _save_collection_summary(self, all_articles: dict, timestamp: str):
        """Save collection summary statistics"""
        try:
            summary = {
                'collection_info': {
                    'journal': self.journal,
                    'collection_timestamp': timestamp,
                    'start_year': START_YEAR,
                    'end_year': END_YEAR,
                    'total_years': START_YEAR - END_YEAR + 1
                },
                'statistics': {
                    'total_articles': sum(len(articles) for articles in all_articles.values()),
                    'years_with_data': len([year for year, articles in all_articles.items() if articles]),
                    'years_without_data': len([year for year, articles in all_articles.items() if not articles])
                },
                'year_breakdown': {}
            }
            
            for year, articles in all_articles.items():
                summary['year_breakdown'][year] = {
                    'article_count': len(articles),
                    'total_citations': sum(article.get('citation_count', 0) for article in articles),
                    'volumes': list(set(article.get('volume', '') for article in articles if article.get('volume')))
                }
            
            summary_file = RESULTS_DIR / f"{self.journal_key}_summary_{timestamp}.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Collection summary saved to {summary_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving collection summary: {e}")

def main():
    """Main execution function"""
    print("Citation Analysis v7 - Article Collector")
    print("=" * 50)
    print(f"Journal: {DEFAULT_JOURNAL['name']}")
    print(f"ISSN: {DEFAULT_JOURNAL['issn']}")
    print(f"Collection period: {START_YEAR} to {END_YEAR}")
    print("=" * 50)
    
    # Initialize collector
    collector = ArticleCollector()
    
    # Start collection
    try:
        results = collector.collect_all_articles()
        
        total_articles = sum(len(articles) for articles in results.values())
        print(f"\nCollection completed successfully!")
        print(f"Total articles collected: {total_articles}")
        print(f"Results saved in: {RESULTS_DIR}")
        
    except KeyboardInterrupt:
        print("\nCollection interrupted by user")
    except Exception as e:
        print(f"\nError during collection: {e}")
        logging.error(f"Collection error: {e}")

if __name__ == "__main__":
    main()