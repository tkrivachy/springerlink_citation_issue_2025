#!/usr/bin/env python3
"""
Create a 3-panel scientific figure showing citation rankings for three journals:
Scientific Reports, Nature Communications, and BMC Public Health.

Each panel shows:
- Main plot: Linear scale citation vs rank (similar to main_analysis.py)
- Inset: Log-log scale citation vs rank in top-right corner
- Panel labels: a), b), c) in top-left

Designed for publication with configurable figure size.
"""

import json
import sys
import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import numpy as np

# ensure local package imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (RESULTS_DIR, JOURNALS, SCIENTIFIC_FIGURE_SIZE, SCIENTIFIC_DPI, SCIENTIFIC_FONT_SIZE,
                    INSET_WIDTH_PERCENT, INSET_HEIGHT_PERCENT, MAX_ARTICLE_1_LINES, 
                    ARTICLE_1_LINE_ALPHA, ARTICLE_1_LINE_WIDTH)
from main_analysis import load_collected_articles, normalize_article_row


def get_journal_data(journal_key: str, results_dir: Path) -> list:
    """Load and process data for a specific journal."""
    articles = load_collected_articles(results_dir, journal_key=journal_key)
    
    if not articles:
        print(f"No articles found for {journal_key}")
        return []
    
    # Normalize and sort articles
    normalized = [normalize_article_row(a) for a in articles]
    
    # Sort by citations desc, then by year desc, then by volume/article_number
    def sort_key(x):
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
    
    # Add ranks
    rows = []
    for idx, item in enumerate(normalized_sorted, start=1):
        item_row = item.copy()
        item_row['rank'] = idx
        rows.append(item_row)
    
    return rows


def create_panel_plot(ax, rows, journal_name, panel_label):
    """Create a single panel plot with main linear plot and log-log inset."""
    if not rows:
        ax.text(0.5, 0.5, f'No data for\n{journal_name}', 
                ha='center', va='center', transform=ax.transAxes, fontsize=SCIENTIFIC_FONT_SIZE)
        ax.set_xlabel('Rank', fontsize=SCIENTIFIC_FONT_SIZE)
        ax.set_ylabel('Citations', fontsize=SCIENTIFIC_FONT_SIZE)
        ax.text(0.05, 0.95, panel_label, transform=ax.transAxes, 
                fontsize=SCIENTIFIC_FONT_SIZE+2, va='top')
        return
    
    # Extract data
    ranks = [row['rank'] for row in rows]
    citations = [row['citations'] for row in rows]
    
    # Main linear plot
    ax.scatter(ranks, citations, alpha=0.6, s=8, color='blue')
    
    # Find and mark article #1 entries
    article_1_entries = []
    for row in rows:
        article_num = str(row.get('article_number', '')).strip()
        if article_num == '1':
            article_1_entries.append({
                'rank': row['rank'],
                'citations': row['citations'],
                'year': row['year']
            })
    
    print(f"    Found {len(article_1_entries)} article #1 entries")
    
    # Determine which article #1 entries to show (for both main plot and inset)
    lines_to_show = min(len(article_1_entries), MAX_ARTICLE_1_LINES)
    entries_to_show = []
    if lines_to_show > 0:
        # If too many, sample evenly across the years
        if len(article_1_entries) > MAX_ARTICLE_1_LINES:
            step = len(article_1_entries) // MAX_ARTICLE_1_LINES
            entries_to_show = article_1_entries[::step]
        else:
            entries_to_show = article_1_entries
            
        # Add vertical lines to main plot
        for entry in entries_to_show:
            ax.axvline(x=entry['rank'], color='red', linestyle='--', 
                      alpha=ARTICLE_1_LINE_ALPHA, linewidth=ARTICLE_1_LINE_WIDTH)
        
        print(f"    Showing {len(entries_to_show)} article #1 vertical lines")
    
    # Formatting
    ax.set_xlabel('Rank', fontsize=SCIENTIFIC_FONT_SIZE)
    ax.set_ylabel('Citations', fontsize=SCIENTIFIC_FONT_SIZE)
    ax.tick_params(axis='both', labelsize=SCIENTIFIC_FONT_SIZE-1)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)
    
    # Add panel label
    ax.text(-0.2, 1.00, panel_label, transform=ax.transAxes, 
            fontsize=SCIENTIFIC_FONT_SIZE+2, va='top')
    
    # Add journal name, with small boundary with curved corners
    journal_name_box = ax.text(0.5, 0.1, journal_name, transform=ax.transAxes,
            fontsize=SCIENTIFIC_FONT_SIZE, ha='center', va='top')
    journal_name_box.set_bbox(dict(facecolor='white', edgecolor='black', boxstyle='round,pad=0.2'))

    # Create inset for log-log plot
    # Filter out zero citations for log plot
    nonzero_data = [(r, c) for r, c in zip(ranks, citations) if c > 0]
    
    if nonzero_data and len(nonzero_data) > 10:  # Only create inset if enough data
        nonzero_ranks, nonzero_citations = zip(*nonzero_data)
        
        # Create inset axes in top-right
        inset_ax = inset_axes(ax, width=f"{INSET_WIDTH_PERCENT}%", height=f"{INSET_HEIGHT_PERCENT}%", loc='upper right')
        
        # Log-log plot in inset
        inset_ax.loglog(nonzero_ranks, nonzero_citations, 'o', alpha=0.6, markersize=2, color='blue')
        
        # Add vertical lines for article #1 entries in the inset (only non-zero citations)
        if lines_to_show > 0:
            for entry in entries_to_show:
                if entry['citations'] > 0:  # Only show lines for non-zero citations in log plot
                    inset_ax.axvline(x=entry['rank'], color='red', linestyle='--', 
                                   alpha=ARTICLE_1_LINE_ALPHA * 0.8, linewidth=ARTICLE_1_LINE_WIDTH * 0.8)
        
        # Inset formatting
        inset_ax.tick_params(axis='both', labelsize=SCIENTIFIC_FONT_SIZE-2)
        inset_ax.grid(True, alpha=0.3, which='both')
        # inset_ax.set_xlabel('Rank (log)', fontsize=SCIENTIFIC_FONT_SIZE-1)
        # inset_ax.set_ylabel('Citations (log)', fontsize=SCIENTIFIC_FONT_SIZE-1)


def main():
    """Create the 3-panel scientific figure."""
    results_dir = Path(RESULTS_DIR)
    
    # Journal configurations for the three panels
    journal_configs = [
        ("scientific_reports", "Scientific Reports", "a)"),
        ("nature_communications", "Nature Communications", "b)"),
        ("bmc_public_health", "BMC Public Health", "c)")
    ]
    
    # Set up matplotlib for publication quality
    plt.rcParams.update({
        'font.size': SCIENTIFIC_FONT_SIZE,
        'axes.linewidth': 0.8,
        'xtick.major.width': 0.8,
        'ytick.major.width': 0.8,
        'xtick.minor.width': 0.6,
        'ytick.minor.width': 0.6,
    })
    
    # Create figure with three subplots
    fig, axes = plt.subplots(1, 3, figsize=SCIENTIFIC_FIGURE_SIZE)
    # fig.suptitle('Article Citation Rankings by Journal', fontsize=SCIENTIFIC_FONT_SIZE+2, y=0.98)
    
    # Load data and create plots for each journal
    for i, (journal_key, journal_name, panel_label) in enumerate(journal_configs):
        print(f"Processing {journal_name} ({journal_key})...")
        
        # Load data for this journal
        rows = get_journal_data(journal_key, results_dir)
        print(f"  - Loaded {len(rows)} articles")
        
        if rows:
            max_citations = max(row['citations'] for row in rows)
            total_citations = sum(row['citations'] for row in rows)
            print(f"  - Max citations: {max_citations:,}")
            print(f"  - Total citations: {total_citations:,}")
        
        # Create the panel plot
        create_panel_plot(axes[i], rows, journal_name, panel_label)
    
    # Adjust layout (avoid tight_layout warning with insets)
    plt.subplots_adjust(left=0.08, right=0.95, bottom=0.15, top=0.88, wspace=0.25)
    
    # Save the figure
    output_path = results_dir / "scientific_figure_three_journals.png"
    plt.savefig(output_path, dpi=SCIENTIFIC_DPI, bbox_inches='tight', facecolor='white')
    
    # Also save as PDF for publication
    output_path_pdf = results_dir / "scientific_figure_three_journals.pdf"
    # plt.savefig(output_path_pdf, bbox_inches='tight', facecolor='white')
    
    print(f"\nScientific figure saved to:")
    print(f"  PNG: {output_path}")
    print(f"  PDF: {output_path_pdf}")
    print(f"Figure size: {SCIENTIFIC_FIGURE_SIZE[0]}\" × {SCIENTIFIC_FIGURE_SIZE[1]}\"")
    print(f"DPI: {SCIENTIFIC_DPI}")
    
    # plt.show()


if __name__ == '__main__':
    main()