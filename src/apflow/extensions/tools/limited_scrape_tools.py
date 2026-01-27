"""
Limited Website Scraping Tool
"""

from typing import Dict, Type, Optional
from apflow.core.tools import BaseTool, tool_register
from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

from apflow.logger import get_logger

logger = get_logger(__name__)


class LimitedScrapeWebsiteInputSchema(BaseModel):
    website_url: str = Field(..., description="The URL of the website to scrape")
    max_chars: int = Field(
        default=5000, description="Maximum characters to extract from the website"
    )
    extract_metadata: bool = Field(
        default=True, description="Whether to extract metadata like title, description, etc."
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Headers to use for the request"
    )


@tool_register()
class LimitedScrapeWebsiteTool(BaseTool):
    """Tool for scraping website content with character limits to prevent token overflow"""

    name: str = "Limited Website Scraper"
    description: str = (
        "Scrape website content with configurable character limits to prevent token overflow"
    )
    args_schema: Type[BaseModel] = LimitedScrapeWebsiteInputSchema

    def _run(
        self,
        website_url: str,
        max_chars: int = 5000,
        extract_metadata: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Scrape website content with character limits

        Args:
            website_url: URL to scrape
            max_chars: Maximum characters to extract
            extract_metadata: Whether to extract metadata

        Returns:
            Limited website content as string
        """

        try:
            # Set headers to mimic a real browser
            default_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            if headers:
                default_headers.update(headers)

            # Make request
            response = requests.get(website_url, headers=default_headers, timeout=10)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract metadata if requested
            metadata = ""
            if extract_metadata:
                title = soup.find("title")
                if title:
                    metadata += f"Title: {title.get_text().strip()}\n"

                description = soup.find("meta", attrs={"name": "description"})
                if description and hasattr(description, "get"):
                    content = description.get("content", "")  # type: ignore
                    if content and hasattr(content, "strip"):
                        metadata += f"Description: {content.strip()}\n"  # type: ignore

                metadata += f"URL: {website_url}\n"

            social_links = self._extract_social_media_links(soup, website_url)

            content = self.extract_content(response=response)

            # Combine metadata and content
            full_content = metadata + "\n"
            if social_links:
                full_content += "Social Media Links:\n"
                for platform, link in social_links.items():
                    full_content += f"- {platform}: {link}\n"
                full_content += "\n"

            if content:
                full_content += "\n---\n\nMain Text:\n" + content

            # Limit content length
            if len(full_content) > max_chars:
                full_content = full_content[:max_chars]
                # Try to end at a complete sentence
                last_period = full_content.rfind(".")
                if last_period > max_chars * 0.8:  # If we can find a period in the last 20%
                    full_content = full_content[: last_period + 1]
                else:
                    full_content += "..."

            logger.info(f"Scraped {len(full_content)} characters from {website_url}")
            return full_content

        except requests.RequestException as e:
            logger.error(f"Request error scraping {website_url}: {str(e)}")
            return f"Error: Could not access {website_url} - {str(e)}"
        except Exception as e:
            logger.error(f"Error scraping {website_url}: {str(e)}")
            return f"Error: Failed to scrape {website_url} - {str(e)}"

    def _extract_social_media_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
        """Extract social media links from the website"""
        social_media = {}

        # Common social media patterns
        social_patterns = {
            "facebook": [r"facebook\.com/[^/\s]+", r"fb\.com/[^/\s]+"],
            "twitter": [r"twitter\.com/[^/\s]+", r"x\.com/[^/\s]+"],
            "instagram": [r"instagram\.com/[^/\s]+"],
            "linkedin": [r"linkedin\.com/(?:in|company)/[^/\s]+"],
            "youtube": [r"youtube\.com/(?:channel|c|user)/[^/\s]+", r"youtu\.be/[^/\s]+"],
            "github": [r"github\.com/[^/\s]+"],
            "telegram": [r"t\.me/[^/\s]+", r"telegram\.me/[^/\s]+"],
            "discord": [r"discord\.gg/[^/\s]+", r"discord\.com/invite/[^/\s]+"],
            "tiktok": [r"tiktok\.com/@[^/\s]+"],
            "wechat": [r"weixin\.qq\.com/[^/\s]+"],
            "weibo": [r"weibo\.com/[^/\s]+"],
            "zhihu": [r"zhihu\.com/people/[^/\s]+"],
            "bilibili": [r"bilibili\.com/[^/\s]+"],
            "wikipedia": [r"en\.wikipedia\.org/wiki/[^/\s]+"],
        }

        # Find all links
        links = soup.find_all("a", href=True)

        for link in links:
            try:
                href = link.get("href")  # type: ignore
                if isinstance(href, str):
                    # Convert relative URLs to absolute
                    full_url = urljoin(base_url, href)

                    # Check against social media patterns
                    for platform, patterns in social_patterns.items():
                        for pattern in patterns:
                            if re.search(pattern, full_url, re.IGNORECASE):
                                if platform not in social_media:
                                    social_media[platform] = full_url
                                break
            except (AttributeError, TypeError):
                pass

        return social_media

    def extract_content(self, response: requests.Response) -> str:
        """Helper method to get content with default parameters"""
        try:
            import trafilatura

            main_text = trafilatura.extract(response.text)
            if main_text:
                return main_text.strip()
            else:
                return self.extract_content_by_soup(response)
        except Exception as e:
            logger.warning(f"Trafilatura extraction failed for {response.url}: {str(e)}")
            return ""

    def extract_content_by_soup(self, response: requests.Response) -> str:
        # Extract main content
        content = ""
        soup = BeautifulSoup(response.content, "html.parser")
        # Try to find main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|main|body", re.I))
        )

        if main_content:
            content = main_content.get_text(separator=" ", strip=True)
        else:
            # Fallback to body content
            body = soup.find("body")
            if body:
                content = body.get_text(separator=" ", strip=True)
            else:
                content = soup.get_text(separator=" ", strip=True)

        # Clean up content
        content = re.sub(r"\s+", " ", content)  # Replace multiple whitespace with single space
        content = content.strip()
        return content
