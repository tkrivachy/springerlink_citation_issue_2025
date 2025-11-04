#!/usr/bin/env python3
"""
Produce a CSV of articles ranked by number of citations.

Output columns (in order):
  rank, number_of_citations, article_number, volume, year, doi

This script uses files produced by `main_collect_articles.py` saved into
the `RESULTS_DIR` defined in `config.py`.
"""

import json
import csv
from pathlib import Path
import sys
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ensure local package imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import RESULTS_DIR, DEFAULT_JOURNAL, ACTIVE_JOURNAL_KEY, SPLIT_AT_YEAR


def load_collected_articles(results_dir: Path, journal_key: str = None) -> list:
    """Load articles from the results directory.

    Prefer CSV files to stay under file size limits, fall back to JSON if needed.
    """
    articles = []
    actual_journal_key = journal_key or ACTIVE_JOURNAL_KEY

    # Try CSV files first (they're smaller and stay under 99MB limit)
    csv_articles_loaded = False
    for d in sorted(results_dir.iterdir()):
        if d.is_dir() and d.name.isdigit():
            csv_pattern = f"{actual_journal_key}_{d.name}_articles.csv"
            csv_file = d / csv_pattern
            if csv_file.exists():
                try:
                    df = pd.read_csv(csv_file)
                    # Convert DataFrame rows to dictionaries
                    year_articles = df.to_dict('records')
                    articles.extend(year_articles)
                    csv_articles_loaded = True
                except Exception as e:
                    print(f"Error reading CSV {csv_file}: {e}")
                    continue

    if csv_articles_loaded:
        return articles

    # Fallback: Try to find a consolidated JSON file
    pattern = f"{actual_journal_key}_complete_*.json"
    complete_files = list(results_dir.glob(pattern))

    if complete_files:
        # pick the most recent
        latest = max(complete_files, key=lambda p: p.stat().st_mtime)
        with open(latest, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # data expected to be a dict keyed by year
        for year, year_articles in data.items():
            if isinstance(year_articles, list):
                articles.extend(year_articles)
        return articles

    # Final fallback: look into year directories for JSON files
    # Filter by journal key to avoid mixing different journals
    for d in sorted(results_dir.iterdir()):
        if d.is_dir() and d.name.isdigit():
            # Look for JSON files that match the journal key
            journal_pattern = f"{actual_journal_key}_*.json"
            for jf in sorted(d.glob(journal_pattern)):
                try:
                    with open(jf, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                    if isinstance(loaded, list):
                        articles.extend(loaded)
                except Exception:
                    # skip problematic files
                    continue

    return articles


def normalize_article_row(article: dict) -> dict:
    """Return a dict with fields used for ranking and CSV output."""
    # Citation count
    citations = article.get('citation_count')
    try:
        citations = int(citations) if citations is not None else 0
    except Exception:
        citations = 0

    # Article number (may be string/int/None)
    article_number = article.get('article_number')
    if article_number is None:
        # try to infer from page or other fields
        article_number = article.get('page') or ''
    article_number = str(article_number) if article_number is not None else ''

    # Volume
    volume = article.get('volume') or ''
    volume = str(volume)

    # Year
    year = article.get('publication_year') or article.get('published_date') or ''
    # publication_year might be int or str; if published_date is YYYY-MM-DD take year
    if isinstance(year, str) and '-' in year:
        year = year.split('-')[0]
    try:
        year = int(year)
    except Exception:
        # leave as string if unparsable
        pass

    # DOI link (convert DOI to clickable link)
    doi = article.get('doi', '')
    doi_link = ''
    if doi:
        # Remove any existing https://doi.org/ prefix to avoid duplication
        if doi.startswith('https://doi.org/'):
            doi_link = doi
        elif doi.startswith('doi.org/'):
            doi_link = f"https://{doi}"
        elif doi.startswith('10.'):
            doi_link = f"https://doi.org/{doi}"
        else:
            # For any other format, try to preserve it but make it a link if it looks like a DOI
            if '10.' in doi:
                # Extract the DOI part if it's embedded in other text
                doi_part = doi[doi.find('10.'):]
                doi_link = f"https://doi.org/{doi_part}"
            else:
                doi_link = doi  # Keep as is if it doesn't look like a DOI

    return {
        'citations': citations,
        'article_number': article_number,
        'volume': volume,
        'year': year,
        'doi': doi_link
    }


def write_ranked_csv(rows: list, outpath: Path):
    headers = ['rank', 'number_of_citations', 'article_number', 'volume', 'year', 'doi_link']
    with open(outpath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        for r in rows:
            writer.writerow([
                r['rank'],
                r['citations'],
                r['article_number'],
                r['volume'],
                r['year'],
                r['doi']
            ])


def create_citation_plots(rows: list, linear_output_path: Path, loglog_output_path: Path):
    """Create both linear and log-log plots showing citations vs rank with vertical lines for article #1 entries."""
    
    # Extract data for plotting
    ranks = [row['rank'] for row in rows]
    citations = [row['citations'] for row in rows]
    
    # Find article #1 entries (first article of each volume/year)
    article_1_entries = []
    for row in rows:
        article_num = str(row.get('article_number', '')).strip()
        if article_num == '1':
            article_1_entries.append({
                'rank': row['rank'],
                'citations': row['citations'],
                'year': row['year']
            })
            # print its data as well
            print(f"Article #1 found - Rank: {row['rank']}, Citations: {row['citations']}, Year: {row['year']}, DOI: {row.get('doi', '')}")
    
    # Create linear plot
    plt.figure(figsize=(12, 8))
    
    # Main scatter plot
    plt.scatter(ranks, citations, alpha=0.6, s=10, color='blue')
    
    # Add vertical dashed lines for article #1 entries
    for entry in article_1_entries:
        plt.axvline(x=entry['rank'], color='red', linestyle='--', alpha=0.7, linewidth=1)
        # Add year label on the line
        plt.text(entry['rank'], max(citations) * 0.9, str(entry['year']), 
                rotation=90, ha='right', va='top', fontsize=8, color='red')
    
    plt.xlabel('Rank')
    plt.ylabel('Number of Citations')
    plt.title('Article Citations by Rank (Linear Scale)\n(Red dashed lines mark Article #1 of each volume)')
    plt.grid(True, alpha=0.3)
    
    # Set y-axis to start from 0 (linear scale)
    plt.ylim(bottom=0)
    
    plt.tight_layout()
    plt.savefig(linear_output_path, dpi=300, bbox_inches='tight')
    plt.close()  # Close to free memory
    
    # Create log-log plot
    # Filter out zero citations for log plot
    nonzero_data = [(r, c) for r, c in zip(ranks, citations) if c > 0]
    if nonzero_data:
        nonzero_ranks, nonzero_citations = zip(*nonzero_data)
        
        # Filter article #1 entries for non-zero citations
        nonzero_article_1_entries = [entry for entry in article_1_entries if entry['citations'] > 0]
        
        plt.figure(figsize=(12, 8))
        
        # Main scatter plot in log-log scale
        plt.loglog(nonzero_ranks, nonzero_citations, 'o', alpha=0.6, markersize=4, color='blue')
        
        # Add vertical dashed lines for article #1 entries with non-zero citations
        for entry in nonzero_article_1_entries:
            plt.axvline(x=entry['rank'], color='red', linestyle='--', alpha=0.7, linewidth=1)
            # Add year label on the line
            plt.text(entry['rank'], max(nonzero_citations) * 0.8, str(entry['year']), 
                    rotation=90, ha='right', va='top', fontsize=8, color='red')
        
        plt.xlabel('Rank (log scale)')
        plt.ylabel('Number of Citations (log scale)')
        plt.title('Article Citations by Rank (Log-Log Scale)\n(Red dashed lines mark Article #1 of each volume, zero citations excluded)')
        plt.grid(True, alpha=0.3, which='both')
        
        plt.tight_layout()
        plt.savefig(loglog_output_path, dpi=300, bbox_inches='tight')
        plt.close()  # Close to free memory
        
        print(f"Log-log plot created with {len(nonzero_data)} non-zero citation entries out of {len(rows)} total")
    else:
        print("No articles with non-zero citations found, skipping log-log plot")
    
    return len(article_1_entries)


def process_articles(articles: list, suffix: str = "") -> tuple:
    """Process and rank articles, return (rows, sort_function)"""
    normalized = [normalize_article_row(a) for a in articles]

    # Sort by citations desc, then by year desc, then by volume/article_number
    def sort_key(x):
        # year may be int or string; try to make it int for sorting, fallback to 0
        y = x.get('year')
        try:
            yv = int(y)
        except Exception:
            yv = 0
        try:
            an = int(x.get('article_number'))
        except Exception:
            an = 0
        try:
            vol = int(x.get('volume'))
        except Exception:
            vol = 0
        return (-x.get('citations', 0), -yv, -vol, -an)

    normalized_sorted = sorted(normalized, key=sort_key)

    # Add rank (1-based). Equal citation counts get sequential ranks (no ties collapsing)
    rows = []
    for idx, item in enumerate(normalized_sorted, start=1):
        item_row = item.copy()
        item_row['rank'] = idx
        rows.append(item_row)
    
    return rows

def main():
    results_dir = Path(RESULTS_DIR)
    if not results_dir.exists():
        print(f"Results directory does not exist: {results_dir}")
        return

    # Use the active journal key from config for file matching
    journal_key = ACTIVE_JOURNAL_KEY

    print(f"Loading collected articles from: {results_dir}")
    articles = load_collected_articles(results_dir, journal_key=journal_key)
    print(f"Total articles loaded: {len(articles)}")

    if not articles:
        print("No articles found in results directory. Run main_collect_articles.py first.")
        return

    # Check if split analysis is requested
    if SPLIT_AT_YEAR is not None:
        print(f"Split analysis enabled at year: {SPLIT_AT_YEAR}")
        
        # Split articles into two groups
        early_articles = []
        recent_articles = []
        
        for article in articles:
            normalized_article = normalize_article_row(article)
            year = normalized_article.get('year')
            
            try:
                year_int = int(year)
                if year_int <= SPLIT_AT_YEAR:
                    early_articles.append(article)
                else:
                    recent_articles.append(article)
            except (ValueError, TypeError):
                # If year can't be parsed, put in recent articles
                recent_articles.append(article)
        
        print(f"Articles ≤{SPLIT_AT_YEAR}: {len(early_articles)}")
        print(f"Articles >{SPLIT_AT_YEAR}: {len(recent_articles)}")
        
        # Process both groups
        
        # Early articles (up to split year)
        if early_articles:
            early_rows = process_articles(early_articles)
            early_csv = results_dir / f"{journal_key}_ranked_up_to_{SPLIT_AT_YEAR}.csv"
            early_linear_plot = results_dir / f"{journal_key}_citation_plot_linear_up_to_{SPLIT_AT_YEAR}.png"
            early_loglog_plot = results_dir / f"{journal_key}_citation_plot_loglog_up_to_{SPLIT_AT_YEAR}.png"
            
            write_ranked_csv(early_rows, early_csv)
            print(f"Early period CSV saved to: {early_csv}")
            print(f"Early period rows: {len(early_rows)}")
            
            try:
                early_article_1_count = create_citation_plots(early_rows, early_linear_plot, early_loglog_plot)
                print(f"Early period linear plot saved to: {early_linear_plot}")
                print(f"Early period log-log plot saved to: {early_loglog_plot}")
                print(f"Early period article #1 entries: {early_article_1_count}")
            except Exception as e:
                print(f"Error creating early period plots: {e}")
        
        # Recent articles (after split year)
        if recent_articles:
            recent_rows = process_articles(recent_articles)
            recent_csv = results_dir / f"{journal_key}_ranked_after_{SPLIT_AT_YEAR}.csv"
            recent_linear_plot = results_dir / f"{journal_key}_citation_plot_linear_after_{SPLIT_AT_YEAR}.png"
            recent_loglog_plot = results_dir / f"{journal_key}_citation_plot_loglog_after_{SPLIT_AT_YEAR}.png"
            
            write_ranked_csv(recent_rows, recent_csv)
            print(f"Recent period CSV saved to: {recent_csv}")
            print(f"Recent period rows: {len(recent_rows)}")
            
            try:
                recent_article_1_count = create_citation_plots(recent_rows, recent_linear_plot, recent_loglog_plot)
                print(f"Recent period linear plot saved to: {recent_linear_plot}")
                print(f"Recent period log-log plot saved to: {recent_loglog_plot}")
                print(f"Recent period article #1 entries: {recent_article_1_count}")
            except Exception as e:
                print(f"Error creating recent period plots: {e}")
    
    else:
        # Original single ranking approach
        print("Single ranking analysis (no year split)")
        
        rows = process_articles(articles)

        # Output files
        out_file = results_dir / f"{journal_key}_ranked_by_citations.csv"
        linear_plot_file = results_dir / f"{journal_key}_citation_rank_plot_linear.png"
        loglog_plot_file = results_dir / f"{journal_key}_citation_rank_plot_loglog.png"
        
        # Save CSV
        write_ranked_csv(rows, out_file)
        print(f"Ranked CSV saved to: {out_file}")
        print(f"Total rows written: {len(rows)}")
        
        # Create and save plots
        try:
            article_1_count = create_citation_plots(rows, linear_plot_file, loglog_plot_file)
            print(f"Linear citation plot saved to: {linear_plot_file}")
            print(f"Log-log citation plot saved to: {loglog_plot_file}")
            print(f"Article #1 entries marked: {article_1_count}")
        except Exception as e:
            print(f"Error creating plots: {e}")
            print("Plot creation failed, but CSV was saved successfully.")


if __name__ == '__main__':
    main()
