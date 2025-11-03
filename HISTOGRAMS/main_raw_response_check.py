#!/usr/bin/env python3
"""
Main Raw Response Checker for Citation Analysis v2
Tests all Springer API endpoints and formats (JSON, JSONP, PAM, JATS) with configurable DOI
Single script for comprehensive API testing and comparison
"""

import sys
import os
import json
import time
import logging
import requests
import random
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (API_KEY_META, API_KEY_OPENACCESS, SPRINGER_ENDPOINTS, TEST_DOI, 
                   TEST_ENDPOINTS, TEST_FORMATS, RAW_RESPONSE_DIR, RANDOM_NUMBER_OF_DOIS,
                   SPRINGER_REQUEST_DELAY, LOG_LEVEL, LOG_FORMAT, DATA_DIR, DEFAULT_JOURNALS)

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT
    )

def collect_available_dois() -> List[str]:
    """Collect all available DOIs from the data directory"""
    dois = []
    logger = logging.getLogger(__name__)
    
    try:
        # Iterate through all journal directories
        for journal_dir in DATA_DIR.iterdir():
            if not journal_dir.is_dir() or journal_dir.name in ['analysis_results', 'raw_responses']:
                continue
                
            # Check first_articles directory
            first_articles_dir = journal_dir / "first_articles"
            if first_articles_dir.exists():
                for json_file in first_articles_dir.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        if 'article_data' in data and 'doi' in data['article_data']:
                            doi = data['article_data']['doi']
                            if doi not in dois:
                                dois.append(doi)
                                logger.debug(f"Found DOI in first_articles: {doi}")
                    except Exception as e:
                        logger.warning(f"Error reading {json_file}: {e}")
            
            # Check same_age_articles directory
            same_age_dir = journal_dir / "same_age_articles"
            if same_age_dir.exists():
                # Recursively find all JSON files in subdirectories
                for json_file in same_age_dir.rglob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        if 'article_data' in data and 'doi' in data['article_data']:
                            doi = data['article_data']['doi']
                            if doi not in dois:
                                dois.append(doi)
                                logger.debug(f"Found DOI in same_age_articles: {doi}")
                    except Exception as e:
                        logger.warning(f"Error reading {json_file}: {e}")
    
    except Exception as e:
        logger.error(f"Error collecting DOIs: {e}")
    
    logger.info(f"Collected {len(dois)} unique DOIs from data directory")
    return dois

def select_test_dois(random_count: int = RANDOM_NUMBER_OF_DOIS) -> List[str]:
    """Select DOIs for testing: configured TEST_DOI + random DOIs from data"""
    logger = logging.getLogger(__name__)
    
    # Always include the configured TEST_DOI
    test_dois = [TEST_DOI]
    
    # Collect available DOIs from data directory
    available_dois = collect_available_dois()
    
    if not available_dois:
        logger.warning("No DOIs found in data directory, using only TEST_DOI")
        return test_dois
    
    # Remove TEST_DOI from available list if it exists to avoid duplicates
    available_dois = [doi for doi in available_dois if doi != TEST_DOI]
    
    # Select random DOIs
    random_count = min(random_count, len(available_dois))
    if random_count > 0:
        random_dois = random.sample(available_dois, random_count)
        test_dois.extend(random_dois)
        logger.info(f"Selected {random_count} random DOIs from {len(available_dois)} available")
    else:
        logger.warning("No additional DOIs available for random selection")
    
    logger.info(f"Total DOIs selected for testing: {len(test_dois)}")
    for i, doi in enumerate(test_dois):
        logger.info(f"  {i+1}. {doi}")
    
    return test_dois

class SpringerAPITester:
    """Comprehensive tester for Springer Nature API endpoints"""
    
    def __init__(self):
        self.api_key_meta = API_KEY_META
        self.api_key_openaccess = API_KEY_OPENACCESS or API_KEY_META
        self.request_delay = SPRINGER_REQUEST_DELAY
        self.logger = logging.getLogger(__name__)
        
        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Citation-Analysis-v2/1.0 Raw Response Tester'
        })
        
        self.logger.info("Springer API tester initialized")
    
    def _make_request(self, endpoint: str, params: Dict, endpoint_name: str) -> Tuple[bool, Optional[str], Dict]:
        """Make API request and return success status, content, and metadata"""
        try:
            print(f"\n{'='*60}")
            print(f"🔍 Testing {endpoint_name}")
            print(f"{'='*60}")
            print(f"URL: {endpoint}")
            print(f"Parameters: {params}")
            
            start_time = time.time()
            response = self.session.get(endpoint, params=params, timeout=30)
            end_time = time.time()
            
            # Collect response metadata
            metadata = {
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'content_length': response.headers.get('content-length', 'N/A'),
                'content_type': response.headers.get('content-type', 'N/A'),
                'rate_limit_remaining': response.headers.get('x-ratelimit-remaining', 'N/A'),
                'url': endpoint,
                'params': params
            }
            
            # Print response details
            print(f"\n📊 Response Details:")
            print(f"Status Code: {metadata['status_code']}")
            print(f"Response Time: {metadata['response_time']:.3f}s")
            print(f"Content-Length: {metadata['content_length']}")
            print(f"Content-Type: {metadata['content_type']}")
            print(f"Rate Limit Remaining: {metadata['rate_limit_remaining']}")
            
            if response.status_code == 200:
                print(f"✅ Request successful")
                time.sleep(self.request_delay)
                return True, response.text, metadata
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"Error message: {response.text}")
                return False, response.text, metadata
                
        except Exception as e:
            print(f"❌ Request exception: {e}")
            metadata = {'error': str(e), 'url': endpoint, 'params': params}
            return False, None, metadata
    
    def _parse_json_response(self, content: str) -> Tuple[Optional[Dict], str]:
        """Parse JSON response and return data + summary"""
        try:
            data = json.loads(content)
            
            # Generate summary
            if isinstance(data, dict):
                summary = f"JSON Object with keys: {list(data.keys())}\n"
                
                # Look for common Springer response patterns
                if 'records' in data:
                    records = data['records']
                    summary += f"Records found: {len(records)}\n"
                    if records and isinstance(records, list):
                        sample = records[0]
                        summary += f"Sample record keys: {list(sample.keys())}\n"
                        for key in ['doi', 'title', 'creators', 'publicationName']:
                            if key in sample:
                                value = str(sample[key])[:100]
                                summary += f"{key}: {value}...\n"
                
                # Check for result metadata
                if 'result' in data:
                    result = data['result']
                    summary += f"Result type: {type(result)}\n"
                    if isinstance(result, list) and result:
                        summary += f"Result items: {len(result[0])}\n"
                        summary += f"Total available: {result[0].get('total', 'N/A')}\n"
                
            else:
                summary = f"JSON {type(data).__name__}"
            
            return data, summary
            
        except json.JSONDecodeError as e:
            return None, f"JSON Parse Error: {e}"
    
    def _parse_jsonp_response(self, content: str) -> Tuple[Optional[Dict], str]:
        """Parse JSONP response and return data + summary"""
        try:
            # Remove JSONP callback wrapper
            if '(' in content and content.strip().endswith(')'):
                start = content.find('(') + 1
                end = content.rfind(')')
                json_content = content[start:end]
                
                data = json.loads(json_content)
                
                # Generate summary similar to JSON
                summary = "JSONP Response\n"
                if isinstance(data, dict):
                    summary += f"Keys: {list(data.keys())}\n"
                    
                    if 'records' in data:
                        records = data['records']
                        summary += f"Records: {len(records)}\n"
                    
                    if 'result' in data and isinstance(data['result'], list) and data['result']:
                        summary += f"Total available: {data['result'][0].get('total', 'N/A')}\n"
                
                return data, summary
            else:
                return None, "Invalid JSONP format"
                
        except (json.JSONDecodeError, ValueError) as e:
            return None, f"JSONP Parse Error: {e}"
    
    def _parse_xml_response(self, content: str, format_type: str) -> Tuple[Optional[ET.Element], str]:
        """Parse XML response (PAM or JATS) and return root element + summary"""
        try:
            root = ET.fromstring(content)
            
            # Generate summary
            summary = f"{format_type.upper()} XML Response\n"
            summary += f"Root element: {root.tag}\n"
            summary += f"Root attributes: {root.attrib}\n"
            
            # Count children
            children = list(root)
            summary += f"Direct children: {len(children)}\n"
            
            if children:
                child_tags = {}
                for child in children:
                    tag = child.tag
                    child_tags[tag] = child_tags.get(tag, 0) + 1
                
                summary += f"Child elements: {child_tags}\n"
                
                # Look for articles in JATS format
                articles = root.findall('.//article')
                if articles:
                    summary += f"Articles found: {len(articles)}\n"
                    
                    # Sample article info
                    sample = articles[0]
                    doi_elem = sample.find('.//article-id[@pub-id-type="doi"]')
                    title_elem = sample.find('.//article-title')
                    elocation_elem = sample.find('.//elocation-id')
                    
                    if doi_elem is not None:
                        summary += f"Sample DOI: {doi_elem.text}\n"
                    if title_elem is not None:
                        title = title_elem.text[:100] if title_elem.text else "N/A"
                        summary += f"Sample title: {title}...\n"
                    if elocation_elem is not None:
                        summary += f"Sample article number: {elocation_elem.text}\n"
            
            return root, summary
            
        except ET.ParseError as e:
            return None, f"XML Parse Error: {e}"
    
    def _format_xml_pretty(self, content: str) -> str:
        """Format XML content for pretty printing"""
        try:
            root = ET.fromstring(content)
            rough_string = ET.tostring(root, 'unicode')
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        except Exception:
            return content  # Return original if formatting fails
    
    def test_endpoint_format(self, endpoint_key: str, format_key: str, test_doi: str) -> Dict:
        """Test a specific endpoint and format combination"""
        
        # Check if endpoint supports this format
        if endpoint_key not in SPRINGER_ENDPOINTS:
            return {'success': False, 'error': f'Unknown endpoint: {endpoint_key}'}
        
        if format_key not in SPRINGER_ENDPOINTS[endpoint_key]:
            return {'success': False, 'error': f'Format {format_key} not supported by {endpoint_key}'}
        
        # Prepare request
        endpoint_url = SPRINGER_ENDPOINTS[endpoint_key][format_key]
        
        # Choose appropriate API key
        if endpoint_key == 'openaccess':
            api_key = self.api_key_openaccess
        else:
            api_key = self.api_key_meta
        
        params = {
            'api_key': api_key,
            'q': f'doi:{test_doi}',
            's': 1,
            'p': 1
        }
        
        # Add callback for JSONP
        if format_key == 'jsonp':
            params['callback'] = 'springerCallback'
        
        # Make request
        endpoint_name = f"{endpoint_key.upper()} - {format_key.upper()}"
        success, content, metadata = self._make_request(endpoint_url, params, endpoint_name)
        
        # Parse response based on format
        parsed_data = None
        summary = "No content"
        
        if success and content:
            if format_key == 'json':
                parsed_data, summary = self._parse_json_response(content)
            elif format_key == 'jsonp':
                parsed_data, summary = self._parse_jsonp_response(content)
            elif format_key in ['pam', 'jats']:
                parsed_data, summary = self._parse_xml_response(content, format_key)
        
        return {
            'success': success,
            'endpoint_key': endpoint_key,
            'format_key': format_key,
            'raw_content': content,
            'parsed_data': parsed_data,
            'summary': summary,
            'metadata': metadata
        }
    
    def print_response_summary(self, result: Dict):
        """Print summary of a test result"""
        endpoint_name = f"{result['endpoint_key'].upper()} - {result['format_key'].upper()}"
        
        print(f"\n📋 {endpoint_name} - Summary:")
        print("-" * 40)
        
        if result['success']:
            print("✅ Request successful")
            print(f"Format: {result['format_key'].upper()}")
            print("\n📊 Parsed Content Summary:")
            print(result['summary'])
        else:
            print("❌ Request failed")
            if 'error' in result:
                print(f"Error: {result['error']}")
    
    def print_full_response(self, result: Dict):
        """Print full response content"""
        endpoint_name = f"{result['endpoint_key'].upper()} - {result['format_key'].upper()}"
        
        print(f"\n📄 {endpoint_name} - Full Response:")
        print("=" * 80)
        
        if result['raw_content']:
            # Format based on content type
            if result['format_key'] in ['pam', 'jats']:
                formatted_content = self._format_xml_pretty(result['raw_content'])
                print(formatted_content)
            elif result['format_key'] in ['json', 'jsonp']:
                # Try to pretty-print JSON
                try:
                    if result['format_key'] == 'jsonp':
                        # Extract JSON part from JSONP
                        content = result['raw_content']
                        if '(' in content and content.strip().endswith(')'):
                            start = content.find('(') + 1
                            end = content.rfind(')')
                            json_content = content[start:end]
                            parsed = json.loads(json_content)
                            print(f"Callback: {content[:start-1]}")
                            print("JSON Content:")
                            print(json.dumps(parsed, indent=2, ensure_ascii=False))
                        else:
                            print(content)
                    else:
                        parsed = json.loads(result['raw_content'])
                        print(json.dumps(parsed, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    print(result['raw_content'])
            else:
                print(result['raw_content'])
        else:
            print("No content available")
        
        print("=" * 80)
    
    def _format_content_for_saving(self, content: str, format_key: str) -> str:
        """Format content for pretty-printed saving"""
        try:
            if format_key == 'json':
                # Parse and format JSON with proper indentation
                parsed = json.loads(content)
                return json.dumps(parsed, indent=2, ensure_ascii=False)
            
            elif format_key == 'jsonp':
                # Extract JSON from JSONP and format it
                if '(' in content and content.strip().endswith(')'):
                    start = content.find('(') + 1
                    end = content.rfind(')')
                    callback_name = content[:start-1]
                    json_content = content[start:end]
                    
                    # Parse and format the JSON part
                    parsed = json.loads(json_content)
                    formatted_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                    
                    # Reconstruct JSONP with formatted JSON
                    return f"{callback_name}({formatted_json})"
                else:
                    return content
            
            elif format_key in ['pam', 'jats']:
                # Format XML with proper indentation
                return self._format_xml_pretty(content)
            
            else:
                # Return as-is for unknown formats
                return content
                
        except Exception as e:
            # If formatting fails, return original content
            print(f"⚠️  Warning: Could not format {format_key} content: {e}")
            return content
    
    def save_responses_to_files(self, results: Dict[str, Dict], test_doi: str):
        """Save all responses to individual files in DOI-specific subdirectory"""
        try:
            # Clean DOI for directory name
            safe_doi = test_doi.replace('/', '_').replace(':', '_').replace('.', '_')
            
            # Create DOI-specific subdirectory
            doi_dir = RAW_RESPONSE_DIR / safe_doi
            doi_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"\n💾 Saving responses for DOI: {test_doi}")
            print(f"Output directory: {doi_dir}")
            
            saved_count = 0
            
            for test_name, result in results.items():
                if result['success'] and result['raw_content']:
                    
                    # Determine file extension
                    format_key = result['format_key']
                    if format_key in ['pam', 'jats']:
                        ext = 'xml'
                    elif format_key in ['json', 'jsonp']:
                        ext = 'json' if format_key == 'json' else 'jsonp'
                    else:
                        ext = 'txt'
                    
                    # Create filename (without DOI since it's in the directory name)
                    endpoint_key = result['endpoint_key']
                    filename = f"{endpoint_key}_{format_key}.{ext}"
                    filepath = doi_dir / filename
                    
                    # Format and save content based on type
                    formatted_content = self._format_content_for_saving(result['raw_content'], format_key)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(formatted_content)
                    
                    # Save metadata
                    meta_filename = f"{endpoint_key}_{format_key}_metadata.json"
                    meta_filepath = doi_dir / meta_filename
                    
                    metadata = {
                        'endpoint': endpoint_key,
                        'format': format_key,
                        'test_doi': test_doi,
                        'safe_doi': safe_doi,
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'metadata': result['metadata'],
                        'summary': result['summary'],
                        'filename': filename
                    }
                    
                    with open(meta_filepath, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    
                    saved_count += 1
                    print(f"  💾 Saved: {filename}")
            
            print(f"💾 Successfully saved {saved_count} responses for {test_doi}")
            
            # Create summary file for this DOI
            summary_file = doi_dir / "test_summary.json"
            summary_data = {
                'test_doi': test_doi,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_tests': len(results),
                'successful_tests': saved_count,
                'success_rate': f"{saved_count/len(results)*100:.1f}%" if results else "0%",
                'test_results': {
                    test_name: {
                        'success': result['success'],
                        'endpoint': result.get('endpoint_key', 'unknown'),
                        'format': result.get('format_key', 'unknown')
                    }
                    for test_name, result in results.items()
                }
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            
            print(f"  📋 Summary saved: test_summary.json")
            
        except Exception as e:
            print(f"❌ Error saving responses: {e}")

def run_single_doi_test(test_doi: str, endpoints: List[str], formats: List[str]) -> Dict[str, Dict]:
    """Run comprehensive test for a single DOI"""
    
    tester = SpringerAPITester()
    results = {}
    
    print(f"\n🔬 Testing DOI: {test_doi}")
    print("=" * 80)
    
    # Test all combinations
    total_tests = len(endpoints) * len(formats)
    test_count = 0
    
    for endpoint_key in endpoints:
        for format_key in formats:
            test_count += 1
            test_name = f"{endpoint_key}_{format_key}"
            
            print(f"\n🧪 Test {test_count}/{total_tests}: {test_name}")
            
            result = tester.test_endpoint_format(endpoint_key, format_key, test_doi)
            results[test_name] = result
            
            # Print summary
            tester.print_response_summary(result)
    
    # Print overall summary for this DOI
    print(f"\n🔍 SUMMARY FOR DOI: {test_doi}")
    print("=" * 100)
    
    success_count = 0
    for test_name, result in results.items():
        status = "✅ Success" if result['success'] else "❌ Failed"
        endpoint_key = result.get('endpoint_key', 'unknown')
        format_key = result.get('format_key', 'unknown')
        
        # Try to get record count
        record_info = "N/A"
        if result['success'] and result.get('parsed_data'):
            if format_key == 'json' and isinstance(result['parsed_data'], dict):
                if 'records' in result['parsed_data']:
                    record_info = len(result['parsed_data']['records'])
            elif format_key in ['pam', 'jats'] and result['parsed_data'] is not None:
                articles = result['parsed_data'].findall('.//article')
                if articles:
                    record_info = len(articles)
        
        print(f"{test_name:<25} | {status:<12} | Format: {format_key:<6} | Records: {record_info}")
        
        if result['success']:
            success_count += 1
    
    print(f"\n📊 DOI Success Rate: {success_count}/{total_tests} ({success_count/total_tests*100:.1f}%)")
    
    # Save all responses for this DOI
    tester.save_responses_to_files(results, test_doi)
    
    return results

def run_comprehensive_test(test_dois: List[str] = None, endpoints: List[str] = None, 
                          formats: List[str] = None, interactive: bool = True) -> Dict[str, Dict[str, Dict]]:
    """Run comprehensive test of all specified endpoints and formats for multiple DOIs"""
    
    # Use defaults from config if not specified
    if test_dois is None:
        test_dois = select_test_dois()
    if endpoints is None:
        endpoints = TEST_ENDPOINTS
    if formats is None:
        formats = TEST_FORMATS
    
    print("🔬 SPRINGER NATURE API COMPREHENSIVE TESTER v2 - MULTI-DOI")
    print("=" * 80)
    print(f"Test DOIs: {len(test_dois)} DOIs selected")
    for i, doi in enumerate(test_dois):
        print(f"  {i+1}. {doi}")
    print(f"Endpoints: {', '.join(endpoints)}")
    print(f"Formats: {', '.join(formats)}")
    print(f"Total tests per DOI: {len(endpoints) * len(formats)}")
    print(f"Total tests overall: {len(test_dois) * len(endpoints) * len(formats)}")
    print("=" * 80)
    
    all_results = {}
    overall_success_count = 0
    overall_total_tests = 0
    
    # Test each DOI
    for doi_index, test_doi in enumerate(test_dois):
        print(f"\n{'='*100}")
        print(f"🧬 PROCESSING DOI {doi_index + 1}/{len(test_dois)}")
        print(f"{'='*100}")
        
        # Run tests for this DOI
        doi_results = run_single_doi_test(test_doi, endpoints, formats)
        all_results[test_doi] = doi_results
        
        # Update overall statistics
        doi_success_count = sum(1 for result in doi_results.values() if result['success'])
        overall_success_count += doi_success_count
        overall_total_tests += len(doi_results)
        
        print(f"\n✅ Completed DOI {doi_index + 1}/{len(test_dois)}: {test_doi}")
        print(f"   Success rate: {doi_success_count}/{len(doi_results)} ({doi_success_count/len(doi_results)*100:.1f}%)")
    
    # Print final summary
    print(f"\n{'🎉 FINAL OVERALL SUMMARY'}")
    print("=" * 100)
    print(f"Total DOIs tested: {len(test_dois)}")
    print(f"Total API calls made: {overall_total_tests}")
    print(f"Overall success rate: {overall_success_count}/{overall_total_tests} ({overall_success_count/overall_total_tests*100:.1f}%)")
    
    # Per-DOI summary
    print(f"\n📋 Per-DOI Results:")
    for test_doi, doi_results in all_results.items():
        doi_success = sum(1 for result in doi_results.values() if result['success'])
        doi_total = len(doi_results)
        print(f"  {test_doi}: {doi_success}/{doi_total} ({doi_success/doi_total*100:.1f}%)")
    
    # Analyze article numbers across all responses
    analyze_article_numbers_across_responses(all_results)
    
    return all_results

def extract_article_number_from_jats(jats_content: str) -> Optional[str]:
    """Extract article number from JATS XML content"""
    try:
        root = ET.fromstring(jats_content)
        # Look for elocation-id elements
        elocation_elements = root.findall('.//elocation-id')
        
        for elem in elocation_elements:
            if elem.text and elem.text.strip():
                return elem.text.strip()
        
        return None
    except Exception as e:
        logging.getLogger(__name__).warning(f"Error extracting article number from JATS: {e}")
        return None

def find_number_in_text(text: str, number: str, context_chars: int = 100) -> List[str]:
    """Find all occurrences of a number in text and return surrounding context"""
    matches = []
    if not text or not number:
        return matches
    
    # Convert to string to handle different data types
    text_str = str(text)
    number_str = str(number)
    
    # Find all occurrences
    start = 0
    while True:
        pos = text_str.find(number_str, start)
        if pos == -1:
            break
            
        # Extract context around the match
        context_start = max(0, pos - context_chars)
        context_end = min(len(text_str), pos + len(number_str) + context_chars)
        context = text_str[context_start:context_end]
        
        # Mark the actual match within the context
        relative_pos = pos - context_start
        marked_context = (
            context[:relative_pos] + 
            f"**{number_str}**" + 
            context[relative_pos + len(number_str):]
        )
        
        matches.append(marked_context.strip())
        start = pos + 1
    
    return matches

def analyze_article_numbers_across_responses(all_results: Dict[str, Dict[str, Dict]]):
    """Analyze article numbers from JATS and search across all response formats"""
    logger = logging.getLogger(__name__)
    
    print(f"\n{'🔍 ARTICLE NUMBER ANALYSIS ACROSS ALL RESPONSES'}")
    print("=" * 100)
    
    for doi, doi_results in all_results.items():
        print(f"\n🧬 Analyzing DOI: {doi}")
        print("-" * 80)
        
        # First, try to extract article number from JATS responses
        article_number = None
        jats_sources = []
        
        # Check all JATS format responses
        for test_name, result in doi_results.items():
            if result['success'] and result.get('format_key') == 'jats' and result.get('raw_content'):
                extracted_number = extract_article_number_from_jats(result['raw_content'])
                if extracted_number:
                    article_number = extracted_number
                    jats_sources.append(result['endpoint_key'])
        
        if not article_number:
            print(f"❌ No article number found in JATS responses for {doi}")
            continue
        
        print(f"📄 Article Number: {article_number}")
        print(f"📋 Extracted from: {', '.join(jats_sources)} JATS format(s)")
        
        # Now search for this number across all response formats
        print(f"\n🔎 Searching for article number '{article_number}' across all response formats:")
        
        found_in_formats = []
        
        for test_name, result in doi_results.items():
            if result['success'] and result.get('raw_content'):
                endpoint = result.get('endpoint_key', 'unknown')
                format_type = result.get('format_key', 'unknown')
                
                # Search for the article number in the response content
                matches = find_number_in_text(result['raw_content'], article_number)
                
                if matches:
                    found_in_formats.append(f"{endpoint}-{format_type}")
                    print(f"\n  ✅ Found in {endpoint.upper()} - {format_type.upper()}: {len(matches)} occurrence(s)")
                    
                    # Show first few matches with context
                    for i, match in enumerate(matches[:3]):  # Limit to first 3 matches per format
                        print(f"    Match {i+1}: ...{match}...")
                    
                    if len(matches) > 3:
                        print(f"    ... and {len(matches) - 3} more occurrence(s)")
        
        if found_in_formats:
            print(f"\n📊 Article number '{article_number}' found in: {', '.join(found_in_formats)}")
        else:
            print(f"\n❌ Article number '{article_number}' not found in any other response formats")
        
        # Additional analysis: check if the number appears in parsed JSON data
        print(f"\n🔍 Checking structured data fields:")
        for test_name, result in doi_results.items():
            if (result['success'] and 
                result.get('format_key') in ['json', 'jsonp'] and 
                result.get('parsed_data')):
                
                endpoint = result.get('endpoint_key', 'unknown')
                format_type = result.get('format_key', 'unknown')
                
                # Check specific fields in JSON data
                if isinstance(result['parsed_data'], dict) and 'records' in result['parsed_data']:
                    records = result['parsed_data']['records']
                    if records and isinstance(records, list):
                        record = records[0]  # Check first record
                        
                        # Check common fields where article number might appear
                        fields_to_check = [
                            'number', 'articleNumber', 'elocationId', 'startingPage', 
                            'endingPage', 'volume', 'issue', 'identifier', 'url'
                        ]
                        
                        found_fields = []
                        for field in fields_to_check:
                            if field in record:
                                field_value = str(record[field])
                                if article_number in field_value:
                                    found_fields.append(f"{field}='{field_value}'")
                        
                        if found_fields:
                            print(f"  ✅ {endpoint.upper()}-{format_type.upper()}: {', '.join(found_fields)}")

def main():
    """Main function"""
    setup_logging()
    
    # Configuration - modify these as needed
    TEST_DOIS_OVERRIDE = None  # Set to override DOI selection
    RANDOM_COUNT_OVERRIDE = None  # Set to override random DOI count
    TEST_ENDPOINTS_OVERRIDE = None  # Set to override config endpoints
    TEST_FORMATS_OVERRIDE = None  # Set to override config formats
    INTERACTIVE = True  # Set to False to skip detailed response display
    
    try:
        # Select DOIs for testing
        if TEST_DOIS_OVERRIDE:
            test_dois = TEST_DOIS_OVERRIDE
        else:
            # Use config value or override
            random_count = RANDOM_COUNT_OVERRIDE if RANDOM_COUNT_OVERRIDE is not None else RANDOM_NUMBER_OF_DOIS
            test_dois = select_test_dois(random_count)
        
        results = run_comprehensive_test(
            test_dois=test_dois,
            endpoints=TEST_ENDPOINTS_OVERRIDE,
            formats=TEST_FORMATS_OVERRIDE,
            interactive=INTERACTIVE
        )
        
        # Calculate overall success
        total_success = 0
        total_tests = 0
        for doi_results in results.values():
            for result in doi_results.values():
                total_tests += 1
                if result['success']:
                    total_success += 1
        
        if total_success > 0:
            print(f"\n🎉 Multi-DOI API testing completed!")
            print(f"   Overall success: {total_success}/{total_tests} tests successful.")
            print(f"   DOIs tested: {len(results)}")
            sys.exit(0)
        else:
            print(f"\n❌ All API tests failed across all DOIs.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
