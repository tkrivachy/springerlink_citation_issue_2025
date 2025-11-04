#!/usr/bin/env python3
"""
Configuration file for Citation Analysis v7
Focused on collecting complete article metadata from journals using only Crossref API
Starting from current year (2025) and moving backward chronologically
"""

import os
from pathlib import Path
from datetime import datetime

# =============================================================================
# DIRECTORY PATHS
# =============================================================================

# Base directory
BASE_DIR = Path(__file__).parent

# Data directories
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = DATA_DIR / "results"
RAW_DATA_DIR = DATA_DIR / "raw_responses"

# Create directories if they don't exist
for directory in [DATA_DIR, RESULTS_DIR, RAW_DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# =============================================================================
# API CONFIGURATION
# =============================================================================

# Crossref API Settings (polite usage)
CROSSREF_EMAIL = "email@domain.eu"  # Replace with your email
CROSSREF_BASE_URL = "https://api.crossref.org"
CROSSREF_REQUEST_DELAY = 1.0  # Seconds between requests
CROSSREF_TIMEOUT = 30
CROSSREF_ROWS_PER_REQUEST = 1000  # Max articles per request
CROSSREF_MAX_RETRIES = 3

# =============================================================================
# JOURNAL CONFIGURATION
# =============================================================================

# Available journals - easily add new ones here
JOURNALS = {
    "bmc_public_health": {
        "name": "BMC Public Health",
        "issn": "1471-2458",
        "publisher": "BioMed Central",
        "description": "Open access public health journal"
    },
    "nature_communications": {
        "name": "Nature Communications",
        "issn": "2041-1723",
        "publisher": "Nature Publishing Group",
        "description": "Multidisciplinary open access journal"
    },
    "scientific_reports": {
        "name": "Scientific Reports",
        "issn": "2045-2322",
        "publisher": "Nature Publishing Group", 
        "description": "Open access multidisciplinary journal"
    }
}

# =============================================================================
# ACTIVE JOURNAL SELECTION - CHANGE THIS LINE TO SWITCH JOURNALS
# =============================================================================
# Available options: "bmc_public_health", "nature_communications", "scientific_reports"

ACTIVE_JOURNAL_KEY = "scientific_reports"
BMC_SPLIT_YEAR = None

# Set the default journal based on active selection
DEFAULT_JOURNAL = JOURNALS[ACTIVE_JOURNAL_KEY]

# =============================================================================
# COLLECTION SETTINGS
# =============================================================================

# Current year (starting point)
CURRENT_YEAR = datetime.now().year
START_YEAR = CURRENT_YEAR  # Start from current year
END_YEAR = 2000  # Go back to this year (can be adjusted)

# Data collection settings
COLLECT_FULL_METADATA = True
INCLUDE_CITATION_COUNT = True
INCLUDE_VOLUME_INFO = True
INCLUDE_ARTICLE_NUMBER = True

# Output formats
SAVE_AS_JSON = True
SAVE_AS_CSV = True
SAVE_RAW_RESPONSES = False

# =============================================================================
# ANALYSIS SETTINGS
# =============================================================================

# Year split for analysis - set to None for single ranking, or year for split analysis
# Example: SPLIT_AT_YEAR = 2020 creates two rankings: ≤2020 and >2020
if ACTIVE_JOURNAL_KEY == "bmc_public_health":
    SPLIT_AT_YEAR = BMC_SPLIT_YEAR  # Change to a year (e.g., 2020) to enable split analysis
else:
    SPLIT_AT_YEAR = None  # No split analysis for other journals

# =============================================================================
# FIGURE SETTINGS
# =============================================================================

# Scientific figure settings for publication
SCIENTIFIC_FIGURE_SIZE = (12, 4)  # Width, height in inches for 3-panel figure
SCIENTIFIC_DPI = 300  # High DPI for publication quality
SCIENTIFIC_FONT_SIZE = 10  # Small font size for publication

# Subplot and inset settings
INSET_WIDTH_PERCENT = 68  # Width of inset as percentage of main plot
INSET_HEIGHT_PERCENT = 68  # Height of inset as percentage of main plot
MAX_ARTICLE_1_LINES = 1000  # Maximum number of article #1 vertical lines to show
ARTICLE_1_LINE_ALPHA = 0.7  # Transparency of article #1 vertical lines
ARTICLE_1_LINE_WIDTH = 1.0  # Line width of article #1 vertical lines

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = DATA_DIR / "v7_collection.log"

# =============================================================================
# REQUIRED FIELDS FOR ARTICLE METADATA
# =============================================================================

REQUIRED_FIELDS = [
    'doi',
    'title', 
    'authors',
    'published_date',
    'volume',
    'issue',
    'page',
    'article_number',
    'citation_count',
    'publisher'
]

OPTIONAL_FIELDS = [
    'abstract',
    'keywords',
    'subject_areas',
    'language',
    'license'
]