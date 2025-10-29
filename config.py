#!/usr/bin/env python3
"""
Configuration file for Citation Analysis v2
Contains all settings, API keys, journal information, and paths
No dotenv dependencies - all configuration is in this file
"""

import os
from pathlib import Path

# =============================================================================
# DIRECTORY PATHS (Windows/Linux compatible)
# =============================================================================

# Base directory - modify this for your system
BASE_DIR = Path(__file__).parent

# Data directories
DATA_DIR = BASE_DIR / "data"
ANALYSIS_RESULTS_DIR = DATA_DIR / "analysis_results"
RAW_RESPONSE_DIR = ANALYSIS_RESULTS_DIR / "raw_responses"

# Create base directories if they don't exist
for directory in [DATA_DIR, ANALYSIS_RESULTS_DIR, RAW_RESPONSE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# =============================================================================
# API KEYS - MODIFY THESE FOR YOUR SETUP
# =============================================================================

# Springer Nature API Keys
API_KEY_META = "blablablablablalblablalb"
API_KEY_OPENACCESS = "blablablablablalblablalb"

# Other API Keys (if needed)
SEMANTIC_SCHOLAR_API_KEY = "blablablablablalblablalb"  # Recommended, can be None for rate-limited access
CROSSREF_EMAIL = "email@domain.eu"  # For polite Crossref usage

# Web Scraper Settings
SCRAPER_DELAY = 1.0  # Seconds between web scraping requests (be respectful)
SCRAPER_MAX_RETRIES = 3  # Maximum retries for failed scraping attempts

# =============================================================================
# JOURNAL CONFIGURATIONS
# =============================================================================

# Available journals - add more as needed
JOURNALS = {
    "nature_communications": {
        "name": "Nature Communications",
        "short_name": "Nat. Comm.",
        "issn": "2041-1723",
        "is_open_access": True,
        "start_year": 2010,
        "start_month": 4,
        "start_day": 12,
        "analysis_years": list(range(2018, 2026)),  # Years to include in analysis
        "excluded_years": [2022]  # Years to exclude from histograms
    },
    "bmc_public_health": {
        "name": "BMC Public Health",
        "short_name": "BMC Pub. H.",
        "issn": "1471-2458",
        "is_open_access": True,
        "start_year": 2001, #2001
        "start_month": 1, #1
        "start_day": 1, #30
        "analysis_years": list(range(2002, 2026)),
        "excluded_years": []
    },
    "scientific_reports": {
        "name": "Scientific Reports",
        "short_name": "Sci. Rep.",
        "issn": "2045-2322",
        "is_open_access": True,
        "start_year": 2011,
        "start_month": 6,
        "start_day": 14,
        "analysis_years": list(range(2019, 2026)),
        "excluded_years": []
    }
}

# Default list of journals to process (for batch operations)
DEFAULT_JOURNALS = ["scientific_reports", "nature_communications", "bmc_public_health"]
# To narrow down to e.g. only BMC Public Health, uncomment below:
# DEFAULT_JOURNALS = ["bmc_public_health"]

# =============================================================================
# CITATION CLIENTS CONFIGURATION
# =============================================================================

# Available citation clients
CITATION_CLIENTS = {
    "semantic": {
        "name": "Semantic Scholar",
        "short_name": "Semantic Scholar",
        "description": "Semantic Scholar API for citation counts",
        "enabled": True
    },
    "crossref": {
        "name": "Crossref",
        "short_name": "Crossref",
        "description": "Crossref API for citation counts", 
        "enabled": True
    },
    "opencitations": {
        "name": "OpenCitations",
        "short_name": "OpenCitations",
        "description": "OpenCitations API for citation counts",
        "enabled": True
    },
    "nature_scraper": {
        "name": "Journal Website",
        "short_name": "Journal website",
        "description": "Web scraping citation counts from journal websites",
        "enabled": True
    }
}

# Default list of citation clients to use (for batch operations)
DEFAULT_CITATION_CLIENTS = ["semantic", "crossref", "opencitations", "nature_scraper"]

# DEFAULT_CITATION_CLIENTS = ["crossref"] 
# semantic turned off for now because it requires an API key.
# OpenCitations works but responses are not so robust - many times we get missing data.
# nature_scraper is also an option, not recommended for citation count gathering, but useful for plotting already existing data.


# =============================================================================
# ARTICLE COLLECTION SETTINGS
# =============================================================================

# Minimum articles to collect for comparison with Article #1
# Ultra-optimized search uses intelligent day estimation to minimize API calls
MIN_ARTICLES_FOR_COMPARISON = 15

# Maximum months to expand when looking for articles (used in fallback scenarios)
MAX_MONTHS_TO_EXPAND = 12

# Citation count caching control
# If True, forces fresh API calls for all articles, ignoring cached citation counts
# If False, uses cached citation counts when available (recommended if you do fresh data collection so you can stop and resume)
OVERWRITE_PREVIOUS_CITATION_COUNT = True

# Note: The system now uses ultra-optimized search strategies:
# - Week-by-week Article #1 search (stops when found)
# - Intelligent day estimation for companion articles  
# - Massive API call reduction (~95% fewer calls)
# - Small range queries to avoid daily limit impact

# =============================================================================
# SPRINGER API SETTINGS
# =============================================================================

# Springer API configuration
SPRINGER_BASE_URL = "https://api.springernature.com"
SPRINGER_BATCH_SIZE = 25  # Articles per request (max 25 for basic access)
SPRINGER_REQUEST_DELAY = 1.0  # Seconds between requests

# Available Springer API endpoints and formats
SPRINGER_ENDPOINTS = {
    "meta_v1": {
        "json": f"{SPRINGER_BASE_URL}/meta/v1/json",
        "jsonp": f"{SPRINGER_BASE_URL}/meta/v1/jsonp", 
        "pam": f"{SPRINGER_BASE_URL}/meta/v1/pam",
        "jats": f"{SPRINGER_BASE_URL}/meta/v1/jats"
    },
    "meta_v2": {
        "json": f"{SPRINGER_BASE_URL}/meta/v2/json",
        "jsonp": f"{SPRINGER_BASE_URL}/meta/v2/jsonp",
        "pam": f"{SPRINGER_BASE_URL}/meta/v2/pam", 
        "jats": f"{SPRINGER_BASE_URL}/meta/v2/jats"
    },
    "openaccess": {
        "json": f"{SPRINGER_BASE_URL}/openaccess/json",
        "jsonp": f"{SPRINGER_BASE_URL}/openaccess/jsonp",
        "pam": f"{SPRINGER_BASE_URL}/openaccess/pam",
        "jats": f"{SPRINGER_BASE_URL}/openaccess/jats"
    }
}

# =============================================================================
# RAW RESPONSE CHECK SETTINGS
# =============================================================================

# DOI to use for testing raw API responses
TEST_DOI = "10.1038/s41534-020-00305-x"

# Number of random DOIs to test (in addition to TEST_DOI)
RANDOM_NUMBER_OF_DOIS = 3

# Which endpoints and formats to test
TEST_ENDPOINTS = ["meta_v1", "meta_v2", "openaccess"]
TEST_FORMATS = ["json", "jsonp", "pam", "jats"]

# =============================================================================
# ANALYSIS SETTINGS
# =============================================================================

# Histogram settings
HISTOGRAM_BINS = 50
HISTOGRAM_FIGURE_SIZE = (5, 4)
HISTOGRAM_DPI = 300

# Citation count limits for histograms (None for no limit)
MAX_CITATION_COUNT_FOR_HIST = None

# BMC-specific settings
HISTOGRAM_SPLIT_YEAR_BMC = 2011  # Year to split BMC histograms (pre/post comparison)

# Colors for different data series in plots
PLOT_COLORS = {
    "same_age_articles": "skyblue",
    "article_1": "red",
    "meta_histogram": "green"
}

# Aggregate figure settings (7x4 grid for A4 paper)
AGGREGATE_FIGURE_SIZE = (11.7, 16.5)  # A4 paper dimensions in inches (210x297mm)
AGGREGATE_GRID_ROWS = 7
AGGREGATE_GRID_COLS = 4
AGGREGATE_TEXT_SIZE = 6
AGGREGATE_DPI = 300

# Meta aggregate figure settings (3x4 grid: 3 journals x 4 clients)
META_AGGREGATE_FIGURE_SIZE = (11.7, 8.5)  # A4 width, smaller height for 3 rows
META_AGGREGATE_GRID_ROWS = 3
META_AGGREGATE_GRID_COLS = 4
META_AGGREGATE_TEXT_SIZE = 8
META_AGGREGATE_DPI = 300

# =============================================================================
# LOGGING SETTINGS
# =============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_journal_config(journal_key):
    """Get configuration for a specific journal"""
    if journal_key not in JOURNALS:
        raise ValueError(f"Journal '{journal_key}' not found in configuration")
    
    return JOURNALS[journal_key]

def get_citation_client_config(client_key):
    """Get configuration for a specific citation client"""
    if client_key not in CITATION_CLIENTS:
        raise ValueError(f"Citation client '{client_key}' not found in configuration")
    
    return CITATION_CLIENTS[client_key]

def get_available_journals():
    """Get list of available journal keys"""
    return list(JOURNALS.keys())

def get_available_citation_clients():
    """Get list of available citation client keys"""
    return [key for key, config in CITATION_CLIENTS.items() if config["enabled"]]

def get_default_journals():
    """Get list of default journals to process"""
    return DEFAULT_JOURNALS.copy()

def get_default_citation_clients():
    """Get list of default citation clients to process"""
    # Filter to only return enabled clients
    available_clients = get_available_citation_clients()
    return [client for client in DEFAULT_CITATION_CLIENTS if client in available_clients]

def get_journal_data_dir(journal_key):
    """Get the data directory for a specific journal"""
    journal_config = get_journal_config(journal_key)  # This validates the journal key
    journal_dir = DATA_DIR / journal_key
    journal_dir.mkdir(parents=True, exist_ok=True)
    return journal_dir

def get_journal_first_articles_dir(journal_key):
    """Get the first_articles directory for a specific journal"""
    journal_dir = get_journal_data_dir(journal_key)
    first_articles_dir = journal_dir / "first_articles"
    first_articles_dir.mkdir(parents=True, exist_ok=True)
    return first_articles_dir

def get_journal_same_age_articles_dir(journal_key):
    """Get the same_age_articles directory for a specific journal"""
    journal_dir = get_journal_data_dir(journal_key)
    same_age_articles_dir = journal_dir / "same_age_articles"
    same_age_articles_dir.mkdir(parents=True, exist_ok=True)
    return same_age_articles_dir

def validate_config():
    """Validate the configuration settings"""
    errors = []
    
    # Check API keys
    if not API_KEY_META or API_KEY_META == "your_springer_api_key_here":
        errors.append("API_KEY_META is not set properly")
    
    # Check journal configurations
    for journal_key, journal_config in JOURNALS.items():
        required_fields = ["name", "issn", "start_year", "analysis_years"]
        for field in required_fields:
            if field not in journal_config:
                errors.append(f"Journal '{journal_key}' missing required field: {field}")
    
    # Check default settings
    for journal_key in DEFAULT_JOURNALS:
        if journal_key not in JOURNALS:
            errors.append(f"DEFAULT_JOURNALS contains invalid journal '{journal_key}'")
    
    for client_key in DEFAULT_CITATION_CLIENTS:
        if client_key not in CITATION_CLIENTS:
            errors.append(f"DEFAULT_CITATION_CLIENTS contains invalid client '{client_key}'")
    
    if errors:
        raise ValueError("Configuration errors found:\n" + "\n".join(f"- {error}" for error in errors))
    
    return True

# Validate configuration on import
if __name__ != "__main__":
    try:
        validate_config()
    except ValueError as e:
        print(f"⚠️  Configuration validation failed: {e}")
        print("Please update config.py with proper settings before running scripts.")
