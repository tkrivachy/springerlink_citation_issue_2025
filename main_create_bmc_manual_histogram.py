#!/usr/bin/env python3
"""
BMC Manual Histogram Creator
Creates a histogram from BMC_2012_manual_histogram.csv in the same format as main_article_info_analyzer.py.
Data for this histogram was manually collected from BMC Public Health articles published in 2012 on/near Article 1 data,
via the Wayback Machine of the Internet Archive, from webpages as they were in 2020 for Article 1 and 2021 for the other articles.
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (HISTOGRAM_FIGURE_SIZE, HISTOGRAM_DPI, PLOT_COLORS)

def load_bmc_manual_data(csv_file: str) -> list:
    """Load citation data from BMC_2012_manual_histogram.csv"""
    with open(csv_file, 'r') as f:
        lines = f.readlines()
    
    # Parse the CSV data (second line contains the citation counts)
    data_line = lines[1].strip()
    citation_counts = [int(x) for x in data_line.split(',')]
    
    return citation_counts

def create_bmc_manual_histogram(citation_data: list, save_dir: Path) -> None:
    """Create histogram in the same format as main_article_info_analyzer.py"""
    
    plt.figure(figsize=HISTOGRAM_FIGURE_SIZE)
    
    # Find Article #1 (highest citation count)
    article_1_citations = max(citation_data)
    same_age_citations = citation_data.copy()  # All data points are comparison articles
    
    # Use dynamic bins like the main analyzer (at least 30 bins, more if needed)
    bins = max(30, len(set(same_age_citations)))
    plt.hist(same_age_citations, bins=bins, alpha=0.7, 
            color=PLOT_COLORS['same_age_articles'], edgecolor='black',
            label=f'Comparison Articles ({len(same_age_citations)} papers)')
    
    # Add Article #1 marker (vertical dashed red line)
    plt.axvline(article_1_citations, color=PLOT_COLORS['article_1'], 
               linewidth=2, linestyle='--', label=f'Article #1 ({article_1_citations} citations)')
    
    # Calculate statistics
    mean_citations = np.mean(same_age_citations)
    median_citations = np.median(same_age_citations)
    std_dev_citations = np.std(same_age_citations)
    
    # Formatting (same as main analyzer)
    plt.xlabel('Citation Count')
    plt.ylabel('Number of Articles')
    plt.title(f'BMC Public Health - 2012\nCitation Analysis (Manual Data)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Set y-axis to show only integer ticks from 0 to 4
    plt.yticks([0, 1, 2, 3, 4])
    
    # Add "a)" label in top left outside plot area
    plt.text(-0.15, 1.02, 'a)', transform=plt.gca().transAxes, fontsize=12)
    
    # Add statistics text box (same format as main analyzer)
    stats_text = f"""Statistics for Comparison Articles:
Total articles: {len(same_age_citations)}
Mean citations: {mean_citations:.1f}
Median citations: {median_citations:.1f}
Standard Deviation: {std_dev_citations:.1f}
Max citations: {max(same_age_citations)}
Min citations: {min(same_age_citations)}"""
    
    # Calculate Article #1 percentile
    percentile = np.sum(np.array(same_age_citations) <= article_1_citations) / len(same_age_citations) * 100
    stats_text += f"\n\nArticle #1 percentile: {percentile:.1f}%"
    
    # Save plot
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Filenames
    filename = "bmc_public_health_manual_2012_histogram.png"
    filename_no_title = "bmc_public_health_manual_2012_histogram_no_title.png"
    filepath = save_dir / filename
    filepath_no_title = save_dir / filename_no_title
    
    # Save plot with title
    plt.tight_layout()
    plt.savefig(filepath, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    # Save plot without title
    plt.title('')  # Remove title
    plt.tight_layout()
    plt.savefig(filepath_no_title, dpi=HISTOGRAM_DPI, bbox_inches='tight')
    
    plt.close()
    
    print(f"Saved histogram with title: {filepath}")
    print(f"Saved histogram without title: {filepath_no_title}")
    print(f"\nData summary:")
    print(f"- Total articles: {len(same_age_citations)}")
    print(f"- Article #1 citations: {article_1_citations}")
    print(f"- Mean citations: {mean_citations:.1f}")
    print(f"- Median citations: {median_citations:.1f}")
    print(f"- Article #1 percentile: {percentile:.1f}%")

def main():
    """Main function"""
    # File paths
    csv_file = "BMC_2012_manual_histogram.csv"
    save_dir = Path("./data/analysis_results") / "bmc_manual_citation_count_from_2020"
    
    # Check if CSV file exists
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found in current directory")
        return
    
    # Load data
    citation_data = load_bmc_manual_data(csv_file)
    print(f"Loaded {len(citation_data)} citation counts from {csv_file}")
    print(f"Citation data: {citation_data}")
    
    # Create histogram
    create_bmc_manual_histogram(citation_data, save_dir)

if __name__ == "__main__":
    main()