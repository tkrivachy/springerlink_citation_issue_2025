#!/usr/bin/env python3
"""
Main Article Info Downloader for Citation Analysis v2
Downloads Article #1 and comparison articles using JATS format from Springer API
Extracts article numbers from elocation-id tags, no web scraping needed
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (get_journal_config, get_default_journals, get_journal_first_articles_dir, 
                   get_journal_same_age_articles_dir, MIN_ARTICLES_FOR_COMPARISON, LOG_LEVEL, LOG_FORMAT)
from clients.springer_client import SpringerClient

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT
    )

def save_article_metadata(article: dict, year: int, article_type: str, date_str: str, 
                         output_dir: Path, index: int = None) -> bool:
    """
    Save article metadata to JSON file
    
    Args:
        article: Article metadata dictionary
        year: Year of the article
        article_type: 'article_1' or 'comparison'
        date_str: Publication date string
        output_dir: Directory to save the file
        index: Index for comparison articles
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create safe filename
        doi = article.get('doi', 'unknown')
        safe_doi = doi.replace('/', '_').replace(':', '_')
        
        if article_type == 'article_1':
            filename = f"{year}_article_1_{safe_doi}.json"
        else:
            filename = f"{year}_{date_str}_{index:03d}_{safe_doi}.json"
        
        filepath = output_dir / filename
        
        # Add metadata
        article_with_meta = {
            'extraction_date': datetime.now().isoformat(),
            'year': year,
            'article_type': article_type,
            'publication_date': date_str,
            'article_data': article
        }
        
        if index is not None:
            article_with_meta['article_index'] = index
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(article_with_meta, f, indent=2, ensure_ascii=False)
        
        if LOG_LEVEL == "DEBUG":
            print(f"  💾 Saved: {filename}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error saving article metadata: {e}")
        return False

def download_article_1_for_year(client: SpringerClient, journal_config: dict, journal_key: str, year: int) -> bool:
    """
    Download Article #1 for a specific year
    
    Args:
        client: SpringerClient instance
        journal_config: Journal configuration dictionary
        journal_key: Journal key for directory structure
        year: Year to process
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n🔍 Searching for Article #1 in {year}...")
    
    issn = journal_config['issn']
    is_open_access = journal_config.get('is_open_access', False)
    
    # Special handling for journal start year
    if year == journal_config['start_year']:
        start_month = journal_config.get('start_month', 1)
        start_day = journal_config.get('start_day', 1)
        article_1, date_str = client.find_article_number_1(issn, year, start_month, start_day, is_open_access)
    else:
        article_1, date_str = client.find_article_number_1(issn, year, is_open_access=is_open_access)
    
    if article_1 and date_str:
        # Get journal-specific directory for first articles
        first_articles_dir = get_journal_first_articles_dir(journal_key)
        
        # Save Article #1 metadata
        success = save_article_metadata(
            article=article_1,
            year=year,
            article_type='article_1',
            date_str=date_str,
            output_dir=first_articles_dir
        )
        
        if success:
            print(f"✅ Found and saved Article #1 for {year}")
            print(f"    DOI: {article_1.get('doi', 'N/A')}")
            print(f"    Date: {date_str}")
            print(f"    Article Number: {article_1.get('article_number', 'N/A')}")
            return True
    
    print(f"❌ Article #1 not found for {year}")
    return False

def download_articles_optimized_for_year(client: SpringerClient, journal_config: dict, journal_key: str, year: int) -> Tuple[bool, bool]:
    """
    Download both Article #1 and comparison articles for a specific year using optimized API calls
    
    Args:
        client: SpringerClient instance
        journal_config: Journal configuration dictionary
        journal_key: Journal key for directory structure
        year: Year to process
        
    Returns:
        Tuple of (article_1_success, comparison_success)
    """
    print(f"\n🔍 Searching for Article #1 and comparison articles for {year}...")
    
    issn = journal_config['issn']
    is_open_access = journal_config.get('is_open_access', False)
    
    # Use optimized search that returns cached articles
    if year == journal_config['start_year']:
        start_month = journal_config.get('start_month', 1)
        start_day = journal_config.get('start_day', 1)
        article_1, reference_date, cached_articles = client.find_article_number_1_with_cache(issn, year, start_month, start_day, is_open_access)
    else:
        article_1, reference_date, cached_articles = client.find_article_number_1_with_cache(issn, year, is_open_access=is_open_access)
    
    # Save Article #1
    article_1_success = False
    if article_1 and reference_date:
        first_articles_dir = get_journal_first_articles_dir(journal_key)
        
        article_1_success = save_article_metadata(
            article=article_1,
            year=year,
            article_type='article_1',
            date_str=reference_date,
            output_dir=first_articles_dir
        )
        
        if article_1_success:
            print(f"✅ Found and saved Article #1 for {year}")
            print(f"    DOI: {article_1.get('doi', 'N/A')}")
            print(f"    Date: {reference_date}")
            print(f"    Article Number: {article_1.get('article_number', 'N/A')}")
            print(f"    Cached {len(cached_articles)} articles from search for reuse")
        else:
            print(f"❌ Failed to save Article #1 for {year}")
    else:
        print(f"❌ Article #1 not found for {year}")
    
    # Collect comparison articles using cached data
    comparison_success = False
    if reference_date:
        print(f"\n📚 Collecting comparison articles for {year} using cached data...")
        
        # First, check if we have enough articles to meet the minimum requirement
        comparison_articles = client.collect_comparison_articles(
            issn=issn,
            year=year,
            target_date=reference_date,
            min_articles=MIN_ARTICLES_FOR_COMPARISON,
            cached_articles=cached_articles,
            is_open_access=is_open_access
        )
        
        if comparison_articles:
            # Use the comparison articles returned by the client, which includes all found articles
            articles_to_save = comparison_articles
            
            print(f"📊 Found {len(articles_to_save)} total articles published on/after {reference_date}")
            if len(articles_to_save) >= MIN_ARTICLES_FOR_COMPARISON:
                print(f"   Using all {len(articles_to_save)} articles (exceeds minimum {MIN_ARTICLES_FOR_COMPARISON})")
            else:
                print(f"   Using all {len(articles_to_save)} articles (less than minimum {MIN_ARTICLES_FOR_COMPARISON}, but saving all found)")
            
            # Get journal-specific directory for same age articles
            same_age_dir = get_journal_same_age_articles_dir(journal_key)
            
            # Create year-specific directory for comparison articles
            year_dir = same_age_dir / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)
            
            # Save all eligible comparison articles
            saved_count = 0
            for i, article in enumerate(articles_to_save, 1):
                success = save_article_metadata(
                    article=article,
                    year=year,
                    article_type='comparison',
                    date_str=reference_date,
                    output_dir=year_dir,
                    index=i
                )
                if success:
                    saved_count += 1
            
            if saved_count > 0:
                comparison_success = True
                print(f"✅ Saved {saved_count}/{len(articles_to_save)} comparison articles for {year}")
                if len(articles_to_save) >= MIN_ARTICLES_FOR_COMPARISON:
                    print(f"   📈 Saved {len(articles_to_save) - MIN_ARTICLES_FOR_COMPARISON} additional articles beyond minimum requirement")
                else:
                    print(f"   📊 Saved all {saved_count} articles found (less than minimum {MIN_ARTICLES_FOR_COMPARISON})")
            else:
                print(f"❌ Failed to save comparison articles for {year}")
        else:
            print(f"❌ No comparison articles found for {year}")
    else:
        print(f"❌ Cannot collect comparison articles without reference date for {year}")
    
    return article_1_success, comparison_success

def download_comparison_articles_for_year(client: SpringerClient, journal_config: dict, journal_key: str, year: int) -> bool:
    """
    Download comparison articles for a specific year (legacy method - kept for compatibility)
    
    Args:
        client: SpringerClient instance
        journal_config: Journal configuration dictionary
        journal_key: Journal key for directory structure
        year: Year to process
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n📚 Collecting comparison articles for {year}...")
    
    issn = journal_config['issn']
    is_open_access = journal_config.get('is_open_access', False)
    
    # First, we need to find when Article #1 was published to use as reference date
    if year == journal_config['start_year']:
        start_month = journal_config.get('start_month', 1)
        start_day = journal_config.get('start_day', 1)
        article_1, reference_date = client.find_article_number_1(issn, year, start_month, start_day, is_open_access)
    else:
        article_1, reference_date = client.find_article_number_1(issn, year, is_open_access=is_open_access)
    
    if not reference_date:
        print(f"❌ Cannot find reference date (Article #1) for {year}")
        return False
    
    # Collect comparison articles starting from the reference date
    comparison_articles = client.collect_comparison_articles(
        issn=issn,
        year=year,
        target_date=reference_date,
        min_articles=MIN_ARTICLES_FOR_COMPARISON,
        is_open_access=is_open_access
    )
    
    if not comparison_articles:
        print(f"❌ No comparison articles found for {year}")
        return False
    
    # Get journal-specific directory for same age articles
    same_age_dir = get_journal_same_age_articles_dir(journal_key)
    
    # Create year-specific directory for comparison articles
    year_dir = same_age_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    
    # Save comparison articles
    saved_count = 0
    for i, article in enumerate(comparison_articles, 1):
        success = save_article_metadata(
            article=article,
            year=year,
            article_type='comparison',
            date_str=reference_date,
            output_dir=year_dir,
            index=i
        )
        if success:
            saved_count += 1
    
    if len(comparison_articles) >= MIN_ARTICLES_FOR_COMPARISON:
        print(f"✅ Saved {saved_count}/{len(comparison_articles)} comparison articles for {year}")
    else:
        print(f"✅ Saved {saved_count}/{len(comparison_articles)} comparison articles for {year} (less than minimum {MIN_ARTICLES_FOR_COMPARISON}, but saving all found)")
    return saved_count > 0

def process_journal_years(journal_key: str, years: list = None) -> dict:
    """
    Process multiple years for a journal
    
    Args:
        journal_key: Journal identifier from config
        years: List of years to process (None for all analysis_years)
        
    Returns:
        Dictionary with processing results
    """
    print("=" * 80)
    print("ARTICLE INFO DOWNLOADER v2")
    print("=" * 80)
    
    # Get journal configuration
    journal_config = get_journal_config(journal_key)
    journal_name = journal_config['name']
    
    print(f"📖 Journal: {journal_name}")
    print(f"📧 ISSN: {journal_config['issn']}")
    
    # Use provided years or default to analysis_years
    if years is None:
        years = journal_config['analysis_years']
    
    print(f"📅 Processing years: {min(years)}-{max(years)} ({len(years)} years)")
    
    # Initialize Springer client
    client = SpringerClient()
    
    results = {
        'journal': journal_name,
        'years_processed': [],
        'article_1_found': {},
        'comparison_articles_found': {},
        'errors': []
    }
    
    # Process each year
    for year in sorted(years):
        try:
            print(f"\n{'='*60}")
            print(f"PROCESSING YEAR {year}")
            print(f"{'='*60}")
            
            # Use optimized function that gets both Article #1 and comparison articles
            article_1_success, comparison_success = download_articles_optimized_for_year(
                client, journal_config, journal_key, year
            )
            
            results['article_1_found'][year] = article_1_success
            results['comparison_articles_found'][year] = comparison_success
            
            if article_1_success and comparison_success:
                results['years_processed'].append(year)
                print(f"✅ Successfully processed {year} with optimized API calls")
            else:
                print(f"⚠️  Partial or no success for {year}")
                
        except Exception as e:
            error_msg = f"Error processing year {year}: {e}"
            print(f"❌ {error_msg}")
            results['errors'].append(error_msg)
    
    return results

def print_summary(results: dict):
    """Print summary of processing results"""
    print("\n" + "=" * 80)
    print("PROCESSING SUMMARY")
    print("=" * 80)
    
    journal_name = results['journal']
    years_processed = results['years_processed']
    article_1_found = results['article_1_found']
    comparison_found = results['comparison_articles_found']
    errors = results['errors']
    
    print(f"📖 Journal: {journal_name}")
    print(f"✅ Successfully processed years: {len(years_processed)}")
    
    if years_processed:
        print(f"   Years: {', '.join(map(str, sorted(years_processed)))}")
    
    # Article #1 summary
    article_1_success = sum(1 for found in article_1_found.values() if found)
    print(f"🎯 Article #1 found: {article_1_success}/{len(article_1_found)} years")
    
    # Comparison articles summary  
    comparison_success = sum(1 for found in comparison_found.values() if found)
    print(f"📚 Comparison articles found: {comparison_success}/{len(comparison_found)} years")
    
    # Errors
    if errors:
        print(f"❌ Errors encountered: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
    
    print(f"\n💾 Output structure:")
    print(f"   Articles saved in journal-specific directories")
    print(f"   - data/journal_name/first_articles/: Article #1 for each year")
    print(f"   - data/journal_name/same_age_articles/: Comparison articles by year")

def process_multiple_journals(journal_keys: list = None, years: list = None) -> dict:
    """
    Process multiple journals
    
    Args:
        journal_keys: List of journal identifiers (None for default journals)
        years: List of years to process (None for all analysis_years per journal)
        
    Returns:
        Dictionary with overall processing results
    """
    if journal_keys is None:
        journal_keys = get_default_journals()
    
    print("=" * 80)
    print("MULTI-JOURNAL ARTICLE INFO DOWNLOADER v2")
    print("=" * 80)
    print(f"📚 Processing {len(journal_keys)} journals: {', '.join(journal_keys)}")
    
    overall_results = {
        'journals_processed': [],
        'journal_results': {},
        'total_articles_downloaded': 0,
        'total_errors': []
    }
    
    for i, journal_key in enumerate(journal_keys, 1):
        try:
            print(f"\n{'='*20} JOURNAL {i}/{len(journal_keys)} {'='*20}")
            
            # Process this journal
            journal_results = process_journal_years(journal_key, years)
            overall_results['journal_results'][journal_key] = journal_results
            
            # Track overall stats
            if journal_results['years_processed']:
                overall_results['journals_processed'].append(journal_key)
                # Count articles downloaded (rough estimate)
                years_count = len(journal_results['years_processed'])
                articles_per_year = MIN_ARTICLES_FOR_COMPARISON + 1  # comparison + article #1
                overall_results['total_articles_downloaded'] += years_count * articles_per_year
            
            if journal_results.get('errors'):
                overall_results['total_errors'].extend(journal_results['errors'])
                
        except Exception as e:
            error_msg = f"Fatal error processing journal {journal_key}: {e}"
            print(f"❌ {error_msg}")
            overall_results['total_errors'].append(error_msg)
    
    return overall_results

def print_multi_journal_summary(results: dict):
    """Print summary of multi-journal processing results"""
    print("\n" + "=" * 80)
    print("MULTI-JOURNAL PROCESSING SUMMARY")
    print("=" * 80)
    
    journals_processed = results['journals_processed']
    total_journals = len(results['journal_results'])
    total_articles = results['total_articles_downloaded']
    total_errors = len(results['total_errors'])
    
    print(f"📚 Journals processed successfully: {len(journals_processed)}/{total_journals}")
    
    if journals_processed:
        print(f"   Success: {', '.join(journals_processed)}")
    
    failed_journals = [j for j in results['journal_results'].keys() if j not in journals_processed]
    if failed_journals:
        print(f"   Failed: {', '.join(failed_journals)}")
    
    print(f"📊 Estimated articles downloaded: {total_articles}")
    
    if total_errors:
        print(f"❌ Total errors: {total_errors}")
        print("   (See individual journal summaries above for details)")
    
    # Print detailed results for each journal
    print(f"\n📖 Individual Journal Results:")
    for journal_key, journal_results in results['journal_results'].items():
        journal_config = get_journal_config(journal_key)
        years_processed = len(journal_results.get('years_processed', []))
        article_1_found = sum(1 for found in journal_results.get('article_1_found', {}).values() if found)
        comparison_found = sum(1 for found in journal_results.get('comparison_articles_found', {}).values() if found)
        
        status = "✅" if journal_key in journals_processed else "❌"
        print(f"   {status} {journal_config['name']}: {years_processed} years, "
              f"Article #1: {article_1_found}, Comparisons: {comparison_found}")
    
    print(f"\n💾 Output structure:")
    print(f"   Each journal has its own directory structure:")
    print(f"   - data/journal_key/first_articles/: Article #1 for each year")
    print(f"   - data/journal_key/same_age_articles/YYYY/: Comparison articles by year")

def main():
    """Main function"""
    setup_logging()
    
    # Configuration - modify these settings or add command line argument parsing
    JOURNAL_KEYS = None  # None = use default journals, or specify list like ["nature_communications"] for single journal
    YEARS = None  # None = use all analysis_years from config, or specify list like [2020, 2021, 2022]
    
    try:
        results = process_multiple_journals(JOURNAL_KEYS, YEARS)
        print_multi_journal_summary(results)
        
        # Check if any processing was successful
        if results['journals_processed']:
            print(f"\n🎉 Article download completed successfully!")
            print(f"   Successfully processed {len(results['journals_processed'])} out of {len(results['journal_results'])} journals")
            sys.exit(0)
        else:
            print(f"\n❌ No journals were processed successfully")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
