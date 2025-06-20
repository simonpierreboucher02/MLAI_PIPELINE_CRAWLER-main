import os
import re
import sys
import time
import hashlib
import logging
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict, deque

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from colorama import init, Fore, Style
from tqdm import tqdm
import html2text

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.traceback import install

# Initialize Rich modules for enhanced tracebacks
install()

# Initialize Colorama for colored terminal output
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """
    Custom logging formatter that injects colors and symbols into log messages for improved readability.
    """

    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }

    SYMBOLS = {
        'INFO': '✔',
        'WARNING': '⚠',
        'ERROR': '✘',
        'CRITICAL': '✘'
    }

    def format(self, record):
        """
        Format a log record with color and symbol based on its severity level.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted log message with appropriate color and symbol.
        """
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        symbol = self.SYMBOLS.get(record.levelname, '')
        header = f"{color}{symbol} {self.formatTime(record, self.datefmt)}#"
        level = f"- {record.levelname}#"
        message = f"- {record.getMessage()}#"
        return f"{header}\n{level}\n{message}"


class MovingIndicator(threading.Thread):
    """
    A threading class that displays a dynamic moving indicator in the terminal to signal ongoing operations.
    """

    def __init__(self, delay=0.1, length=20):
        """
        Initialize the MovingIndicator thread.

        Args:
            delay (float, optional): Time delay between indicator updates in seconds. Defaults to 0.1.
            length (int, optional): The length of the moving indicator. Defaults to 20.
        """
        super().__init__()
        self.delay = delay
        self.length = length
        self.running = False
        self.position = self.length - 1  # Initial position
        self.direction = -1  # Movement direction

    def run(self):
        """
        Execute the moving indicator animation until the thread is stopped.
        """
        self.running = True
        while self.running:
            line = [' '] * self.length
            if 0 <= self.position < self.length:
                line[self.position] = '#'
            indicator = ''.join(line) + '##'
            sys.stdout.write(f"\r{indicator}")
            sys.stdout.flush()
            self.position += self.direction
            if self.position == 0 or self.position == self.length - 1:
                self.direction *= -1  # Reverse direction
            time.sleep(self.delay)

    def stop(self):
        """
        Terminate the moving indicator thread and clear the indicator from the terminal.
        """
        self.running = False
        self.join()
        sys.stdout.write('\r' + ' ' * (self.length + 2) + '\r')  # Clears the indicator
        sys.stdout.flush()


class WebCrawler:
    """
    A robust web crawler designed to extract textual content and downloadable files from websites.
    """

    def __init__(self, start_url, max_depth=2, use_playwright=False, excluded_paths=None,
                 download_extensions=None, language_pattern=None, base_dir=None):
        """
        Initialize the WebCrawler with the specified configuration.

        Args:
            start_url (str): The initial URL from which the crawler begins.
            max_depth (int, optional): The maximum depth to traverse from the start URL. Defaults to 2.
            use_playwright (bool, optional): Flag to determine if Playwright should be used for rendering JavaScript. Defaults to False.
            excluded_paths (list, optional): List of URL path segments to exclude from crawling. Defaults to None.
            download_extensions (dict, optional): Mapping of file types to their corresponding extensions. Defaults to None.
            language_pattern (re.Pattern, optional): Regular expression pattern to filter URLs based on language. Defaults to None.
            base_dir (str, optional): Base directory for storing crawler outputs. Defaults to a timestamped directory.
        """
        self.start_url = start_url
        self.max_depth = max_depth
        self.use_playwright = use_playwright
        self.visited_pages = set()
        self.downloaded_files = set()
        self.domain = urlparse(start_url).netloc
        self.excluded_paths = excluded_paths or ['selecteur-de-produits']
        self.download_extensions = download_extensions or {
            'PDF': ['.pdf'],
            'Image': ['.png', '.jpg', '.jpeg', '.gif', '.svg'],
            'Doc': ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
        }
        self.language_pattern = language_pattern
        self.base_dir = base_dir or f"crawler_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.create_directories()
        self.setup_logging()
        self.stats = defaultdict(int)
        self.all_downloadable_exts = set(ext for exts in self.download_extensions.values() for ext in exts)
        self.content_type_mapping = {
            'PDF': {
                'application/pdf': '.pdf'
            },
            'Image': {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/svg+xml': '.svg',
            },
            'Doc': {
                'application/msword': '.doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
                'application/vnd.ms-excel': '.xls',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
                'application/vnd.ms-powerpoint': '.ppt',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
            }
        }
        self.session = self.setup_session()
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.body_width = 0
        self.html_converter.ignore_images = True
        self.html_converter.single_line_break = False

        if self.use_playwright:
            from playwright.sync_api import sync_playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()

        self.indicator = MovingIndicator(length=20)

    def setup_session(self):
        """
        Configure and return a Requests session with retry strategy and custom headers.

        Returns:
            requests.Session: A configured session object for making HTTP requests.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.verify = False  # Disable SSL verification if necessary
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36'
        })
        return session

    def create_directories(self):
        """
        Create essential directories for storing content, downloads, and logs within the base directory.
        """
        directories = ['content', 'PDF', 'Image', 'Doc', 'logs']
        for dir_name in directories:
            path = os.path.join(self.base_dir, dir_name)
            os.makedirs(path, exist_ok=True)

    def setup_logging(self):
        """
        Set up logging configurations with both file and console handlers, utilizing colored formatting for console output.
        """
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        formatter = ColoredFormatter(log_format)

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # File handler for logging to a file without colors
        file_handler = logging.FileHandler(os.path.join(self.base_dir, 'logs', 'crawler.log'), encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

        # Console handler for logging to the terminal with colors
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Log the initiation of the crawler
        logging.info(f"Crawler initiated with language pattern: {self.language_pattern}")

    def should_exclude(self, url):
        """
        Determine whether a given URL should be excluded based on predefined path segments.

        Args:
            url (str): The URL to evaluate.

        Returns:
            bool: True if the URL contains an excluded path segment, False otherwise.
        """
        for excluded in self.excluded_paths:
            if excluded in url:
                return True
        return False

    def is_same_language(self, url):
        """
        Verify if the URL matches the specified language pattern.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if the URL matches the language pattern or if no pattern is specified, False otherwise.
        """
        if not self.language_pattern:
            return True
        return self.language_pattern.search(url) is not None

    def is_downloadable_file(self, url):
        """
        Assess whether a URL points to a downloadable file based on its file extension.

        Args:
            url (str): The URL to evaluate.

        Returns:
            bool: True if the URL has a recognized downloadable file extension, False otherwise.
        """
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        pattern = re.compile(r'\.(' + '|'.join([ext.strip('.') for exts in self.download_extensions.values() for ext in exts]) + r')(\.[a-z0-9]+)?$', re.IGNORECASE)
        return bool(pattern.search(path))

    def get_file_type_and_extension(self, url, response):
        """
        Determine the file type and appropriate extension based on the URL and HTTP response headers.

        Args:
            url (str): The URL of the file.
            response (requests.Response): The HTTP response object from a HEAD request.

        Returns:
            tuple:
                - file_type (str or None): The determined file type (e.g., 'PDF', 'Image', 'Doc'), or None if undetermined.
                - extension (str or None): The appropriate file extension, or None if undetermined.
        """
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        # Primary method: deduce file type based on URL extension
        for file_type, extensions in self.download_extensions.items():
            for ext in extensions:
                pattern = re.compile(re.escape(ext) + r'(\.[a-z0-9]+)?$', re.IGNORECASE)
                if pattern.search(path):
                    return file_type, self.content_type_mapping[file_type].get(response.headers.get('Content-Type', '').lower(), ext)

        # Secondary method: deduce file type based on Content-Type header
        content_type = response.headers.get('Content-Type', '').lower()
        for file_type, mapping in self.content_type_mapping.items():
            if content_type in mapping:
                return file_type, mapping[content_type]

        # If file type cannot be determined
        return None, None

    def sanitize_filename(self, url, file_type, extension, page_number=None):
        """
        Generate a sanitized and unique filename based on the URL and file type.

        Args:
            url (str): The source URL of the file or page.
            file_type (str): The category of the file (e.g., 'PDF', 'Image', 'Doc').
            extension (str): The file extension.
            page_number (int, optional): The page number, if applicable. Defaults to None.

        Returns:
            str: A sanitized and uniquely hashed filename.
        """
        # Generate a short hash from the URL for uniqueness
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # Extract the last segment of the URL path
        filename = url.split('/')[-1] or 'index'

        # Replace unsafe characters with underscores
        filename = re.sub(r'[^\w\-_.]', '_', filename)

        # Remove existing extensions to append the correct one
        name, _ = os.path.splitext(filename)

        # Assign default extension if none is provided
        if not extension:
            extension = '.txt'

        # Incorporate page number if provided
        if page_number is not None:
            sanitized = f"{name}_page_{page_number:03d}_{url_hash}{extension}"
        else:
            sanitized = f"{name}_{url_hash}{extension}"

        logging.debug(f"Sanitized filename generated: {sanitized}")
        return sanitized

    def download_file(self, url, file_type):
        """
        Download a file from the specified URL and save it to the designated directory.

        Args:
            url (str): The URL of the file to download.
            file_type (str): The category of the file (e.g., 'PDF', 'Image', 'Doc').

        Returns:
            bool: True if the download was successful, False otherwise.
        """
        try:
            logging.info(f"Initiating download of {file_type} from: {url}")

            # Determine the file type and extension via HEAD request
            response = self.session.head(url, allow_redirects=True, timeout=10)
            file_type_detected, extension = self.get_file_type_and_extension(url, response)
            if not file_type_detected:
                logging.warning(f"⚠ Unable to ascertain file type for URL: {url}")
                return False

            # Generate a sanitized filename
            filename = self.sanitize_filename(url, file_type_detected, extension)
            save_path = os.path.join(self.base_dir, file_type_detected, filename)

            # Skip download if file already exists
            if os.path.exists(save_path):
                logging.info(f"📂 File already exists. Skipping download: {filename}")
                return False

            # Perform the download with a progress bar
            response = self.session.get(url, stream=True, timeout=20)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024  # 1 Kibibyte
            progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True, desc=f"⏬ Downloading {filename}", leave=False)

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        progress_bar.update(len(chunk))
            progress_bar.close()

            # Verify the completeness of the download
            if total_size != 0 and progress_bar.n != total_size:
                logging.warning(f"⚠ Download incomplete for URL: {url}")
                return False

            self.stats[f'{file_type_detected}_downloaded'] += 1
            self.downloaded_files.add(url)
            logging.info(f"✅ Successfully downloaded {file_type_detected}: {filename}")
            return True

        except Exception as e:
            logging.error(f"✘ Error encountered while downloading {url}: {str(e)}")
            return False

    def convert_links_to_absolute(self, soup, base_url):
        """
        Convert all relative links within the HTML content to absolute URLs.

        Args:
            soup (BeautifulSoup): The BeautifulSoup object containing parsed HTML.
            base_url (str): The base URL to resolve relative links against.

        Returns:
            BeautifulSoup: The modified BeautifulSoup object with absolute links.
        """
        # Process tags that can contain links
        for tag in soup.find_all(['a', 'embed', 'iframe', 'object'], href=True):
            href = tag.get('href') or tag.get('src')
            if href:
                absolute_url = urljoin(base_url, href)
                if tag.name in ['embed', 'iframe', 'object']:
                    tag['src'] = absolute_url
                else:
                    tag['href'] = absolute_url
        return soup

    def clean_text(self, text):
        """
        Sanitize and normalize extracted text by removing unwanted characters and formatting.

        Args:
            text (str): The raw text to be cleaned.

        Returns:
            str: The cleaned and normalized text.
        """
        if not text:
            return ""

        # Eliminate non-printable or control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)

        # Condense multiple spaces or tabs into a single space
        text = re.sub(r'[ \t]+', ' ', text)

        # Reduce multiple newlines to a standard two newline format
        text = re.sub(r'\n\s*\n', '\n\n', text)

        return text.strip()

    def fetch_page_content(self, url):
        """
        Retrieve the HTML content of a webpage using either Requests or Playwright.

        Args:
            url (str): The URL of the webpage to fetch.

        Returns:
            str or None: The HTML content of the page if successful, otherwise None.
        """
        if self.use_playwright:
            try:
                logging.info(f"🔍 Fetching content using Playwright: {url}")
                self.page.goto(url, timeout=20000)
                time.sleep(2)  # Allow time for dynamic content to load
                content = self.page.content()
                return content
            except Exception as e:
                logging.error(f"✘ Playwright failed to retrieve {url}: {str(e)}")
                return None
        else:
            try:
                response = self.session.get(url, timeout=20)
                if response.status_code == 200:
                    logging.info(f"✅ Successfully fetched content from: {url}")
                    return response.text
                else:
                    logging.warning(f"⚠ Failed to fetch {url} with status code: {response.status_code}")
                    return None
            except Exception as e:
                logging.error(f"✘ Requests encountered an error while fetching {url}: {str(e)}")
                return None

    def extract_content(self, url):
        """
        Extract and save the main textual content from a specified URL and download associated files.

        Args:
            url (str): The URL from which to extract content.
        """
        logging.info(f"📄 Initiating content extraction from: {url}")

        try:
            if self.is_downloadable_file(url):
                logging.info(f"🔗 URL identified as a downloadable file. Skipping content extraction: {url}")
                return

            page_content = self.fetch_page_content(url)
            if page_content is None:
                logging.warning(f"⚠ Unable to retrieve content for URL: {url}")
                return

            soup = BeautifulSoup(page_content, 'html.parser')

            # Remove non-essential HTML elements
            for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'aside', 'iframe']):
                element.decompose()

            # Identify the primary content section
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_='content') or
                soup.find('div', id='content')
            )

            if main_content:
                # Convert all links within the main content to absolute URLs
                main_content = self.convert_links_to_absolute(main_content, url)

                # Transform HTML content to Markdown format
                markdown_content = self.html_converter.handle(str(main_content))

                # Assemble the complete content with title and source URL
                content_parts = []

                # Append the title if present
                title = soup.find('h1')
                if title:
                    content_parts.append(f"# {title.get_text().strip()}")

                # Append the source URL
                content_parts.append(f"**Source:** {url}")

                # Append the main Markdown content
                content_parts.append(markdown_content)

                # Clean the aggregated content
                content = self.clean_text('\n\n'.join(content_parts))

                if content:
                    # Generate a sanitized filename for the content
                    filename = self.sanitize_filename(url, 'Doc', '.txt')  # Using 'Doc' category with '.txt' extension
                    save_path = os.path.join(self.base_dir, 'content', filename)
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                    self.stats['pages_processed'] += 1
                    logging.info(f"✅ Content successfully saved as: {filename}")
                else:
                    logging.warning(f"⚠ No substantial content found for URL: {url}")

                # Identify and process downloadable files within the main content
                downloadable_tags = main_content.find_all(['a', 'embed', 'iframe', 'object'], href=True)

                if downloadable_tags:
                    logging.info(f"🔄 Detected {len(downloadable_tags)} downloadable files on the page.")

                for tag in downloadable_tags:
                    href = tag.get('href') or tag.get('src')
                    if href:
                        file_url = urljoin(url, href)
                        if self.is_downloadable_file(file_url) and file_url not in self.downloaded_files:
                            # Attempt to determine file type via HEAD request
                            try:
                                response_head = self.session.head(file_url, allow_redirects=True, timeout=10)
                                file_type_detected, _ = self.get_file_type_and_extension(file_url, response_head)
                            except:
                                # Fallback to GET request if HEAD fails
                                response_head = self.session.get(file_url, allow_redirects=True, timeout=10)
                                file_type_detected, _ = self.get_file_type_and_extension(file_url, response_head)

                            if file_type_detected:
                                # Generate a sanitized filename
                                filename = self.sanitize_filename(
                                    file_url,
                                    file_type_detected,
                                    self.content_type_mapping[file_type_detected].get(
                                        response_head.headers.get('Content-Type', '').lower(), ''
                                    )
                                )
                                save_path = os.path.join(self.base_dir, file_type_detected, filename)

                                if os.path.exists(save_path):
                                    logging.info(f"📂 File already exists. Skipping download: {filename}")
                                    continue

                                self.download_file(file_url, file_type_detected)
            else:
                logging.warning(f"⚠ Unable to locate main content section for URL: {url}")

        except Exception as e:
            logging.error(f"✘ An error occurred while processing URL {url}: {str(e)}")

    def extract_urls(self, start_url):
        """
        Traverse and collect all relevant URLs starting from the initial URL up to the defined maximum depth.

        Args:
            start_url (str): The starting URL for the crawling process.
        """
        queue = deque()
        queue.append((start_url, 0))
        self.visited_pages.add(start_url)

        pbar = tqdm(total=1, desc="🔍 Extracting URLs", unit="page", ncols=100)

        while queue:
            current_url, depth = queue.popleft()

            if depth > self.max_depth:
                pbar.update(1)
                continue

            if self.should_exclude(current_url):
                logging.info(f"🚫 Excluding URL based on excluded paths: {current_url}")
                pbar.update(1)
                continue

            logging.info(f"🔎 Extracting URLs from: {current_url} (Depth: {depth})")

            try:
                if self.is_downloadable_file(current_url):
                    # Attempt to determine file type via HEAD request
                    try:
                        response_head = self.session.head(current_url, allow_redirects=True, timeout=10)
                        file_type_detected, _ = self.get_file_type_and_extension(current_url, response_head)
                    except:
                        # Fallback to GET request if HEAD fails
                        response_head = self.session.get(current_url, allow_redirects=True, timeout=10)
                        file_type_detected, _ = self.get_file_type_and_extension(current_url, response_head)

                    if file_type_detected:
                        # Generate a sanitized filename
                        filename = self.sanitize_filename(
                            current_url,
                            file_type_detected,
                            self.content_type_mapping[file_type_detected].get(
                                response_head.headers.get('Content-Type', '').lower(), ''
                            )
                        )
                        save_path = os.path.join(self.base_dir, file_type_detected, filename)

                        if os.path.exists(save_path):
                            logging.info(f"📂 File already exists. Skipping download: {filename}")
                            pbar.update(1)
                            continue

                        self.download_file(current_url, file_type_detected)
                        self.downloaded_files.add(current_url)
                    pbar.update(1)
                    continue

                # Fetch page content using the appropriate method
                page_content = self.fetch_page_content(current_url)
                if page_content is None:
                    logging.warning(f"⚠ Unable to retrieve content for URL: {current_url}")
                    pbar.update(1)
                    continue

                soup = BeautifulSoup(page_content, 'html.parser')

                # Identify all relevant link-containing tags
                for tag in soup.find_all(['a', 'link', 'embed', 'iframe', 'object'], href=True):
                    href = tag.get('href') or tag.get('src')
                    if href:
                        absolute_url = urljoin(current_url, href)
                        parsed_url = urlparse(absolute_url)

                        if self.is_downloadable_file(absolute_url):
                            # Determine file type via HEAD request
                            try:
                                response_head = self.session.head(absolute_url, allow_redirects=True, timeout=10)
                                file_type_detected, _ = self.get_file_type_and_extension(absolute_url, response_head)
                            except:
                                # Fallback to GET request if HEAD fails
                                response_head = self.session.get(absolute_url, allow_redirects=True, timeout=10)
                                file_type_detected, _ = self.get_file_type_and_extension(absolute_url, response_head)

                            if file_type_detected:
                                # Generate a sanitized filename
                                filename = self.sanitize_filename(
                                    absolute_url,
                                    file_type_detected,
                                    self.content_type_mapping[file_type_detected].get(
                                        response_head.headers.get('Content-Type', '').lower(), ''
                                    )
                                )
                                save_path = os.path.join(self.base_dir, file_type_detected, filename)

                                if os.path.exists(save_path):
                                    logging.info(f"📂 File already exists. Skipping download: {filename}")
                                    continue

                                self.download_file(absolute_url, file_type_detected)
                                self.downloaded_files.add(absolute_url)
                            continue

                        # Assess if the link is internal and eligible for crawling
                        if (self.domain in parsed_url.netloc and
                            self.is_same_language(absolute_url) and
                            absolute_url not in self.visited_pages and
                            not absolute_url.endswith(('#', 'javascript:void(0)', 'javascript:;')) and
                            not self.should_exclude(absolute_url)):

                            # Enqueue the URL for further crawling
                            queue.append((absolute_url, depth + 1))
                            self.visited_pages.add(absolute_url)
                            pbar.total += 1
                            pbar.refresh()

            except Exception as e:
                logging.error(f"✘ An error occurred while crawling URL {current_url}: {str(e)}")

            pbar.update(1)

        pbar.close()
        logging.info("🔍 Completed URL extraction phase.")

    def crawl(self):
        """
        Execute the complete crawling process, encompassing URL extraction, content scraping, and report generation.
        """
        start_time = time.time()
        logging.info(f"🚀 Initiating crawl of: {self.start_url}")
        logging.info(f"🌐 Language Pattern: {self.language_pattern}")
        logging.info(f"📏 Maximum Crawling Depth: {self.max_depth}")

        # Load previously downloaded files to avoid redundant downloads
        self.load_downloaded_files()

        # Start the moving indicator to signify active crawling
        self.indicator.start()

        try:
            # Phase 1: Extract URLs up to the specified depth
            logging.info("🔍 Phase 1: URL Extraction")
            self.extract_urls(self.start_url)

            # Phase 2: Extract content from the collected URLs
            logging.info("📄 Phase 2: Content Extraction")
            non_file_urls = [url for url in self.visited_pages if not self.is_downloadable_file(url)]

            pbar_content = tqdm(total=len(non_file_urls), desc="📄 Extracting Content", unit="page", ncols=100)
            for i, url in enumerate(non_file_urls, 1):
                logging.info(f"📝 Processing ({i}/{len(non_file_urls)}): {url}")
                self.extract_content(url)
                pbar_content.update(1)
            pbar_content.close()
            logging.info("📄 Completed content extraction phase.")

            # Generate a comprehensive report summarizing the crawl
            end_time = time.time()
            self.generate_report(end_time - start_time)

        except Exception as e:
            logging.error(f"⚠ A critical error occurred during crawling: {str(e)}")
            self.generate_report(time.time() - start_time, error=str(e))

        finally:
            # Terminate the moving indicator
            self.indicator.stop()

            # Persist the list of downloaded files
            self.save_downloaded_files()

            # Clean up Playwright resources if utilized
            if self.use_playwright:
                self.page.close()
                self.browser.close()
                self.playwright.stop()

    def load_downloaded_files(self):
        """
        Load the list of previously downloaded files from the tracking file to prevent duplicate downloads.
        """
        downloaded_files_path = os.path.join(self.base_dir, 'logs', 'downloaded_files.txt')
        if os.path.exists(downloaded_files_path):
            with open(downloaded_files_path, 'r', encoding='utf-8') as f:
                for line in f:
                    self.downloaded_files.add(line.strip())
            logging.info(f"📥 Loaded {len(self.downloaded_files)} previously downloaded files from tracking.")
        else:
            logging.info("🆕 No existing download tracking file found. Starting fresh.")

    def save_downloaded_files(self):
        """
        Save the current list of downloaded files to the tracking file for future reference.
        """
        downloaded_files_path = os.path.join(self.base_dir, 'logs', 'downloaded_files.txt')
        try:
            with open(downloaded_files_path, 'w', encoding='utf-8') as f:
                for url in sorted(self.downloaded_files):
                    f.write(url + '\n')
            logging.info(f"💾 Saved {len(self.downloaded_files)} downloaded files to the tracking file.")
        except Exception as e:
            logging.error(f"✘ Failed to save downloaded files tracking: {str(e)}")

    def generate_report(self, duration, error=None):
        """
        Compile and save a detailed report of the crawling session, including statistics and any encountered errors.

        Args:
            duration (float): Total time taken for the crawling process in seconds.
            error (str, optional): Error message if a critical failure occurred during crawling. Defaults to None.
        """
        report_sections = []

        # Header Section
        report_sections.append(f"""
Crawler Report
==============
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Configuration
-------------
Start URL: {self.start_url}
Language Pattern: {self.language_pattern}
Max Depth: {self.max_depth}
Duration: {duration:.2f} seconds

Statistics
----------
Total URLs Found: {len(self.visited_pages)}
Pages Processed: {self.stats['pages_processed']}
Files Downloaded:
- PDFs: {self.stats['PDF_downloaded']}
- Images: {self.stats['Image_downloaded']}
- Documents: {self.stats['Doc_downloaded']}
""")

        # Error Section (if applicable)
        if error:
            report_sections.append(f"""

Errors
------
Critical Error: {error}

""")

        # Processed URLs Section
        report_sections.append("""
Processed URLs
--------------
""")
        for url in sorted(self.visited_pages):
            report_sections.append(url)

        # Generated Files Section
        report_sections.append("""
Generated Files
---------------
""")
        for directory in ['content', 'PDF', 'Image', 'Doc']:
            dir_path = os.path.join(self.base_dir, directory)
            if os.path.exists(dir_path):
                files = os.listdir(dir_path)
                report_sections.append(f"\n{directory} Files ({len(files)}):")
                for file in sorted(files):
                    report_sections.append(f"- {file}")

        # Consolidate and save the report
        report_content = '\n'.join(report_sections)
        report_path = os.path.join(self.base_dir, 'crawler_report.txt')

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            logging.info(f"📄 Successfully generated report: {report_path}")
        except Exception as e:
            logging.error(f"✘ Failed to generate report: {str(e)}")

        # Summary Section
        summary = f"""
Crawling Summary
----------------
Start URL: {self.start_url}
Total URLs: {len(self.visited_pages)}
Pages Processed: {self.stats['pages_processed']}
Total Files Downloaded: {sum(self.stats[k] for k in ['PDF_downloaded', 'Image_downloaded', 'Doc_downloaded'])}
Duration: {duration:.2f} seconds
Status: {'⚠ Completed with errors' if error else '✅ Completed successfully'}
"""
        try:
            with open(os.path.join(self.base_dir, 'summary.txt'), 'w', encoding='utf-8') as f:
                f.write(summary)
            logging.info(f"📄 Successfully generated summary: {os.path.join(self.base_dir, 'summary.txt')}")
        except Exception as e:
            logging.error(f"✘ Failed to generate summary: {str(e)}")
