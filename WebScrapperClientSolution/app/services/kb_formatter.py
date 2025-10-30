# app/services/kb_formatter.py

import html2text
from bs4 import BeautifulSoup
import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class HtmlKnowledgeBaseFormatter:
    """
    Service to clean and format raw HTML into clean, dense,
    AI-readable plain text using a 'SECTION:' prefix.
    """

    def __init__(self):
        self.text_maker = html2text.HTML2Text()

        # Configure html2text to output simpler Markdown
        self.text_maker.body_width = 0  # No line wrapping
        self.text_maker.ignore_links = False  # We will strip links manually
        self.text_maker.ignore_images = True
        self.text_maker.ignore_tables = False
        self.text_maker.ignore_emphasis = True  # Removes **bold** and *italic*

        # Tags to completely remove with all their content
        self.junk_tags = [
            'script', 'style', 'nav', 'footer', 'header',
            'aside', 'form', 'button', 'noscript', 'svg'
        ]

        logger.info("✅ HtmlKnowledgeBaseFormatter initialized (Dense AI-Structure)")

    def _clean_html(self, html_content: str) -> str:
        """
        Removes "junk" tags (like nav, footer, scripts) from the HTML
        before converting to Markdown, focusing on main content.
        """
        try:
            # Use 'html.parser' as a robust fallback if 'lxml' is not available
            soup = BeautifulSoup(html_content, 'html.parser')

            for tag_name in self.junk_tags:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Prioritize semantic main content
            main_content = soup.find('main')
            if not main_content:
                # Fallback for the Codroipo example's div ID
                main_content = soup.find(id='main')

            # If main content is found, use it; otherwise, use the body content
            target_element = main_content if main_content else soup.find('body')

            if target_element:
                logger.debug(f"Extracting content from: {target_element.name or 'document root'}")
                return str(target_element)
            else:
                logger.debug("No target content found, using full soup.")
                return str(soup)

        except Exception as e:
            logger.error(f"❌ Error during HTML cleaning: {e}")
            return html_content  # Fallback to original content

    def format(self, html_content: str) -> str:
        """
        Converts raw HTML content into a dense, structured, AI-optimized plain text.

        Args:
            html_content: The raw HTML from the scrape.

        Returns:
            A dense, structured plain-text string.
        """
        try:
            # 1. Clean the HTML
            cleaned_html = self._clean_html(html_content)

            # 2. Convert the cleaned HTML to simple Markdown
            markdown_content = self.text_maker.handle(cleaned_html)

            # 3. Post-process: Convert simple Markdown to Dense AI-style plain text

            # --- A. Cleanup Markdown Artifacts ---
            # Strip Markdown links: [text](url) -> text
            processed_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', markdown_content)

            # Remove redundant text from the Codroipo example's Terms and Conditions link
            processed_text = re.sub(r'\(javascript:void\(\)\)', '', processed_text)

            # Remove emphasis/bold markers (already mostly handled by ignore_emphasis=True, but clean up just in case)
            processed_text = processed_text.replace('**', '').replace('*', '')

            # --- B. Heading Transformation (Key step) ---
            # Convert headings: '## Heading' -> 'SECTION: HEADING'
            # This regex finds lines starting with 1-4 hashes and captures the text.
            processed_text = re.sub(
                r'^[#]{1,4}\s*(.*)',  # Matches '## Heading' or '# Heading' at start of a line
                lambda m: f"\n\nSECTION: {m.group(1).strip().upper()}",  # Prefix with SECTION: and uppercase
                processed_text,
                flags=re.MULTILINE
            )

            # --- C. List and Whitespace Consolidation ---
            # Remove list item markers (*, -) and numbered list markers (1., 2.)
            processed_text = re.sub(r'^\s*[\-\*]\s*|^\s*\d+\.\s*', '', processed_text, flags=re.MULTILINE)

            # Consolidate excessive newlines (3+ newlines to 2, ensuring sections are separated)
            processed_text = re.sub(r'\n{3,}', '\n\n', processed_text)

            # Consolidate spaces
            processed_text = re.sub(r'\s{2,}', ' ', processed_text)

            # --- D. Final Cleanup ---
            clean_text = processed_text.strip()

            logger.info(f"✅ Successfully formatted HTML to Dense AI-style text. Length: {len(clean_text)}")
            return clean_text

        except Exception as e:
            logger.error(f"❌ Failed to format HTML to Dense AI style: {e}")
            # Fallback to empty string or clean Markdown on failure
            return markdown_content.strip() if 'markdown_content' in locals() else ""

        # Singleton instance


kb_formatter_service = HtmlKnowledgeBaseFormatter()
