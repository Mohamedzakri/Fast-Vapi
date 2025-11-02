import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
import os  # os is still useful for environment variables if needed

# Configure logging
logger = logging.getLogger(__name__)


class ScraperService:
    """Service for web scraping operations with support for dynamic content"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.timeout = 30  # seconds
        self.use_selenium = True  # Set to True to use Selenium by default for dynamic content

    def _get_chrome_driver(self):
        """
        Initialize Chrome WebDriver using Selenium Manager.
        Selenium Manager will automatically find the installed Chrome,
        download the correct ChromeDriver version and architecture, and cache it.
        """
        try:
            chrome_options = Options()

            # Headless mode (no browser window)
            chrome_options.add_argument('--headless=new')

            # Performance optimizations
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')

            # Set user agent
            chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')

            # Set window size
            chrome_options.add_argument('--window-size=1920,1080')

            # Suppress logging
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

            logger.info(" Initializing Chrome WebDriver using Selenium Manager...")

            # Initialize the Service object. Selenium Manager will take over.
            # No executable_path or os_type is needed.
            service = Service()

            # Initialize the driver
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(self.timeout)

            logger.info(" Chrome WebDriver initialized successfully")
            return driver

        except Exception as e:
            logger.error(f" Failed to initialize Chrome WebDriver: {e}")

            # Add helpful hints for common Selenium Manager issues
            msg = str(e).lower()
            if "cannot find chrome binary" in msg:
                logger.error(
                    " Hint: Selenium couldn't find Google Chrome. Please ensure Google Chrome is installed.")
            elif "session not created" in msg and "this version of chromedriver only supports" in msg:
                logger.error(
                    " Hint: Potential mismatch. Try clearing the Selenium cache (e.g., ~/.cache/selenium) and retrying.")

            raise Exception(f"WebDriver initialization failed: {str(e)}")

    async def scrape_url(self, url: str, use_selenium: Optional[bool] = None) -> Dict[str, Any]:
        """
        Scrape HTML content from the given URL

        Args:
            url: The URL to scrape
            use_selenium: Override to force Selenium usage (None = use default)

        Returns:
            Dictionary containing scraped data

        Raises:
            Exception: If scraping fails
        """
        # Determine which method to use
        should_use_selenium = use_selenium if use_selenium is not None else self.use_selenium

        if should_use_selenium:
            return await self._scrape_with_selenium(url)
        else:
            return await self._scrape_with_requests(url)

    async def _scrape_with_selenium(self, url: str) -> Dict[str, Any]:
        """
        Scrape URL using Selenium for JavaScript-rendered content
        """
        driver = None
        try:
            logger.info(f" Starting Selenium scrape for URL: {url}")

            # Initialize WebDriver
            driver = self._get_chrome_driver()

            # Navigate to URL
            driver.get(url)

            # Wait for page to load - adjust selector based on your needs
            # Wait for body to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Additional wait for dynamic content to load
            # You can adjust this or use specific element waits
            time.sleep(2)  # Give JavaScript time to render

            # Get page source after JavaScript execution
            html_content = driver.page_source

            # Get page title
            title = driver.title

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'lxml')

            # Extract metadata
            meta_description = self._extract_meta_description(soup)

            # Prepare scraped data
            scraped_data = {
                'url': url,
                'html_content': html_content,
                'title': title,
                'status_code': 200,  # Selenium doesn't provide HTTP status
                'scraped_at': datetime.utcnow(),
                'content_length': len(html_content),
                'headers': {'scraping_method': 'selenium'},
                'meta_description': meta_description,
                'success': True,
                'error_message': None
            }

            logger.info(f" Successfully scraped with Selenium: {url}")
            logger.info(f" Content length: {scraped_data['content_length']} characters")
            logger.info(f" Page title: {title}")

            return scraped_data

        except Exception as e:
            error_msg = f"Selenium scraping failed: {str(e)}"
            logger.error(f" {error_msg}")
            raise Exception(error_msg)

        finally:
            # Always close the browser
            if driver:
                try:
                    driver.quit()
                    logger.info(" Chrome WebDriver closed")
                except Exception as e:
                    logger.warning(f"️ Error closing WebDriver: {e}")

    async def _scrape_with_requests(self, url: str) -> Dict[str, Any]:
        """
        Scrape URL using requests library for static content
        """
        try:
            logger.info(f" Starting requests scrape for URL: {url}")

            # Make HTTP request
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )

            # Check if request was successful
            response.raise_for_status()

            # Parse HTML content
            soup = BeautifulSoup(response.content, 'lxml')

            # Extract metadata
            title = self._extract_title(soup)
            meta_description = self._extract_meta_description(soup)

            # Prepare scraped data
            scraped_data = {
                'url': url,
                'html_content': response.text,
                'title': title,
                'status_code': response.status_code,
                'scraped_at': datetime.utcnow(),
                'content_length': len(response.text),
                'headers': dict(response.headers),
                'meta_description': meta_description,
                'success': True,
                'error_message': None
            }

            logger.info(f" Successfully scraped with requests: {url}")
            logger.info(f" Content length: {scraped_data['content_length']} characters")
            logger.info(f" Page title: {title}")

            return scraped_data

        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {self.timeout} seconds"
            logger.error(f"  {error_msg} for URL: {url}")
            raise Exception(error_msg)

        except requests.exceptions.ConnectionError:
            error_msg = "Failed to connect to the URL"
            logger.error(f" {error_msg}: {url}")
            raise Exception(error_msg)

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error occurred: {e.response.status_code}"
            logger.error(f" {error_msg} for URL: {url}")
            raise Exception(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(f" {error_msg}")
            raise Exception(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error during scraping: {str(e)}"
            logger.error(f" {error_msg}")
            raise Exception(error_msg)

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title from HTML"""
        try:
            if soup.title and soup.title.string:
                return soup.title.string.strip()
            return None
        except Exception as e:
            logger.warning(f"  Could not extract title: {e}")
            return None

    def _extract_meta_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract meta description from HTML"""
        try:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                return meta_desc.get('content').strip()
            return None
        except Exception as e:
            logger.warning(f"  Could not extract meta description: {e}")
            return None


# Singleton instance
scraper_service = ScraperService()
