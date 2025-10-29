#!/usr/bin/env python3
"""
Main Article Info Analyzer for Citation Analysis v2
Analyzes citation data and creates histograms with proper folder structure
Creates individual, meta, and meta-meta histograms as specified

MODIFIED: Now uses saved citation count data from JSON files instead of making API calls.
Citation data is extracted from the 'citation_counts' field in saved article JSON files.
Supports all client types: semantic, crossref, opencitations, nature_scraper
"""

import sys
import os
import json
import logging
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (get_journal_config, get_citation_client_config, get_available_citation_clients,
                   get_default_journals, get_default_citation_clients, 
                   get_journal_first_articles_dir, get_journal_same_age_articles_dir,
                   ANALYSIS_RESULTS_DIR, HISTOGRAM_BINS, HISTOGRAM_FIGURE_SIZE, HISTOGRAM_DPI, 
                   MAX_CITATION_COUNT_FOR_HIST, HISTOGRAM_SPLIT_YEAR_BMC, PLOT_COLORS, LOG_LEVEL, LOG_FORMAT,
                   AGGREGATE_FIGURE_SIZE, AGGREGATE_GRID_ROWS, AGGREGATE_GRID_COLS, 
                   AGGREGATE_TEXT_SIZE, AGGREGATE_DPI,
                   META_AGGREGATE_FIGURE_SIZE, META_AGGREGATE_GRID_ROWS, META_AGGREGATE_GRID_COLS,
                   META_AGGREGATE_TEXT_SIZE, META_AGGREGATE_DPI)

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT
    )

def load_article_metadata(file_path: Path) -> Optional[Dict]:
    """Load article metadata from JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logging.error(f"Error loading {file_path}: {e}")
        return None

def load_same_age_articles(journal_key: str, year: int) -> List[Dict]:
    """Load all comparison articles for a given journal and year"""
    same_age_dir = get_journal_same_age_articles_dir(journal_key)
    year_dir = same_age_dir / str(year)
    
    if not year_dir.exists():
        logging.warning(f"No comparison articles directory for {journal_key} in {year}")
        return []
    
    articles = []
    for json_file in year_dir.glob("*.json"):
        article_data = load_article_metadata(json_file)
        if article_data:
            articles.append(article_data)
    
    logging.info(f"Loaded {len(articles)} comparison articles for {journal_key} in {year}")
    return articles

def load_article_1(journal_key: str, year: int) -> Optional[Dict]:
    """Load Article #1 for a given journal and year"""
    first_articles_dir = get_journal_first_articles_dir(journal_key)
    pattern = f"{year}_article_1_*.json"
    article_files = list(first_articles_dir.glob(pattern))
    
    if not article_files:
        logging.warning(f"No Article #1 found for {journal_key} in {year}")
        return None
    
    return load_article_metadata(article_files[0])

def extract_citation_counts_from_articles(articles: List[Dict], client_key: str) -> Dict[str, Optional[int]]:
    """Extract citation counts for a specific client from saved article data"""
    citation_counts = {}
    
    for article in articles:
        article_data = article.get('article_data', {})
        doi = article_data.get('doi')
        
        if doi:
            # Extract citation count for the specified client from saved data
            citation_data = article.get('citation_counts', {})
            client_data = citation_data.get(client_key, {})
            citation_count = client_data.get('citation_count')
            citation_counts[doi] = citation_count
    
    return citation_counts

def create_individual_histogram(year: int, journal_key: str, client_key: str,
                              same_age_citations: List[int], article_1_citations: Optional[int],
                              save_dir: Path) -> None:
    """Create and save individual histogram for specific year, journal, and client"""
    
    plt.figure(figsize=HISTOGRAM_FIGURE_SIZE)
    
    # Filter out None values and apply max limit if specified
    valid_citations = [c for c in same_age_citations if c is not None]
    if MAX_CITATION_COUNT_FOR_HIST:
        valid_citations = [c for c in valid_citations if c <= MAX_CITATION_COUNT_FOR_HIST]
    
    if valid_citations:
        # Use dynamic bins like v1 (at least 20 bins, more if needed)
        bins = max(30, len(set(valid_citations)))
        plt.hist(valid_citations, bins=bins, alpha=0.7, 
                color=PLOT_COLORS['same_age_articles'], edgecolor='black',
                label=f'Comparison Articles ({len(valid_citations)} papers)')
        
        # Add Article #1 marker if available
        if article_1_citations is not None and (not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST):
            plt.axvline(article_1_citations, color=PLOT_COLORS['article_1'], 
                       linewidth=2, linestyle='--', label=f'Article #1 ({article_1_citations} citations)')
        
        # Calculate statistics (but don't plot them as lines)
        mean_citations = np.mean(valid_citations)
        median_citations = np.median(valid_citations)
        std_dev_citations = np.std(valid_citations)
        
        # Remove the axvline plots for mean and median to match v1 style
        # plt.axvline(mean_citations, color='orange', linewidth=2, linestyle=':', label=f'Mean ({mean_citations:.1f})')
        # plt.axvline(median_citations, color='purple', linewidth=2, linestyle=':', label=f'Median ({median_citations:.1f})')
        
        # Formatting
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)
        
        plt.xlabel('Citation Count')
        plt.ylabel('Number of Articles')
        plt.title(f'{journal_config["name"]} - {year}\nCitation Analysis using {client_config["name"]}')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Add statistics text box (matching v1 style)
        stats_text = f"""Statistics for Comparison Articles:
Total articles: {len(valid_citations)}
Mean citations: {mean_citations:.1f}
Median citations: {median_citations:.1f}
Standard Deviation: {std_dev_citations:.1f}
Max citations: {max(valid_citations)}
Min citations: {min(valid_citations)}"""
        
        if article_1_citations is not None:
            percentile = np.sum(np.array(valid_citations) <= article_1_citations) / len(valid_citations) * 100
            stats_text += f"\n\nArticle #1 percentile: {percentile:.1f}%"
        
        # plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
        #         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    else:
        # plt.text(0.5, 0.5, 'No citation data available', transform=plt.gca().transAxes, 
        #         ha='center', va='center', fontsize=16)
        plt.title(f'No Data - {journal_key} - {year} - {client_key}')
    
    # Save plot
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean names for filename
    clean_journal = journal_key.replace(' ', '_').lower()
    filename = f"{clean_journal}_{client_key}_{year}_individual.png"
    filename_no_title = f"{clean_journal}_{client_key}_{year}_individual_no_title.png"
    filepath = save_dir / filename
    filepath_no_title = save_dir / filename_no_title
    
    # Save plot with title
    plt.tight_layout()
    plt.savefig(filepath, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    # Save plot without title
    current_title = plt.gca().get_title()
    plt.title('')  # Remove title
    plt.tight_layout()
    plt.savefig(filepath_no_title, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    plt.close()
    
    logging.info(f"Saved individual histogram: {filename} and {filename_no_title}")

def create_meta_histogram(journal_key: str, client_key: str, years_data: Dict[int, Dict],
                         save_dir: Path) -> None:
    """Create normalized meta-histogram for all years of a journal-client combination"""
    
    plt.figure(figsize=HISTOGRAM_FIGURE_SIZE)
    
    all_normalized_data = []
    all_article_1_normalized = []
    valid_years = []
    
    for year, data in years_data.items():
        same_age_citations = data.get('same_age_citations', [])
        article_1_citations = data.get('article_1_citations')
        
        # Filter valid citations
        valid_citations = [c for c in same_age_citations if c is not None]
        if MAX_CITATION_COUNT_FOR_HIST:
            valid_citations = [c for c in valid_citations if c <= MAX_CITATION_COUNT_FOR_HIST]
        
        if valid_citations and len(valid_citations) >= 5:  # Minimum threshold for normalization
            # Calculate mean and std for this year
            mean_citations = np.mean(valid_citations)
            std_citations = np.std(valid_citations)
            
            # Avoid division by zero
            if std_citations == 0:
                logging.warning(f"Standard deviation is 0 for year {year}, skipping normalization")
                continue
            
            # Normalize using z-score: (x - mean) / std
            normalized_citations = [(c - mean_citations) / std_citations for c in valid_citations]
            all_normalized_data.extend(normalized_citations)
            
            # Calculate Article #1 normalized value for this year
            if article_1_citations is not None:
                if not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST:
                    article_1_normalized = (article_1_citations - mean_citations) / std_citations
                    all_article_1_normalized.append(article_1_normalized)
            
            valid_years.append(year)
    
    if all_normalized_data:
        # Use dynamic bins like v1 (50 bins to match aggregate_plotter.py)
        bins = 50
        
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)

        plt.hist(all_normalized_data, bins=bins, alpha=0.7,
                color=PLOT_COLORS['meta_histogram'], edgecolor='black',
                label=f'{journal_config["name"]}\n{client_config["name"]}\ncomparison articles (n={len(all_normalized_data)})', density=True)

        # Add Article #1 normalized values with year labels
        if all_article_1_normalized:
            # Create list of (normalized_value, year) tuples for labeling
            article_1_with_years = []
            year_idx = 0
            for year in sorted(valid_years):
                year_data = years_data[year]
                article_1_citations = year_data.get('article_1_citations')
                if article_1_citations is not None:
                    same_age_citations = year_data.get('same_age_citations', [])
                    valid_citations = [c for c in same_age_citations if c is not None]
                    if MAX_CITATION_COUNT_FOR_HIST:
                        valid_citations = [c for c in valid_citations if c <= MAX_CITATION_COUNT_FOR_HIST]
                    
                    if valid_citations and len(valid_citations) >= 5:
                        mean_citations = np.mean(valid_citations)
                        std_citations = np.std(valid_citations)
                        if std_citations > 0:
                            if not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST:
                                normalized_val = (article_1_citations - mean_citations) / std_citations
                                article_1_with_years.append((normalized_val, year))
            
            # Draw vertical lines and add year labels
            for normalized_val, year in article_1_with_years:
                plt.axvline(normalized_val, color=PLOT_COLORS['article_1'], 
                           alpha=0.6, linewidth=1, linestyle='--')
                # Add year label at the top of the line
                plt.text(normalized_val, plt.ylim()[1] * 0.95, str(year), 
                        rotation=90, ha='center', va='top', fontsize=8, color=PLOT_COLORS['article_1'])
            
            # Add mean Article #1 normalized value if multiple years
            if len(all_article_1_normalized) > 1:
                mean_normalized = np.mean(all_article_1_normalized)
                # plt.axvline(mean_normalized, color=PLOT_COLORS['article_1'], 
                #            linewidth=2, linestyle='-', 
                #            label=f'Mean Article #1 Z-score ({mean_normalized:.2f})')
        
        # Formatting
        
        plt.xlabel('Normalized Citation Count\n(Standard Deviations from Year Mean)')
        plt.ylabel('Density (a.u.)')
        plt.title(f'{journal_config["name"]} - Meta Analysis\nNormalized Citation Distribution using {client_config["name"]}')
        plt.legend()
        
        # Add small a) b) or c) based on journal name, to top left corener outside the plot.
        # journal_to_abc = {"scientific_reports": "a)", "nature_communications": "b)", "bmc_public_health": "c)"}
        # abc_label = journal_to_abc.get(journal_key, "")
        # if abc_label:
        #     plt.text(-0.13, 1, abc_label, transform=plt.gca().transAxes,
        #             verticalalignment='top', fontsize=14)

        plt.grid(True, alpha=0.3)
        
        # Add statistics
        years_str = f"{min(valid_years)}-{max(valid_years)}" if len(valid_years) > 1 else str(valid_years[0])
        stats_text = f'Years: {years_str} ({len(valid_years)} years)\nTotal articles: {len(all_normalized_data)}'
        if all_article_1_normalized:
            stats_text += f'\nArticle #1 papers: {len(all_article_1_normalized)}'
        
        # plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes,
        #         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    else:
        plt.text(0.5, 0.5, 'Insufficient data for meta-analysis', transform=plt.gca().transAxes,
                ha='center', va='center', fontsize=16)
        plt.title(f'No Data - {journal_key} - {client_key} - Meta')
    
    # Save plot
    save_dir.mkdir(parents=True, exist_ok=True)
    
    clean_journal = journal_key.replace(' ', '_').lower()
    filename = f"{clean_journal}_{client_key}_meta.png"
    filename_no_title = f"{clean_journal}_{client_key}_meta_no_title.png"
    filepath = save_dir / filename
    filepath_no_title = save_dir / filename_no_title
    
    # Save plot with title
    plt.tight_layout()
    plt.savefig(filepath, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    # Save plot without title
    current_title = plt.gca().get_title()
    plt.title('')  # Remove title
    plt.tight_layout()
    plt.savefig(filepath_no_title, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    plt.close()
    
    logging.info(f"Saved meta histogram: {filename} and {filename_no_title}")

def create_meta_meta_histogram(journal_key: str, all_clients_data: Dict[str, Dict[int, Dict]],
                              save_dir: Path) -> None:
    """Create meta-meta histogram aggregating all client types for a journal"""
    
    plt.figure(figsize=HISTOGRAM_FIGURE_SIZE)
    
    all_normalized_data = []
    all_article_1_normalized = []
    client_colors = ['skyblue', 'lightgreen', 'lightcoral', 'gold', 'plum']
    
    for i, (client_key, years_data) in enumerate(all_clients_data.items()):
        client_normalized_data = []
        client_article_1_normalized = []
        
        for year, data in years_data.items():
            same_age_citations = data.get('same_age_citations', [])
            article_1_citations = data.get('article_1_citations')
            
            # Filter valid citations
            valid_citations = [c for c in same_age_citations if c is not None]
            if MAX_CITATION_COUNT_FOR_HIST:
                valid_citations = [c for c in valid_citations if c <= MAX_CITATION_COUNT_FOR_HIST]
            
            if valid_citations and len(valid_citations) >= 5:
                # Calculate mean and std for this year
                mean_citations = np.mean(valid_citations)
                std_citations = np.std(valid_citations)
                
                # Avoid division by zero
                if std_citations == 0:
                    continue
                
                # Normalize using z-score: (x - mean) / std
                normalized_citations = [(c - mean_citations) / std_citations for c in valid_citations]
                client_normalized_data.extend(normalized_citations)
                
                # Calculate Article #1 normalized value for this year
                if article_1_citations is not None:
                    if not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST:
                        article_1_normalized = (article_1_citations - mean_citations) / std_citations
                        client_article_1_normalized.append(article_1_normalized)
        
        # Plot this client's data
        if client_normalized_data:
            client_config = get_citation_client_config(client_key)
            color = client_colors[i % len(client_colors)]
            
            # Use 50 bins to match aggregate_plotter.py
            bins = 50
            plt.hist(client_normalized_data, bins=bins, alpha=0.5,
                    color=color, edgecolor='black', 
                    label=f'{client_config["name"]} (n={len(client_normalized_data)})',
                    density=True)
            
            all_normalized_data.extend(client_normalized_data)
            all_article_1_normalized.extend(client_article_1_normalized)
    
    # Add overall Article #1 normalized values
    if all_article_1_normalized:
        # Draw vertical lines for each Article #1
        for normalized_val in all_article_1_normalized:
            plt.axvline(normalized_val, color=PLOT_COLORS['article_1'], 
                       alpha=0.3, linewidth=1, linestyle='--')
        
        # Add mean Article #1 normalized value
        mean_normalized = np.mean(all_article_1_normalized)
        # plt.axvline(mean_normalized, color=PLOT_COLORS['article_1'],
        #            linewidth=2, linestyle='-',
        #            label=f'Mean Article #1 Z-score ({mean_normalized:.2f})')
    
    # Formatting
    journal_config = get_journal_config(journal_key)
    
    plt.xlabel('Normalized Citation Count\n(Standard Deviations from Year Mean)')
    plt.ylabel('Density (a.u.)')
    plt.title(f'{journal_config["name"]} - Complete Meta Analysis\nNormalized Citation Distribution (All Sources)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Add statistics
    # stats_text = f'Total articles: {len(all_normalized_data)}\nSources: {len(all_clients_data)}'
    # plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes,
    #         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Save plot
    save_dir.mkdir(parents=True, exist_ok=True)
    
    clean_journal = journal_key.replace(' ', '_').lower()
    filename = f"{clean_journal}_meta_meta.png"
    filename_no_title = f"{clean_journal}_meta_meta_no_title.png"
    filepath = save_dir / filename
    filepath_no_title = save_dir / filename_no_title
    
    # Save plot with title
    plt.tight_layout()
    plt.savefig(filepath, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    # Save plot without title
    current_title = plt.gca().get_title()
    plt.title('')  # Remove title
    plt.tight_layout()
    plt.savefig(filepath_no_title, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    plt.close()
    
    logging.info(f"Saved meta-meta histogram: {filename} and {filename_no_title}")

def create_individual_histogram_subplot(ax, year: int, journal_key: str, client_key: str,
                                      same_age_citations: List[int], article_1_citations: Optional[int],
                                      row: int, col: int, total_rows: int, total_cols: int) -> None:
    """Create an individual histogram on a given subplot axis for the aggregate figure"""
    
    # Filter out None values and apply max limit if specified
    valid_citations = [c for c in same_age_citations if c is not None]
    if MAX_CITATION_COUNT_FOR_HIST:
        valid_citations = [c for c in valid_citations if c <= MAX_CITATION_COUNT_FOR_HIST]
    
    if valid_citations:
        # Use fewer bins for small plots
        bins = max(15, min(25, len(set(valid_citations))))
        ax.hist(valid_citations, bins=bins, alpha=0.7, 
                color=PLOT_COLORS['same_age_articles'], edgecolor='black')
        
        # Add Article #1 marker if available
        if article_1_citations is not None and (not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST):
            ax.axvline(article_1_citations, color=PLOT_COLORS['article_1'], 
                      linewidth=2, linestyle='--')
        
        # Add axes labels only for bottom row and first column
        if row == total_rows - 1:  # Bottom row
            ax.set_xlabel('Citation Count', fontsize=AGGREGATE_TEXT_SIZE)
        if col == 0:  # First column
            ax.set_ylabel('Number of Articles', fontsize=AGGREGATE_TEXT_SIZE)
            
        # Always keep ticks and tick labels for each subplot
        ax.tick_params(axis='both', which='major', labelsize=AGGREGATE_TEXT_SIZE-1)
        ax.grid(True, alpha=0.3)
        
        # Add centered text box with journal, client, and year info
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)
        
        info_text = f"{journal_config.get('short_name', journal_key)}\n{client_config.get('short_name', client_key)}\n{year}"
        ax.text(0.5, 0.5, info_text, transform=ax.transAxes, ha='center', va='center',
                fontsize=AGGREGATE_TEXT_SIZE, bbox=dict(boxstyle='round,pad=0.3', 
                facecolor='white', alpha=0.8, edgecolor='black', linewidth=0.5))
        
    else:
        # No data available
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)
        
        info_text = f"No Data\n{journal_config.get('short_name', journal_key)}\n{client_config.get('short_name', client_key)}\n{year}"
        ax.text(0.5, 0.5, info_text, transform=ax.transAxes, ha='center', va='center',
                fontsize=AGGREGATE_TEXT_SIZE, bbox=dict(boxstyle='round,pad=0.3', 
                facecolor='lightgray', alpha=0.8, edgecolor='black', linewidth=0.5))
        
        # Add axes labels only for bottom row and first column
        if row == total_rows - 1:  # Bottom row
            ax.set_xlabel('Citation Count', fontsize=AGGREGATE_TEXT_SIZE)
        if col == 0:  # First column
            ax.set_ylabel('Number of Articles', fontsize=AGGREGATE_TEXT_SIZE)
            
        # Always keep ticks and tick labels for each subplot
        ax.tick_params(axis='both', which='major', labelsize=AGGREGATE_TEXT_SIZE-1)

def create_aggregate_histogram_figures(all_data: Dict[str, Dict[str, Dict[int, Dict]]], save_dir: Path) -> None:
    """Create multiple 7x4 grid aggregate figures with all individual histograms"""
    
    # Collect all histogram data in order: by journal, then by year, then by client
    # This way each row will contain all 4 clients for a given journal/year combination
    histogram_data = []
    
    # Iterate through journals, then years, then clients
    for journal_key in get_default_journals():
        if journal_key not in all_data:
            continue
            
        journal_config = get_journal_config(journal_key)
        excluded_years = set(journal_config.get('excluded_years', []))
        analysis_years = [y for y in journal_config['analysis_years'] if y not in excluded_years]
        
        # For each year in this journal
        for year in sorted(analysis_years):
            # Then for each client for this year
            for client_key in get_default_citation_clients():
                if client_key not in all_data[journal_key]:
                    continue
                    
                client_data = all_data[journal_key][client_key]
                
                if year in client_data and client_data[year].get('success'):
                    year_data = client_data[year]
                    histogram_data.append({
                        'year': year,
                        'journal_key': journal_key,
                        'client_key': client_key,
                        'same_age_citations': year_data.get('same_age_citations', []),
                        'article_1_citations': year_data.get('article_1_citations')
                    })
    
    # Calculate number of figures needed
    max_plots_per_figure = AGGREGATE_GRID_ROWS * AGGREGATE_GRID_COLS
    total_histograms = len(histogram_data)
    num_figures = (total_histograms + max_plots_per_figure - 1) // max_plots_per_figure  # Ceiling division
    
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Create multiple figures if needed
    for figure_num in range(num_figures):
        start_idx = figure_num * max_plots_per_figure
        end_idx = min(start_idx + max_plots_per_figure, total_histograms)
        current_figure_data = histogram_data[start_idx:end_idx]
        
        # Create figure
        fig, axes = plt.subplots(AGGREGATE_GRID_ROWS, AGGREGATE_GRID_COLS, 
                                figsize=AGGREGATE_FIGURE_SIZE)
        
        # Flatten axes for easier indexing
        axes_flat = axes.flatten()
        
        # Create histograms for this figure
        for i, data in enumerate(current_figure_data):
            ax = axes_flat[i]
            # Calculate row and column position
            row = i // AGGREGATE_GRID_COLS
            col = i % AGGREGATE_GRID_COLS
            
            create_individual_histogram_subplot(
                ax=ax,
                year=data['year'],
                journal_key=data['journal_key'],
                client_key=data['client_key'],
                same_age_citations=data['same_age_citations'],
                article_1_citations=data['article_1_citations'],
                row=row,
                col=col,
                total_rows=AGGREGATE_GRID_ROWS,
                total_cols=AGGREGATE_GRID_COLS
            )
        
        # Hide unused subplots
        for i in range(len(current_figure_data), max_plots_per_figure):
            axes_flat[i].set_visible(False)
        
        # Adjust layout
        plt.tight_layout(pad=0.3, h_pad=0.4, w_pad=0.3)
        
        # Save the figure
        if num_figures == 1:
            filename = "aggregate_histograms.png"
        else:
            filename = f"aggregate_histograms_part_{figure_num + 1}_of_{num_figures}.png"
        
        filepath = save_dir / filename
        plt.savefig(filepath, dpi=AGGREGATE_DPI, bbox_inches='tight')
        plt.close()
        
        logging.info(f"Saved aggregate histogram figure: {filename} ({len(current_figure_data)} histograms)")
    
    logging.info(f"Created {num_figures} aggregate figure(s) with {total_histograms} total histograms")

def create_meta_aggregate_figure(all_data: Dict[str, Dict[str, Dict[int, Dict]]], save_dir: Path) -> None:
    """Create a 3x4 grid aggregate figure with meta histograms for all journals and clients"""
    
    # Collect meta histogram data for each journal-client combination
    meta_data = []
    
    # Iterate through journals and clients to collect meta data
    for journal_key in get_default_journals():
        if journal_key not in all_data:
            continue
            
        for client_key in get_default_citation_clients():
            if client_key not in all_data[journal_key]:
                continue
                
            years_data = all_data[journal_key][client_key]
            
            # Calculate normalized data for this journal-client combination (same logic as create_meta_histogram)
            all_normalized_data = []
            all_article_1_normalized = []
            valid_years = []
            
            for year, data in years_data.items():
                if not data.get('success'):
                    continue
                    
                same_age_citations = data.get('same_age_citations', [])
                article_1_citations = data.get('article_1_citations')
                
                # Filter valid citations
                valid_citations = [c for c in same_age_citations if c is not None]
                if MAX_CITATION_COUNT_FOR_HIST:
                    valid_citations = [c for c in valid_citations if c <= MAX_CITATION_COUNT_FOR_HIST]
                
                if valid_citations and len(valid_citations) >= 5:  # Minimum threshold for normalization
                    # Calculate mean and std for this year
                    mean_citations = np.mean(valid_citations)
                    std_citations = np.std(valid_citations)
                    
                    # Avoid division by zero
                    if std_citations == 0:
                        continue
                    
                    # Normalize using z-score: (x - mean) / std
                    normalized_citations = [(c - mean_citations) / std_citations for c in valid_citations]
                    all_normalized_data.extend(normalized_citations)
                    
                    # Calculate Article #1 normalized value for this year
                    if article_1_citations is not None:
                        if not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST:
                            article_1_normalized = (article_1_citations - mean_citations) / std_citations
                            all_article_1_normalized.append(article_1_normalized)
                    
                    valid_years.append(year)
            
            # Only add if we have sufficient data
            if all_normalized_data:
                meta_data.append({
                    'journal_key': journal_key,
                    'client_key': client_key,
                    'normalized_data': all_normalized_data,
                    'article_1_normalized': all_article_1_normalized,
                    'valid_years': valid_years
                })
    
    if not meta_data:
        logging.warning("No meta histogram data available for aggregate figure")
        return
    
    # Create figure with 3x4 grid (3 journals x 4 clients)
    fig, axes = plt.subplots(META_AGGREGATE_GRID_ROWS, META_AGGREGATE_GRID_COLS, 
                            figsize=META_AGGREGATE_FIGURE_SIZE)
    
    # Flatten axes for easier indexing
    axes_flat = axes.flatten()
    
    # Create meta histograms for this figure
    for i, data in enumerate(meta_data):
        if i >= len(axes_flat):
            break
            
        ax = axes_flat[i]
        
        # Calculate row and column position
        row = i // META_AGGREGATE_GRID_COLS
        col = i % META_AGGREGATE_GRID_COLS
        
        # Create the meta histogram subplot
        create_meta_histogram_subplot(
            ax=ax,
            journal_key=data['journal_key'],
            client_key=data['client_key'],
            normalized_data=data['normalized_data'],
            article_1_normalized=data['article_1_normalized'],
            valid_years=data['valid_years'],
            row=row,
            col=col,
            total_rows=META_AGGREGATE_GRID_ROWS,
            total_cols=META_AGGREGATE_GRID_COLS
        )
    
    # Hide unused subplots
    for i in range(len(meta_data), len(axes_flat)):
        axes_flat[i].set_visible(False)
    
    # Adjust layout
    plt.tight_layout(pad=0.3, h_pad=0.4, w_pad=0.3)
    
    # Save the figure
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = "meta_aggregate_histograms.png"
    filepath = save_dir / filename
    plt.savefig(filepath, dpi=META_AGGREGATE_DPI, bbox_inches='tight')
    plt.close()
    
    logging.info(f"Saved meta aggregate histogram figure: {filename} ({len(meta_data)} meta histograms)")

def create_meta_histogram_subplot(ax, journal_key: str, client_key: str, normalized_data: list,
                                 article_1_normalized: list, valid_years: list,
                                 row: int, col: int, total_rows: int, total_cols: int) -> None:
    """Create a meta histogram subplot with the same styling as individual meta histograms"""
    
    if normalized_data:
        # Use dynamic bins like the original meta histogram (50 bins)
        bins = 50
        
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)
        
        # Create histogram
        ax.hist(normalized_data, bins=bins, alpha=0.7,
                color=PLOT_COLORS['meta_histogram'], edgecolor='black', density=True)
        
        # Add Article #1 normalized values with year labels
        if article_1_normalized and valid_years:
            # Draw vertical lines for each article #1
            for i, (norm_val, year) in enumerate(zip(article_1_normalized, sorted(valid_years))):
                ax.axvline(norm_val, color=PLOT_COLORS['article_1'], 
                          alpha=0.6, linewidth=1, linestyle='--')
                # Add year label at the top of the line
                ax.text(norm_val, ax.get_ylim()[1] * 0.95, str(year), 
                       rotation=90, ha='center', va='top', fontsize=6, color=PLOT_COLORS['article_1'])
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Add centered text box with journal/client info
        journal_short = journal_config.get('short_name', journal_config['name'])
        client_short = client_config.get('short_name', client_config['name'])
        years_str = f"{min(valid_years)}-{max(valid_years)}" if len(valid_years) > 1 else str(valid_years[0])
        
        text_content = f"{journal_short}\n{client_short}\n{years_str}"
        ax.text(0.5, 0.5, text_content, transform=ax.transAxes,
                ha='center', va='center', fontsize=META_AGGREGATE_TEXT_SIZE,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    else:
        # No data case
        ax.text(0.5, 0.5, 'No Data', transform=ax.transAxes,
                ha='center', va='center', fontsize=META_AGGREGATE_TEXT_SIZE)
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)
        journal_short = journal_config.get('short_name', journal_config['name'])
        client_short = client_config.get('short_name', client_config['name'])
        ax.text(0.5, 0.3, f"{journal_short}\n{client_short}", transform=ax.transAxes,
                ha='center', va='center', fontsize=META_AGGREGATE_TEXT_SIZE)
    
    # Set axis labels only on bottom row and first column
    if row == total_rows - 1:
        ax.set_xlabel('Normalized Citation Count\n(Standard Deviations from Year Mean)')
    else:
        ax.set_xlabel('')
    
    if col == 0:
        ax.set_ylabel('Density (a.u.)')
    else:
        ax.set_ylabel('')
    
    # Keep tick marks and labels for all subplots
    ax.tick_params(axis='both', which='major', labelsize=6)

def create_bmc_split_histogram(journal_key: str, client_key: str, years_data: Dict[int, Dict],
                              save_dir: Path) -> None:
    """Create BMC split histogram showing normalized citation distributions for pre-2012 and 2012+ periods"""
    
    if journal_key != 'bmc_public_health':
        return  # Only create for BMC Public Health
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(HISTOGRAM_FIGURE_SIZE[0], HISTOGRAM_FIGURE_SIZE[1] * 1.5))
    
    # Separate data into two periods
    pre_2012_normalized = []
    post_2012_normalized = []
    pre_2012_article_1 = []
    post_2012_article_1 = []
    pre_2012_years = []
    post_2012_years = []
    
    for year, data in years_data.items():
        if not data.get('success'):
            continue
            
        same_age_citations = data.get('same_age_citations', [])
        article_1_citations = data.get('article_1_citations')
        
        # Filter valid citations
        valid_citations = [c for c in same_age_citations if c is not None]
        if MAX_CITATION_COUNT_FOR_HIST:
            valid_citations = [c for c in valid_citations if c <= MAX_CITATION_COUNT_FOR_HIST]
        
        if valid_citations and len(valid_citations) >= 5:
            # Calculate mean and std for this year
            mean_citations = np.mean(valid_citations)
            std_citations = np.std(valid_citations)
            
            # Avoid division by zero
            if std_citations == 0:
                continue
            
            # Normalize using z-score: (x - mean) / std
            normalized_citations = [(c - mean_citations) / std_citations for c in valid_citations]
            
            if year <= HISTOGRAM_SPLIT_YEAR_BMC:
                pre_2012_normalized.extend(normalized_citations)
                pre_2012_years.append(year)
                if article_1_citations is not None:
                    if not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST:
                        article_1_normalized = (article_1_citations - mean_citations) / std_citations
                        pre_2012_article_1.append((article_1_normalized, year))
            else:
                post_2012_normalized.extend(normalized_citations)
                post_2012_years.append(year)
                if article_1_citations is not None:
                    if not MAX_CITATION_COUNT_FOR_HIST or article_1_citations <= MAX_CITATION_COUNT_FOR_HIST:
                        article_1_normalized = (article_1_citations - mean_citations) / std_citations
                        post_2012_article_1.append((article_1_normalized, year))
    
    # Determine common x-axis range
    all_data = pre_2012_normalized + post_2012_normalized
    if all_data:
        x_min = min(all_data) - 0.5
        x_max = max(all_data) + 0.5
        bins = 50
        
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)
        
        # Top subplot: Pre-2012 data
        if pre_2012_normalized:
            ax1.hist(pre_2012_normalized, bins=bins, alpha=0.7, range=(x_min, x_max),
                    color=PLOT_COLORS['meta_histogram'], edgecolor='black', density=True)
            
            # Add Article #1 markers
            for norm_val, year in pre_2012_article_1:
                ax1.axvline(norm_val, color=PLOT_COLORS['article_1'], 
                           alpha=0.6, linewidth=1, linestyle='--')
                ax1.text(norm_val, ax1.get_ylim()[1] * 0.95, str(year), 
                        rotation=90, ha='center', va='top', fontsize=8, color=PLOT_COLORS['article_1'])
            
            years_str = f"{min(pre_2012_years)}-{max(pre_2012_years)}" if len(pre_2012_years) > 1 else str(pre_2012_years[0])
            ax1.set_title(f'BMC Public Health ({client_config["name"]})\nPre-{HISTOGRAM_SPLIT_YEAR_BMC + 1} Period ({years_str})\nn = {len(pre_2012_normalized)} articles')
        else:
            ax1.text(0.5, 0.5, f'No data for pre-{HISTOGRAM_SPLIT_YEAR_BMC + 1} period', 
                    transform=ax1.transAxes, ha='center', va='center')
            ax1.set_title(f'BMC Public Health ({client_config["name"]})\nPre-{HISTOGRAM_SPLIT_YEAR_BMC + 1} Period - No Data')
        
        ax1.set_ylabel('Density (a.u.)')
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(x_min, x_max)
        
        # Bottom subplot: 2012+ data
        if post_2012_normalized:
            ax2.hist(post_2012_normalized, bins=bins, alpha=0.7, range=(x_min, x_max),
                    color=PLOT_COLORS['meta_histogram'], edgecolor='black', density=True)
            
            # Add Article #1 markers
            for norm_val, year in post_2012_article_1:
                ax2.axvline(norm_val, color=PLOT_COLORS['article_1'], 
                           alpha=0.6, linewidth=1, linestyle='--')
                ax2.text(norm_val, ax2.get_ylim()[1] * 0.95, str(year), 
                        rotation=90, ha='center', va='top', fontsize=8, color=PLOT_COLORS['article_1'])
            
            years_str = f"{min(post_2012_years)}-{max(post_2012_years)}" if len(post_2012_years) > 1 else str(post_2012_years[0])
            ax2.set_title(f'BMC Public Health ({client_config["name"]})\nPost-{HISTOGRAM_SPLIT_YEAR_BMC} Period ({years_str})\nn = {len(post_2012_normalized)} articles')
        else:
            ax2.text(0.5, 0.5, f'No data for Post-{HISTOGRAM_SPLIT_YEAR_BMC} period', 
                    transform=ax2.transAxes, ha='center', va='center')
            ax2.set_title(f'BMC Public Health ({client_config["name"]})\nPost-{HISTOGRAM_SPLIT_YEAR_BMC} Period - No Data')
        
        ax2.set_xlabel('Normalized Citation Count\n(Standard Deviations from Year Mean)')
        ax2.set_ylabel('Density (a.u.)')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(x_min, x_max)
        
        # Add overall title
        fig.suptitle(f'{journal_config["name"]} - Split Period Analysis\nUsing {client_config["name"]}', 
                    fontsize=14, y=0.95)
    
    else:
        # No data case
        ax1.text(0.5, 0.5, 'No data available', transform=ax1.transAxes, ha='center', va='center')
        ax2.text(0.5, 0.5, 'No data available', transform=ax2.transAxes, ha='center', va='center')
        journal_config = get_journal_config(journal_key)
        client_config = get_citation_client_config(client_key)
        fig.suptitle(f'No Data - {journal_key} - {client_key} - Split', fontsize=14, y=0.95)
    
    # Save plot with titles
    save_dir.mkdir(parents=True, exist_ok=True)
    
    clean_journal = journal_key.replace(' ', '_').lower()
    filename = f"{clean_journal}_{client_key}_split_histograms.png"
    filename_no_title = f"{clean_journal}_{client_key}_split_histograms_no_title.png"
    filepath = save_dir / filename
    filepath_no_title = save_dir / filename_no_title
    
    plt.tight_layout()
    plt.savefig(filepath, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    # Create no-title version
    # Remove titles and adjust layout for closer panels
    fig.suptitle('')  # Remove main title
    ax1.set_title('')  # Remove subplot titles
    ax2.set_title('')
    
    # Remove x-axis ticks and labels from top subplot for compactness
    ax1.set_xticks([])
    ax1.set_xlabel('')
    
    # Add text boxes in lower right corner with subtitle information
    if pre_2012_normalized:
        years_str = f"{min(pre_2012_years)}-{max(pre_2012_years)}" if len(pre_2012_years) > 1 else str(pre_2012_years[0])
        info_text = f'BMC Public Health ({client_config["name"]})\nPre-{HISTOGRAM_SPLIT_YEAR_BMC} Period ({years_str})\nn = {len(pre_2012_normalized)} articles'
        ax1.text(0.98, 0.06, info_text, transform=ax1.transAxes, ha='right', va='bottom',
                fontsize=8, bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='black'))
    
    if post_2012_normalized:
        years_str = f"{min(post_2012_years)}-{max(post_2012_years)}" if len(post_2012_years) > 1 else str(post_2012_years[0])
        info_text = f'BMC Public Health ({client_config["name"]})\nPost-{HISTOGRAM_SPLIT_YEAR_BMC} Period ({years_str})\nn = {len(post_2012_normalized)} articles'
        ax2.text(0.98, 0.06, info_text, transform=ax2.transAxes, ha='right', va='bottom',
                fontsize=8, bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='black'))

    # Adjust layout for closer panels (minimize whitespace)
    plt.subplots_adjust(hspace=0.01)  # Minimal vertical space between subplots
    plt.tight_layout(pad=0.2)
    plt.savefig(filepath_no_title, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    plt.close()
    
    logging.info(f"Saved BMC split histogram: {filename} and {filename_no_title}")

def analyze_year(year: int, journal_key: str, client_key: str) -> Dict:
    """Analyze citation counts for a single year"""
    
    logging.info(f"Analyzing {year} for {journal_key} using {client_key}")
    
    # Load articles
    same_age_articles = load_same_age_articles(journal_key, year)
    article_1 = load_article_1(journal_key, year)
    
    if not same_age_articles:
        logging.warning(f"No comparison articles found for {year}")
        return {'year': year, 'success': False, 'error': 'No comparison articles found'}
    
    # Get citation counts from saved data
    same_age_citation_counts = extract_citation_counts_from_articles(same_age_articles, client_key)
    
    article_1_citations = None
    if article_1:
        article_1_citation_counts = extract_citation_counts_from_articles([article_1], client_key)
        if article_1_citation_counts:
            # Get the citation count for the article (there should only be one)
            article_1_citations = next(iter(article_1_citation_counts.values()), None)
    
    # Extract citation counts as lists
    same_age_citations = list(same_age_citation_counts.values())
    valid_same_age_citations = [c for c in same_age_citations if c is not None]
    
    # Create individual histogram
    journal_client_dir = ANALYSIS_RESULTS_DIR / journal_key / client_key
    create_individual_histogram(
        year=year,
        journal_key=journal_key, 
        client_key=client_key,
        same_age_citations=same_age_citations,
        article_1_citations=article_1_citations,
        save_dir=journal_client_dir
    )
    
    # Prepare results
    results = {
        'year': year,
        'success': True,
        'same_age_count': len(same_age_articles),
        'same_age_citations_found': len(valid_same_age_citations),
        'article_1_found': article_1 is not None,
        'article_1_citations': article_1_citations,
        'same_age_citations': same_age_citations
    }
    
    if valid_same_age_citations:
        results.update({
            'same_age_mean': np.mean(valid_same_age_citations),
            'same_age_median': np.median(valid_same_age_citations),
            'same_age_std': np.std(valid_same_age_citations)
        })
    
    logging.info(f"Successfully analyzed {year}: {len(valid_same_age_citations)} articles with citations")
    return results

def process_journal_client_combination(journal_key: str, client_key: str) -> Dict:
    """Process all years for a specific journal-client combination"""
    
    logging.info(f"Processing {journal_key} with {client_key}")
    
    # Get configuration
    journal_config = get_journal_config(journal_key)
    excluded_years = set(journal_config.get('excluded_years', []))
    analysis_years = [y for y in journal_config['analysis_years'] if y not in excluded_years]
    
    results = {
        'journal_key': journal_key,
        'client_key': client_key,
        'years_data': {},
        'successful_years': [],
        'errors': []
    }
    
    # Process each year
    for year in sorted(analysis_years):
        try:
            year_results = analyze_year(year, journal_key, client_key)
            results['years_data'][year] = year_results
            
            if year_results.get('success'):
                results['successful_years'].append(year)
            
        except Exception as e:
            error_msg = f"Error analyzing {year}: {e}"
            logging.error(error_msg)
            results['errors'].append(error_msg)
    
    # Create meta histogram and BMC split histogram if we have data
    if results['successful_years']:
        try:
            journal_client_dir = ANALYSIS_RESULTS_DIR / journal_key / client_key
            create_meta_histogram(
                journal_key=journal_key,
                client_key=client_key,
                years_data=results['years_data'],
                save_dir=journal_client_dir
            )
            
            # Create BMC-specific split histogram
            create_bmc_split_histogram(
                journal_key=journal_key,
                client_key=client_key,
                years_data=results['years_data'],
                save_dir=journal_client_dir
            )
            
        except Exception as e:
            error_msg = f"Error creating meta histogram: {e}"
            logging.error(error_msg)
            results['errors'].append(error_msg)
    
    return results

def process_journal(journal_key: str, client_keys: List[str] = None) -> Dict:
    """Process a journal with multiple citation clients"""
    
    logging.info(f"Processing journal: {journal_key}")
    
    if client_keys is None:
        client_keys = get_available_citation_clients()
    
    journal_results = {
        'journal_key': journal_key,
        'client_results': {},
        'all_clients_data': {}
    }
    
    # Process each client
    for client_key in client_keys:
        try:
            client_results = process_journal_client_combination(journal_key, client_key)
            journal_results['client_results'][client_key] = client_results
            
            # Store data for meta-meta histogram
            if client_results['successful_years']:
                journal_results['all_clients_data'][client_key] = client_results['years_data']
                
        except Exception as e:
            logging.error(f"Error processing {journal_key} with {client_key}: {e}")
    
    # Create meta-meta histogram
    if journal_results['all_clients_data']:
        try:
            journal_dir = ANALYSIS_RESULTS_DIR / journal_key
            create_meta_meta_histogram(
                journal_key=journal_key,
                all_clients_data=journal_results['all_clients_data'],
                save_dir=journal_dir
            )
        except Exception as e:
            logging.error(f"Error creating meta-meta histogram for {journal_key}: {e}")
    
    return journal_results

def process_multiple_journals(journal_keys: List[str] = None, client_keys: List[str] = None) -> Dict:
    """Process multiple journals with multiple citation clients"""
    
    if journal_keys is None:
        journal_keys = get_default_journals()
    
    if client_keys is None:
        client_keys = get_default_citation_clients()
    
    print("=" * 80)
    print("MULTI-JOURNAL CITATION ANALYSIS v2")
    print("=" * 80)
    print(f"📚 Processing {len(journal_keys)} journals: {', '.join(journal_keys)}")
    print(f"📊 Using {len(client_keys)} citation clients: {', '.join(client_keys)}")
    
    overall_results = {
        'journals_processed': [],
        'journal_results': {},
        'total_histograms_created': 0,
        'total_errors': []
    }
    
    for i, journal_key in enumerate(journal_keys, 1):
        try:
            print(f"\n{'='*20} JOURNAL {i}/{len(journal_keys)} {'='*20}")
            
            # Process this journal with all clients
            journal_results = process_journal(journal_key, client_keys)
            overall_results['journal_results'][journal_key] = journal_results
            
            # Track overall stats
            journal_success = any(len(client_results['successful_years']) > 0 
                                for client_results in journal_results['client_results'].values())
            
            if journal_success:
                overall_results['journals_processed'].append(journal_key)
                
                # Count histograms created (rough estimate)
                for client_results in journal_results['client_results'].values():
                    years_count = len(client_results['successful_years'])
                    # Individual + meta histograms per client, plus meta-meta per journal
                    overall_results['total_histograms_created'] += years_count + 1
                
                # Add meta-meta histogram
                overall_results['total_histograms_created'] += 1
            
            # Collect errors
            for client_results in journal_results['client_results'].values():
                if client_results.get('errors'):
                    overall_results['total_errors'].extend(client_results['errors'])
                
        except Exception as e:
            error_msg = f"Fatal error processing journal {journal_key}: {e}"
            logging.error(error_msg)
            overall_results['total_errors'].append(error_msg)
    
    # Create aggregate figure with all data
    if overall_results['journals_processed']:
        try:
            print(f"\n{'='*20} CREATING AGGREGATE FIGURE {'='*20}")
            
            # Collect all data from journal results
            all_data = {}
            for journal_key, journal_results in overall_results['journal_results'].items():
                if journal_key in overall_results['journals_processed']:
                    all_data[journal_key] = {}
                    for client_key, client_results in journal_results['client_results'].items():
                        if client_results['successful_years']:
                            all_data[journal_key][client_key] = client_results['years_data']
            
            # Create the aggregate figures
            create_aggregate_histogram_figures(all_data, ANALYSIS_RESULTS_DIR)
            # Note: actual count of figures created is logged in the function
            
            # Create the meta aggregate figure
            create_meta_aggregate_figure(all_data, ANALYSIS_RESULTS_DIR)
            
            logging.info("Successfully created aggregate histogram figure")
            
        except Exception as e:
            error_msg = f"Error creating aggregate figure: {e}"
            logging.error(error_msg)
            overall_results['total_errors'].append(error_msg)
    
    return overall_results

def print_summary(results: Dict):
    """Print summary of analysis results (single journal)"""
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    
    journal_key = results['journal_key']
    journal_config = get_journal_config(journal_key)
    
    print(f"📖 Journal: {journal_config['name']}")
    
    for client_key, client_results in results['client_results'].items():
        client_config = get_citation_client_config(client_key)
        successful_years = client_results['successful_years']
        errors = client_results['errors']
        
        print(f"\n📊 {client_config['name']}:")
        print(f"   ✅ Successfully analyzed: {len(successful_years)} years")
        if successful_years:
            print(f"      Years: {', '.join(map(str, sorted(successful_years)))}")
        
        if errors:
            print(f"   ❌ Errors: {len(errors)}")
    
    print(f"\n💾 Output directory: {ANALYSIS_RESULTS_DIR / journal_key}")

def print_multi_journal_summary(results: Dict):
    """Print summary of multi-journal analysis results"""
    print("\n" + "=" * 80)
    print("MULTI-JOURNAL ANALYSIS SUMMARY")
    print("=" * 80)
    
    journals_processed = results['journals_processed']
    total_journals = len(results['journal_results'])
    total_histograms = results['total_histograms_created']
    total_errors = len(results['total_errors'])
    
    print(f"📚 Journals analyzed successfully: {len(journals_processed)}/{total_journals}")
    
    if journals_processed:
        print(f"   Success: {', '.join(journals_processed)}")
    
    failed_journals = [j for j in results['journal_results'].keys() if j not in journals_processed]
    if failed_journals:
        print(f"   Failed: {', '.join(failed_journals)}")
    
    print(f"📊 Estimated histograms created: {total_histograms}")
    
    if total_errors:
        print(f"❌ Total errors: {total_errors}")
        print("   (See individual journal summaries above for details)")
    
    # Print detailed results for each journal and client
    print(f"\n📖 Detailed Results by Journal:")
    for journal_key, journal_results in results['journal_results'].items():
        journal_config = get_journal_config(journal_key)
        print(f"\n   📖 {journal_config['name']}:")
        
        for client_key, client_results in journal_results['client_results'].items():
            client_config = get_citation_client_config(client_key)
            successful_years = client_results['successful_years']
            errors = len(client_results.get('errors', []))
            
            status = "✅" if successful_years else "❌"
            print(f"      {status} {client_config['name']}: {len(successful_years)} years analyzed" +
                  (f", {errors} errors" if errors > 0 else ""))
    
    print(f"\n💾 Output directory: {ANALYSIS_RESULTS_DIR}")
    print(f"   Individual journal results in: {ANALYSIS_RESULTS_DIR}/<journal_name>/<client_name>/")

def main():
    """Main function"""
    setup_logging()
    
    # Configuration - modify these as needed
    JOURNAL_KEYS = None  # None = use default journals, or specify list like ["nature_communications"] for single journal
    CLIENT_KEYS = None   # None = use default clients, or specify list like ["semantic"] for single client
    
    try:
        results = process_multiple_journals(JOURNAL_KEYS, CLIENT_KEYS)
        print_multi_journal_summary(results)
        
        # Check if any analysis was successful
        if results['journals_processed']:
            print(f"\n🎉 Citation analysis completed successfully!")
            print(f"   Successfully analyzed {len(results['journals_processed'])} out of {len(results['journal_results'])} journals")
            sys.exit(0)
        else:
            print(f"\n❌ No journals were analyzed successfully")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)#
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logging.exception("Fatal error details:")
        sys.exit(1)

if __name__ == "__main__":
    main()
