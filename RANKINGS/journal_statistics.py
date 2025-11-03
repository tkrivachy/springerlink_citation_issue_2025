#!/usr/bin/env python3
"""
Journal Statistics Analyzer for v7 Citation Data
Analyzes all collected data to provide comprehensive statistics on articles and authors per journal
"""

import pandas as pd
import os
import json
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
import logging
from config import JOURNALS, RESULTS_DIR

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_authors(author_string):
    """
    Parse the author string from CSV to extract individual authors.
    The author string format appears to be: "Author1; Author2; Author3"
    """
    if pd.isna(author_string) or author_string == '':
        return []
    
    # Split by semicolon and clean up
    authors = [author.strip() for author in str(author_string).split(';')]
    # Remove empty strings
    authors = [author for author in authors if author]
    return authors


def parse_author_details(author_details_string):
    """
    Parse the author_details field which contains structured author information.
    Format appears to be dictionary-like strings separated by semicolons.
    """
    if pd.isna(author_details_string) or author_details_string == '':
        return []
    
    try:
        # The author_details field contains dict-like strings
        # We'll extract unique authors from this field
        authors = []
        if 'full_name' in str(author_details_string):
            # Try to extract full names from the structured data
            parts = str(author_details_string).split(';')
            for part in parts:
                if 'full_name' in part:
                    # Extract the full name
                    start = part.find("'full_name': '") + len("'full_name': '")
                    end = part.find("'", start)
                    if start > 13 and end > start:  # Valid extraction
                        full_name = part[start:end]
                        if full_name and full_name not in authors:
                            authors.append(full_name)
        return authors
    except:
        return []


def get_unique_authors_from_row(row):
    """
    Extract unique authors from a row, trying both authors and author_details fields.
    """
    all_authors = set()
    
    # Parse from authors field
    authors_from_field = parse_authors(row.get('authors', ''))
    all_authors.update(authors_from_field)
    
    # Parse from author_details field
    authors_from_details = parse_author_details(row.get('author_details', ''))
    all_authors.update(authors_from_details)
    
    return list(all_authors)


def analyze_journal_data():
    """
    Analyze all journal data and return comprehensive statistics.
    """
    logger.info("Starting journal data analysis...")
    
    # Dictionary to store results
    journal_stats = {}
    
    # Track overall statistics
    total_articles_all_journals = 0
    total_unique_authors_all_journals = set()  # This will track truly unique authors across ALL journals
    
    # Track cross-journal author statistics
    author_journal_mapping = defaultdict(set)  # author -> set of journals they appear in
    
    # Get all available journal keys from the data
    available_journals = set()
    
    # Scan directories to find what journals we actually have data for
    if RESULTS_DIR.exists():
        for year_dir in RESULTS_DIR.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                for file_path in year_dir.glob("*.csv"):
                    # Extract journal name from filename
                    filename = file_path.stem
                    if '_articles' in filename:
                        journal_key = filename.replace('_articles', '').replace(f'_{year_dir.name}', '')
                        available_journals.add(journal_key)
    
    logger.info(f"Found data for journals: {', '.join(available_journals)}")
    
    # Process each journal
    for journal_key in available_journals:
        logger.info(f"Processing journal: {journal_key}")
        
        journal_info = JOURNALS.get(journal_key, {
            "name": journal_key.replace('_', ' ').title(),
            "issn": "Unknown",
            "publisher": "Unknown"
        })
        
        # Initialize statistics for this journal
        stats = {
            'journal_name': journal_info.get('name', journal_key),
            'journal_key': journal_key,
            'issn': journal_info.get('issn', 'Unknown'),
            'publisher': journal_info.get('publisher', 'Unknown'),
            'total_articles': 0,
            'total_unique_authors': set(),
            'articles_by_year': defaultdict(int),
            'authors_by_year': defaultdict(set),
            'years_covered': [],
            'author_frequency': Counter(),
            'author_counts_per_article': []  # Track number of authors for each article
        }
        
        # Process all years for this journal
        for year_dir in sorted(RESULTS_DIR.iterdir()):
            if year_dir.is_dir() and year_dir.name.isdigit():
                year = year_dir.name
                csv_file = year_dir / f"{journal_key}_{year}_articles.csv"
                
                if csv_file.exists():
                    logger.info(f"  Processing {year} data...")
                    stats['years_covered'].append(int(year))
                    
                    try:
                        # Read the CSV file
                        df = pd.read_csv(csv_file)
                        
                        # Count articles for this year
                        articles_this_year = len(df)
                        stats['total_articles'] += articles_this_year
                        stats['articles_by_year'][int(year)] = articles_this_year
                        
                        # Process authors
                        year_authors = set()
                        for _, row in df.iterrows():
                            authors = get_unique_authors_from_row(row)
                            # Count authors for this article
                            author_count = len(authors) if authors else 0
                            stats['author_counts_per_article'].append(author_count)
                            
                            for author in authors:
                                if author and author.strip():
                                    clean_author = author.strip()
                                    stats['total_unique_authors'].add(clean_author)
                                    year_authors.add(clean_author)
                                    stats['author_frequency'][clean_author] += 1
                                    total_unique_authors_all_journals.add(clean_author)
                                    author_journal_mapping[clean_author].add(journal_key)
                        
                        stats['authors_by_year'][int(year)] = year_authors
                        
                        logger.info(f"    {articles_this_year} articles, {len(year_authors)} unique authors")
                        
                    except Exception as e:
                        logger.error(f"Error processing {csv_file}: {e}")
        
        # Convert sets to counts for final statistics
        stats['total_unique_authors_count'] = len(stats['total_unique_authors'])
        stats['years_covered'] = sorted(stats['years_covered'])
        
        # Convert author sets to counts in authors_by_year
        stats['authors_by_year_count'] = {
            year: len(authors) for year, authors in stats['authors_by_year'].items()
        }
        
        # Calculate author count statistics
        author_counts = stats['author_counts_per_article']
        if author_counts:
            mean_authors = sum(author_counts) / len(author_counts)
            # Calculate standard deviation manually to avoid numpy dependency issues
            variance = sum((x - mean_authors) ** 2 for x in author_counts) / len(author_counts)
            std_authors = variance ** 0.5
        else:
            mean_authors = 0
            std_authors = 0
        
        # Keep only serializable data
        stats_clean = {
            'journal_name': stats['journal_name'],
            'journal_key': stats['journal_key'],
            'issn': stats['issn'],
            'publisher': stats['publisher'],
            'total_articles': stats['total_articles'],
            'total_unique_authors_count': stats['total_unique_authors_count'],
            'mean_authors_per_article': round(mean_authors, 2),
            'std_authors_per_article': round(std_authors, 2),
            'articles_by_year': dict(stats['articles_by_year']),
            'authors_by_year_count': stats['authors_by_year_count'],
            'years_covered': stats['years_covered'],
            'year_range': f"{min(stats['years_covered'])}-{max(stats['years_covered'])}" if stats['years_covered'] else "No data",
            'most_prolific_authors': stats['author_frequency'].most_common(10)
        }
        
        journal_stats[journal_key] = stats_clean
        total_articles_all_journals += stats['total_articles']
        
        logger.info(f"Completed {journal_key}: {stats['total_articles']} articles, {len(stats['total_unique_authors'])} unique authors")
    
    # Calculate cross-journal author statistics
    authors_in_multiple_journals = {
        author: journals for author, journals in author_journal_mapping.items() 
        if len(journals) > 1
    }
    
    # Calculate journal overlap statistics
    journal_overlap_stats = {}
    journal_keys = list(available_journals)
    for i, journal1 in enumerate(journal_keys):
        for j, journal2 in enumerate(journal_keys):
            if i < j:  # Only calculate each pair once
                # Find authors who appear in both journals
                authors_j1 = {author for author, journals in author_journal_mapping.items() if journal1 in journals}
                authors_j2 = {author for author, journals in author_journal_mapping.items() if journal2 in journals}
                overlap = authors_j1.intersection(authors_j2)
                
                journal_overlap_stats[f"{journal1}_vs_{journal2}"] = {
                    'journal1': journal1,
                    'journal2': journal2,
                    'journal1_authors': len(authors_j1),
                    'journal2_authors': len(authors_j2),
                    'shared_authors': len(overlap),
                    'overlap_percentage_j1': (len(overlap) / len(authors_j1) * 100) if len(authors_j1) > 0 else 0,
                    'overlap_percentage_j2': (len(overlap) / len(authors_j2) * 100) if len(authors_j2) > 0 else 0
                }
    
    # Add overall statistics
    overall_stats = {
        'total_journals_analyzed': len(journal_stats),
        'total_articles_all_journals': total_articles_all_journals,
        'total_unique_authors_all_journals': len(total_unique_authors_all_journals),
        'sum_of_journal_unique_authors': sum(stats['total_unique_authors_count'] for stats in journal_stats.values()),
        'authors_appearing_in_multiple_journals': len(authors_in_multiple_journals),
        'percentage_authors_in_multiple_journals': (len(authors_in_multiple_journals) / len(total_unique_authors_all_journals) * 100) if len(total_unique_authors_all_journals) > 0 else 0,
        'journal_overlap_statistics': journal_overlap_stats,
        'analysis_timestamp': pd.Timestamp.now().isoformat()
    }
    
    return journal_stats, overall_stats


def print_summary_report(journal_stats, overall_stats):
    """
    Print a formatted summary report to console.
    """
    print("\n" + "="*80)
    print("JOURNAL STATISTICS SUMMARY REPORT")
    print("="*80)
    print(f"Analysis completed: {overall_stats['analysis_timestamp']}")
    print(f"Total journals analyzed: {overall_stats['total_journals_analyzed']}")
    print(f"Total articles across all journals: {overall_stats['total_articles_all_journals']:,}")
    print()
    print("AUTHOR STATISTICS:")
    print(f"Total truly unique authors across all journals: {overall_stats['total_unique_authors_all_journals']:,}")
    print(f"Sum of unique authors per journal: {overall_stats['sum_of_journal_unique_authors']:,}")
    print(f"Authors appearing in multiple journals: {overall_stats['authors_appearing_in_multiple_journals']:,}")
    print(f"Percentage of authors in multiple journals: {overall_stats['percentage_authors_in_multiple_journals']:.2f}%")
    print()
    
    print("JOURNAL OVERLAP ANALYSIS:")
    for overlap_key, overlap_data in overall_stats['journal_overlap_statistics'].items():
        j1_name = JOURNALS.get(overlap_data['journal1'], {}).get('name', overlap_data['journal1'])
        j2_name = JOURNALS.get(overlap_data['journal2'], {}).get('name', overlap_data['journal2'])
        print(f"📊 {j1_name} vs {j2_name}:")
        print(f"   Shared authors: {overlap_data['shared_authors']:,}")
        print(f"   {overlap_data['overlap_percentage_j1']:.2f}% of {j1_name} authors")
        print(f"   {overlap_data['overlap_percentage_j2']:.2f}% of {j2_name} authors")
    print()
    
    # Sort journals by total articles (descending)
    sorted_journals = sorted(
        journal_stats.items(), 
        key=lambda x: x[1]['total_articles'], 
        reverse=True
    )
    
    print("INDIVIDUAL JOURNAL STATISTICS:")
    print("-" * 80)
    
    for journal_key, stats in sorted_journals:
        print(f"\n📚 {stats['journal_name']}")
        print(f"   Journal Key: {journal_key}")
        print(f"   ISSN: {stats['issn']}")
        print(f"   Publisher: {stats['publisher']}")
        print(f"   Years Covered: {stats['year_range']}")
        print(f"   Total Articles: {stats['total_articles']:,}")
        print(f"   Total Unique Authors: {stats['total_unique_authors_count']:,}")
        print(f"   Mean Authors per Article: {stats['mean_authors_per_article']}")
        print(f"   Std Dev Authors per Article: {stats['std_authors_per_article']}")
        
        if stats['total_articles'] > 0:
            avg_authors_per_article = stats['total_unique_authors_count'] / stats['total_articles']
            print(f"   Unique Authors to Articles Ratio: {avg_authors_per_article:.2f}")
        
        # Show year distribution (top 5 years by article count)
        if stats['articles_by_year']:
            top_years = sorted(
                stats['articles_by_year'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            print(f"   Top Years by Article Count:")
            for year, count in top_years:
                authors_that_year = stats['authors_by_year_count'].get(year, 0)
                print(f"     {year}: {count:,} articles, {authors_that_year:,} authors")
        
        # Show most prolific authors
        if stats['most_prolific_authors']:
            print(f"   Most Prolific Authors:")
            for author, count in stats['most_prolific_authors'][:5]:
                print(f"     {author}: {count} articles")
        
        print()


def save_detailed_report(journal_stats, overall_stats):
    """
    Save detailed statistics to JSON and CSV files.
    """
    # Save complete statistics as JSON
    complete_stats = {
        'overall_statistics': overall_stats,
        'journal_statistics': journal_stats
    }
    
    json_file = RESULTS_DIR / "journal_statistics_complete.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(complete_stats, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Complete statistics saved to: {json_file}")
    
    # Create a summary CSV
    summary_data = []
    for journal_key, stats in journal_stats.items():
        summary_data.append({
            'Journal Name': stats['journal_name'],
            'Journal Key': journal_key,
            'ISSN': stats['issn'],
            'Publisher': stats['publisher'],
            'Total Articles': stats['total_articles'],
            'Total Unique Authors': stats['total_unique_authors_count'],
            'Mean Authors per Article': stats['mean_authors_per_article'],
            'Std Dev Authors per Article': stats['std_authors_per_article'],
            'Unique Authors to Articles Ratio': stats['total_unique_authors_count'] / stats['total_articles'] if stats['total_articles'] > 0 else 0,
            'Years Covered': stats['year_range'],
            'First Year': min(stats['years_covered']) if stats['years_covered'] else None,
            'Last Year': max(stats['years_covered']) if stats['years_covered'] else None
        })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df = summary_df.sort_values('Total Articles', ascending=False)
    
    csv_file = RESULTS_DIR / "journal_statistics_summary.csv"
    summary_df.to_csv(csv_file, index=False)
    
    logger.info(f"Summary statistics saved to: {csv_file}")
    
    # Create detailed year-by-year CSV
    detailed_data = []
    for journal_key, stats in journal_stats.items():
        for year in stats['years_covered']:
            detailed_data.append({
                'Journal Name': stats['journal_name'],
                'Journal Key': journal_key,
                'Year': year,
                'Articles': stats['articles_by_year'].get(year, 0),
                'Unique Authors': stats['authors_by_year_count'].get(year, 0)
            })
    
    detailed_df = pd.DataFrame(detailed_data)
    detailed_df = detailed_df.sort_values(['Journal Name', 'Year'])
    
    detailed_csv_file = RESULTS_DIR / "journal_statistics_by_year.csv"
    detailed_df.to_csv(detailed_csv_file, index=False)
    
    logger.info(f"Year-by-year statistics saved to: {detailed_csv_file}")
    
    # Create cross-journal overlap CSV
    overlap_data = []
    for overlap_key, overlap_info in overall_stats['journal_overlap_statistics'].items():
        j1_name = JOURNALS.get(overlap_info['journal1'], {}).get('name', overlap_info['journal1'])
        j2_name = JOURNALS.get(overlap_info['journal2'], {}).get('name', overlap_info['journal2'])
        overlap_data.append({
            'Journal 1': j1_name,
            'Journal 2': j2_name,
            'Journal 1 Key': overlap_info['journal1'],
            'Journal 2 Key': overlap_info['journal2'],
            'Journal 1 Authors': overlap_info['journal1_authors'],
            'Journal 2 Authors': overlap_info['journal2_authors'],
            'Shared Authors': overlap_info['shared_authors'],
            'Overlap % (Journal 1)': round(overlap_info['overlap_percentage_j1'], 2),
            'Overlap % (Journal 2)': round(overlap_info['overlap_percentage_j2'], 2)
        })
    
    overlap_df = pd.DataFrame(overlap_data)
    overlap_csv_file = RESULTS_DIR / "journal_author_overlap_analysis.csv"
    overlap_df.to_csv(overlap_csv_file, index=False)
    
    logger.info(f"Author overlap analysis saved to: {overlap_csv_file}")
    
    return json_file, csv_file, detailed_csv_file, overlap_csv_file


def main():
    """
    Main function to run the journal statistics analysis.
    """
    logger.info("Starting Journal Statistics Analysis for v7 data...")
    
    try:
        # Analyze all journal data
        journal_stats, overall_stats = analyze_journal_data()
        
        # Print summary report
        print_summary_report(journal_stats, overall_stats)
        
        # Save detailed reports
        json_file, csv_file, detailed_csv_file, overlap_csv_file = save_detailed_report(journal_stats, overall_stats)
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE!")
        print("="*80)
        print("Files generated:")
        print(f"📊 Summary CSV: {csv_file}")
        print(f"📈 Year-by-year CSV: {detailed_csv_file}")
        print(f"� Author Overlap CSV: {overlap_csv_file}")
        print(f"�📋 Complete JSON: {json_file}")
        print("\nUse these files for further analysis or reporting.")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise


if __name__ == "__main__":
    main()