#!/usr/bin/env python3
"""
Augment Records with Citation Count
Adds citation counts from all available clients to existing article JSON files
Goes through all articles in v2/data/JOURNAL_NAME directories and enriches them with citation information
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    get_journal_config, 
    get_citation_client_config, 
    get_available_citation_clients,
    get_default_journals, 
    get_default_citation_clients, 
    get_journal_first_articles_dir, 
    get_journal_same_age_articles_dir,
    LOG_LEVEL, 
    LOG_FORMAT,
    OVERWRITE_PREVIOUS_CITATION_COUNT
)
from clients.semantic_scholar_client import SemanticScholarClient
from clients.crossref_client import CrossrefClient
from clients.opencitations_client import OpenCitationsClient
from clients.nature_scraper_client import NatureScraperClient

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT
    )

def get_citation_client(client_key: str):
    """Initialize and return the appropriate citation client"""
    client_config = get_citation_client_config(client_key)
    
    if client_key == 'semantic':
        return SemanticScholarClient()
    elif client_key == 'crossref':
        return CrossrefClient()
    elif client_key == 'opencitations':
        return OpenCitationsClient()
    elif client_key == 'nature_scraper':
        return NatureScraperClient()
    else:
        raise ValueError(f"Unknown citation client: {client_key}")

def load_article_json(file_path: Path) -> Optional[Dict]:
    """Load article metadata from JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logging.error(f"Error loading {file_path}: {e}")
        return None

def save_article_json(file_path: Path, data: Dict) -> bool:
    """Save article metadata to JSON file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Error saving {file_path}: {e}")
        return False

def extract_doi_from_article(article_data: Dict) -> Optional[str]:
    """Extract DOI from article data"""
    article_info = article_data.get('article_data', {})
    doi = article_info.get('doi')
    return doi if doi else None

def get_citation_count_for_doi(doi: str, client) -> Optional[int]:
    """Get citation count for a single DOI using a specific client"""
    try:
        citation_counts = client.get_citation_counts_for_dois([doi])
        return citation_counts.get(doi)
    except Exception as e:
        logging.warning(f"Error getting citation count for {doi} using {client.__class__.__name__}: {e}")
        return None

def has_recent_citation_data(article_data: Dict, client_key: str, max_age_days: int = 30) -> bool:
    """Check if article already has recent citation data for a specific client"""
    if 'citation_counts' not in article_data:
        return False
    
    client_data = article_data['citation_counts'].get(client_key)
    if not client_data:
        return False
    
    # Check if there's a retrieved_at timestamp
    if 'retrieved_at' not in client_data:
        return False
    
    try:
        retrieved_at = datetime.fromisoformat(client_data['retrieved_at'])
        days_since_retrieval = (datetime.now() - retrieved_at).days
        return days_since_retrieval <= max_age_days
    except:
        return False

def augment_article_with_citations(article_data: Dict, client_keys: List[str]) -> Tuple[Dict, int, int]:
    """Add citation counts from all clients to article data"""
    doi = extract_doi_from_article(article_data)
    
    if not doi:
        logging.warning(f"No DOI found in article data")
        return article_data, 0, 0
    
    # Initialize citation_counts section if it doesn't exist
    if 'citation_counts' not in article_data:
        article_data['citation_counts'] = {}
    
    clients_processed = 0
    clients_skipped = 0
    
    # Get citation counts from each client
    for client_key in client_keys:
        client_config = get_citation_client_config(client_key)
        
        # Check if we should use cached data (only if OVERWRITE_PREVIOUS_CITATION_COUNT is False)
        if not OVERWRITE_PREVIOUS_CITATION_COUNT and has_recent_citation_data(article_data, client_key, max_age_days=30):
            existing_count = article_data['citation_counts'][client_key].get('citation_count')
            if existing_count is not None:
                print(f"        {client_config['name']}: {existing_count} citations (cached)")
            else:
                print(f"        {client_config['name']}: No data available (cached)")
            clients_skipped += 1
            continue
        
        try:
            client = get_citation_client(client_key)
            citation_count = get_citation_count_for_doi(doi, client)
            
            article_data['citation_counts'][client_key] = {
                'client_name': client_config['name'],
                'citation_count': citation_count,
                'retrieved_at': datetime.now().isoformat()
            }
            
            if citation_count is not None:
                print(f"        {client_config['name']}: {citation_count} citations (fresh)")
                logging.info(f"  {client_config['name']}: {citation_count} citations")
            else:
                print(f"        {client_config['name']}: No citation data available (fresh)")
                logging.info(f"  {client_config['name']}: No citation data available")
            
            clients_processed += 1
                
        except Exception as e:
            logging.error(f"Error processing {client_key} for DOI {doi}: {e}")
            article_data['citation_counts'][client_key] = {
                'client_name': client_config['name'],
                'citation_count': None,
                'error': str(e),
                'retrieved_at': datetime.now().isoformat()
            }
            print(f"        {client_config['name']}: Error - {e}")
            clients_processed += 1
    
    # Update the overall timestamp only if we processed any clients
    if clients_processed > 0:
        article_data['citation_counts']['last_updated'] = datetime.now().isoformat()
    
    return article_data, clients_processed, clients_skipped

def process_json_files_in_directory(directory: Path, client_keys: List[str]) -> Tuple[int, int, int, int]:
    """Process all JSON files in a directory, returns (processed_count, error_count, clients_processed, clients_skipped)"""
    if not directory.exists():
        logging.warning(f"Directory does not exist: {directory}")
        return 0, 0, 0, 0
    
    json_files = list(directory.glob("*.json"))
    processed_count = 0
    error_count = 0
    total_clients_processed = 0
    total_clients_skipped = 0
    
    for i, json_file in enumerate(json_files, 1):
        try:
            print(f"    Processing file {i}/{len(json_files)}: {json_file.name}")
            
            # Load the article data
            article_data = load_article_json(json_file)
            if not article_data:
                error_count += 1
                continue
            
            # Extract DOI for logging
            doi = extract_doi_from_article(article_data)
            if doi:
                print(f"      DOI: {doi}")
                
                # Augment with citation counts
                augmented_data, clients_processed, clients_skipped = augment_article_with_citations(article_data, client_keys)
                
                total_clients_processed += clients_processed
                total_clients_skipped += clients_skipped
                
                # Save the updated data (even if only cached data was accessed)
                if save_article_json(json_file, augmented_data):
                    processed_count += 1
                    if clients_processed > 0:
                        print(f"      ✅ Updated with {clients_processed} fresh + {clients_skipped} cached citation counts")
                        # Print current directory that we are examining
                        print(f"      Current directory: {json_file.parent}")
                    else:
                        print(f"      ✅ All {clients_skipped} citation counts from cache")
                else:
                    error_count += 1
                    print(f"      ❌ Error saving updated data")
            else:
                print(f"      ⚠️ No DOI found - skipping citation count retrieval")
                processed_count += 1
            
        except Exception as e:
            logging.error(f"Error processing {json_file}: {e}")
            error_count += 1
            print(f"      ❌ Error: {e}")
    
    return processed_count, error_count, total_clients_processed, total_clients_skipped

def process_journal_year(journal_key: str, year: int, client_keys: List[str]) -> Tuple[int, int, int, int]:
    """Process all articles for a specific journal and year"""
    print(f"  Processing year {year}...")
    
    processed_count = 0
    error_count = 0
    total_clients_processed = 0
    total_clients_skipped = 0
    
    # Process first articles
    first_articles_dir = get_journal_first_articles_dir(journal_key)
    first_article_files = list(first_articles_dir.glob(f"{year}_article_1_*.json"))
    
    if first_article_files:
        print(f"    Processing Article #1:")
        for json_file in first_article_files:
            try:
                print(f"      Processing: {json_file.name}")
                
                article_data = load_article_json(json_file)
                if not article_data:
                    error_count += 1
                    continue
                
                doi = extract_doi_from_article(article_data)
                if doi:
                    print(f"        DOI: {doi}")
                    
                    augmented_data, clients_processed, clients_skipped = augment_article_with_citations(article_data, client_keys)
                    total_clients_processed += clients_processed
                    total_clients_skipped += clients_skipped
                    
                    if save_article_json(json_file, augmented_data):
                        processed_count += 1
                        if clients_processed > 0:
                            print(f"        ✅ Updated with {clients_processed} fresh + {clients_skipped} cached citation counts")
                        else:
                            print(f"        ✅ All {clients_skipped} citation counts from cache")
                    else:
                        error_count += 1
                        print(f"        ❌ Error saving updated data")
                else:
                    print(f"        ⚠️ No DOI found - skipping")
                    processed_count += 1
                        
            except Exception as e:
                logging.error(f"Error processing first article {json_file}: {e}")
                error_count += 1
                print(f"        ❌ Error: {e}")
    
    # Process same-age articles
    same_age_articles_dir = get_journal_same_age_articles_dir(journal_key)
    year_dir = same_age_articles_dir / str(year)
    
    if year_dir.exists():
        print(f"    Processing same-age articles:")
        p_count, e_count, c_processed, c_skipped = process_json_files_in_directory(year_dir, client_keys)
        processed_count += p_count
        error_count += e_count
        total_clients_processed += c_processed
        total_clients_skipped += c_skipped
    else:
        print(f"    No same-age articles directory found for {year}")
    
    return processed_count, error_count, total_clients_processed, total_clients_skipped

def process_journal(journal_key: str, client_keys: List[str]) -> Tuple[int, int, int, int]:
    """Process all articles for a specific journal"""
    journal_config = get_journal_config(journal_key)
    print(f"\n📖 Processing journal: {journal_config['name']}")
    print(f"   Journal key: {journal_key}")
    
    # Get years to process
    excluded_years = set(journal_config.get('excluded_years', []))
    analysis_years = [y for y in journal_config['analysis_years'] if y not in excluded_years]
    
    print(f"   Years to process: {sorted(analysis_years)}")
    if excluded_years:
        print(f"   Excluded years: {sorted(excluded_years)}")
    
    total_processed = 0
    total_errors = 0
    total_clients_processed = 0
    total_clients_skipped = 0
    
    for year in sorted(analysis_years):
        processed_count, error_count, clients_processed, clients_skipped = process_journal_year(journal_key, year, client_keys)
        total_processed += processed_count
        total_errors += error_count
        total_clients_processed += clients_processed
        total_clients_skipped += clients_skipped
        
        print(f"    Year {year}: {processed_count} articles, {error_count} errors, {clients_processed} fresh API calls, {clients_skipped} cached")
    
    print(f"   ✅ Journal {journal_config['name']} complete:")
    print(f"      📄 {total_processed} articles processed, {total_errors} errors")
    print(f"      🔄 {total_clients_processed} fresh API calls, {total_clients_skipped} cached results")
    return total_processed, total_errors, total_clients_processed, total_clients_skipped

def main():
    """Main function"""
    setup_logging()
    
    # Get configuration
    journal_keys = get_default_journals()
    client_keys = get_default_citation_clients()
    
    print("=" * 80)
    print("CITATION COUNT AUGMENTATION SCRIPT")
    print("=" * 80)
    print(f"📚 Journals to process: {', '.join(journal_keys)}")
    print(f"📊 Citation clients: {', '.join([get_citation_client_config(k)['name'] for k in client_keys])}")
    print(f"🔄 Overwrite cached data: {'Yes' if OVERWRITE_PREVIOUS_CITATION_COUNT else 'No'}")
    print("")
    
    total_processed = 0
    total_errors = 0
    total_clients_processed = 0
    total_clients_skipped = 0
    successful_journals = []
    failed_journals = []
    
    for i, journal_key in enumerate(journal_keys, 1):
        try:
            print(f"\n[{i}/{len(journal_keys)}] Starting journal: {journal_key}")
            
            processed_count, error_count, clients_processed, clients_skipped = process_journal(journal_key, client_keys)
            
            total_processed += processed_count
            total_errors += error_count
            total_clients_processed += clients_processed
            total_clients_skipped += clients_skipped
            
            if error_count == 0 or processed_count > 0:
                successful_journals.append(journal_key)
            else:
                failed_journals.append(journal_key)
                
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Process interrupted by user")
            break
        except Exception as e:
            logging.error(f"Fatal error processing journal {journal_key}: {e}")
            failed_journals.append(journal_key)
            print(f"❌ Failed to process journal {journal_key}: {e}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("AUGMENTATION SUMMARY")
    print("=" * 80)
    print(f"� Total articles processed: {total_processed}")
    print(f"🔄 Fresh API calls made: {total_clients_processed}")
    print(f"💾 Cached results used: {total_clients_skipped}")
    print(f"❌ Total errors: {total_errors}")
    print(f"✅ Successful journals ({len(successful_journals)}): {', '.join(successful_journals)}")
    
    if failed_journals:
        print(f"❌ Failed journals ({len(failed_journals)}): {', '.join(failed_journals)}")
    
    efficiency = (total_clients_skipped / (total_clients_processed + total_clients_skipped) * 100) if (total_clients_processed + total_clients_skipped) > 0 else 0
    print(f"\n⚡ Cache efficiency: {efficiency:.1f}% (avoided {total_clients_skipped} unnecessary API calls)")
    
    print(f"\n💾 Updated JSON files are saved in their original locations")
    print(f"   Each article now contains a 'citation_counts' section with data from all clients")
    
    if total_processed > 0:
        print(f"\n🎉 Augmentation completed successfully!")
        return 0
    else:
        print(f"\n⚠️  No articles were processed successfully")
        return 1

if __name__ == "__main__":
    sys.exit(main())
