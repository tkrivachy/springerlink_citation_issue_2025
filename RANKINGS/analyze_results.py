#!/usr/bin/env python3
"""
Analysis script for Citation Analysis v7
Analyzes collected article data and generates insights
"""

import json
import csv
from pathlib import Path
import sys
import os
from collections import defaultdict, Counter
from datetime import datetime
import pandas as pd

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import RESULTS_DIR, DEFAULT_JOURNAL

class ArticleAnalyzer:
    """Analyzer for collected article data"""
    
    def __init__(self):
        self.results_dir = RESULTS_DIR
        
    def load_all_articles(self) -> list:
        """Load all collected articles from result files"""
        all_articles = []
        
        # Try CSV files first (they're smaller and stay under 99MB limit)
        csv_articles_loaded = False
        year_dirs = [d for d in self.results_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        
        for year_dir in sorted(year_dirs, reverse=True):
            csv_files = list(year_dir.glob("*_articles.csv"))
            for csv_file in csv_files:
                try:
                    print(f"Loading articles from CSV: {csv_file}")
                    df = pd.read_csv(csv_file)
                    # Convert DataFrame rows to dictionaries
                    year_articles = df.to_dict('records')
                    all_articles.extend(year_articles)
                    csv_articles_loaded = True
                except Exception as e:
                    print(f"Error loading CSV {csv_file}: {e}")
        
        if csv_articles_loaded:
            print(f"Loaded {len(all_articles)} total articles from CSV files")
            return all_articles
        
        # Fallback: Look for complete JSON files
        complete_files = list(self.results_dir.glob("*_complete_*.json"))
        
        if complete_files:
            # Use the most recent complete file
            latest_file = max(complete_files, key=lambda p: p.stat().st_mtime)
            print(f"Loading articles from: {latest_file}")
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract articles from year-organized data
            for year, articles in data.items():
                all_articles.extend(articles)
                
        else:
            # Final fallback: Load from individual JSON files
            print("Loading articles from individual JSON files...")
            
            for year_dir in sorted(year_dirs, reverse=True):
                json_files = list(year_dir.glob("*.json"))
                for json_file in json_files:
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            articles = json.load(f)
                        all_articles.extend(articles)
                    except Exception as e:
                        print(f"Error loading {json_file}: {e}")
        
        print(f"Loaded {len(all_articles)} total articles")
        return all_articles
    
    def analyze_by_year(self, articles: list) -> dict:
        """Analyze articles by publication year"""
        year_stats = defaultdict(lambda: {
            'count': 0,
            'total_citations': 0,
            'volumes': set(),
            'avg_citations': 0
        })
        
        for article in articles:
            year = article.get('publication_year')
            if year:
                stats = year_stats[year]
                stats['count'] += 1
                stats['total_citations'] += article.get('citation_count', 0)
                
                volume = article.get('volume')
                if volume:
                    stats['volumes'].add(volume)
        
        # Calculate averages and convert sets to lists
        for year, stats in year_stats.items():
            if stats['count'] > 0:
                stats['avg_citations'] = stats['total_citations'] / stats['count']
            stats['volumes'] = sorted(list(stats['volumes']))
        
        return dict(year_stats)
    
    def analyze_citations(self, articles: list) -> dict:
        """Analyze citation patterns"""
        citations = [article.get('citation_count', 0) for article in articles]
        citations = [c for c in citations if c is not None]
        
        if not citations:
            return {}
        
        citations_sorted = sorted(citations, reverse=True)
        
        return {
            'total_articles_with_citations': len([c for c in citations if c > 0]),
            'total_citations': sum(citations),
            'avg_citations': sum(citations) / len(citations),
            'median_citations': citations_sorted[len(citations_sorted) // 2],
            'max_citations': max(citations),
            'min_citations': min(citations),
            'top_10_citations': citations_sorted[:10],
            'highly_cited': len([c for c in citations if c >= 100]),
            'uncited': len([c for c in citations if c == 0])
        }
    
    def analyze_volumes(self, articles: list) -> dict:
        """Analyze volume and article number patterns"""
        volumes = defaultdict(int)
        articles_with_numbers = 0
        articles_with_pages = 0
        
        for article in articles:
            volume = article.get('volume')
            if volume:
                volumes[volume] += 1
            
            if article.get('article_number'):
                articles_with_numbers += 1
            
            if article.get('page'):
                articles_with_pages += 1
        
        return {
            'unique_volumes': len(volumes),
            'volume_distribution': dict(volumes),
            'articles_with_numbers': articles_with_numbers,
            'articles_with_pages': articles_with_pages,
            'total_articles': len(articles)
        }
    
    def find_most_cited_articles(self, articles: list, top_n: int = 10) -> list:
        """Find the most cited articles"""
        articles_with_citations = [
            article for article in articles 
            if article.get('citation_count', 0) > 0
        ]
        
        sorted_articles = sorted(
            articles_with_citations,
            key=lambda x: x.get('citation_count', 0),
            reverse=True
        )
        
        return sorted_articles[:top_n]
    
    def analyze_authors(self, articles: list) -> dict:
        """Analyze author patterns"""
        author_count_distribution = Counter()
        all_authors = []
        
        for article in articles:
            authors = article.get('authors', [])
            author_count_distribution[len(authors)] += 1
            all_authors.extend(authors)
        
        author_frequency = Counter(all_authors)
        
        return {
            'total_unique_authors': len(set(all_authors)),
            'avg_authors_per_article': len(all_authors) / len(articles) if articles else 0,
            'author_count_distribution': dict(author_count_distribution),
            'most_prolific_authors': author_frequency.most_common(10)
        }
    
    def generate_report(self, articles: list) -> dict:
        """Generate comprehensive analysis report"""
        if not articles:
            return {"error": "No articles to analyze"}
        
        report = {
            'summary': {
                'total_articles': len(articles),
                'journal': DEFAULT_JOURNAL['name'],
                'analysis_timestamp': datetime.now().isoformat(),
                'date_range': self._get_date_range(articles)
            },
            'by_year': self.analyze_by_year(articles),
            'citations': self.analyze_citations(articles),
            'volumes': self.analyze_volumes(articles),
            'authors': self.analyze_authors(articles),
            'most_cited': self.find_most_cited_articles(articles)
        }
        
        return report
    
    def _get_date_range(self, articles: list) -> dict:
        """Get the date range of articles"""
        years = [
            article.get('publication_year') 
            for article in articles 
            if article.get('publication_year')
        ]
        
        if years:
            return {
                'earliest_year': min(years),
                'latest_year': max(years),
                'span_years': max(years) - min(years) + 1
            }
        return {}
    
    def save_report(self, report: dict, filename: str = None):
        """Save analysis report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_report_{timestamp}.json"
        
        filepath = self.results_dir / filename
        
        # Convert sets to lists for JSON serialization
        def convert_sets(obj):
            if isinstance(obj, set):
                return list(obj)
            elif isinstance(obj, dict):
                return {k: convert_sets(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_sets(item) for item in obj]
            return obj
        
        report_serializable = convert_sets(report)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_serializable, f, indent=2, ensure_ascii=False)
        
        print(f"Analysis report saved to: {filepath}")
        return filepath

def print_summary(report: dict):
    """Print a summary of the analysis report"""
    if 'error' in report:
        print(f"Error: {report['error']}")
        return
    
    summary = report.get('summary', {})
    citations = report.get('citations', {})
    volumes = report.get('volumes', {})
    authors = report.get('authors', {})
    
    print("\n" + "="*60)
    print("CITATION ANALYSIS v7 - REPORT SUMMARY")
    print("="*60)
    
    print(f"Journal: {summary.get('journal', 'Unknown')}")
    print(f"Total Articles: {summary.get('total_articles', 0):,}")
    
    date_range = summary.get('date_range', {})
    if date_range:
        print(f"Date Range: {date_range.get('earliest_year')} - {date_range.get('latest_year')}")
        print(f"Years Covered: {date_range.get('span_years')}")
    
    print(f"\nCITATIONS:")
    print(f"  Total Citations: {citations.get('total_citations', 0):,}")
    print(f"  Average Citations per Article: {citations.get('avg_citations', 0):.2f}")
    print(f"  Highly Cited Articles (≥100 citations): {citations.get('highly_cited', 0)}")
    print(f"  Uncited Articles: {citations.get('uncited', 0)}")
    
    print(f"\nVOLUMES & STRUCTURE:")
    print(f"  Unique Volumes: {volumes.get('unique_volumes', 0)}")
    print(f"  Articles with Article Numbers: {volumes.get('articles_with_numbers', 0)}")
    print(f"  Articles with Page Numbers: {volumes.get('articles_with_pages', 0)}")
    
    print(f"\nAUTHORS:")
    print(f"  Total Unique Authors: {authors.get('total_unique_authors', 0):,}")
    print(f"  Average Authors per Article: {authors.get('avg_authors_per_article', 0):.2f}")
    
    # Show most cited articles
    most_cited = report.get('most_cited', [])
    if most_cited:
        print(f"\nTOP 5 MOST CITED ARTICLES:")
        for i, article in enumerate(most_cited[:5], 1):
            title = article.get('title', 'Unknown Title')[:60] + "..." if len(article.get('title', '')) > 60 else article.get('title', 'Unknown Title')
            print(f"  {i}. {title}")
            print(f"     Citations: {article.get('citation_count', 0)}, Year: {article.get('publication_year', 'Unknown')}")

def main():
    """Main analysis function"""
    print("Citation Analysis v7 - Data Analyzer")
    print("="*50)
    
    analyzer = ArticleAnalyzer()
    
    # Load articles
    articles = analyzer.load_all_articles()
    
    if not articles:
        print("No articles found. Please run the collection script first.")
        return
    
    # Generate report
    print("Generating analysis report...")
    report = analyzer.generate_report(articles)
    
    # Save report
    report_file = analyzer.save_report(report)
    
    # Print summary
    print_summary(report)
    
    print(f"\nComplete analysis saved to: {report_file}")

if __name__ == "__main__":
    main()