"""
ScrapeExecutor: Uses LimitedScrapeWebsiteTool to fetch and extract website content for downstream use, such as data analysis, NLP, or further processing.
This executor is designed to extract the main text and metadata from a given URL, making it suitable for analytics, machine learning, or information retrieval tasks.
"""

from typing import Dict, Any, Optional
from apflow.core.base import BaseTask
from apflow.core.extensions.decorators import executor_register
from apflow.core.execution.errors import ValidationError
from apflow.extensions.tools.limited_scrape_tools import LimitedScrapeWebsiteTool
from apflow.logger import get_logger

logger = get_logger(__name__)


@executor_register()
class ScrapeExecutor(BaseTask):
    """
    Executor for scraping website content using LimitedScrapeWebsiteTool.
    Accepts a URL and optional parameters, returns extracted content and metadata.
    This is useful for downstream tasks such as data analysis, NLP, or machine learning workflows.
    """

    id = "scrape_executor"
    name = "Website Scraper Executor"
    description = (
        "Scrape website content and metadata from a given URL, returning the main text and metadata for downstream use such as data analysis, NLP, or further processing. "
        "Supports configurable character limits and metadata extraction."
    )
    tags = ["scrape", "website", "content", "metadata"]
    examples = [
        "Scrape a blog post",
        "Extract main text and metadata from a news article",
        "Fetch content from a documentation page",
    ]
    cancelable: bool = False

    def __init__(self, headers=None, **kwargs):
        super().__init__(**kwargs)
        self.headers = headers or {}

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape website content using LimitedScrapeWebsiteTool.

        Args:
            inputs: Dictionary with keys:
                - url (str, required): Target website URL
                - max_chars (int, optional): Maximum characters to extract (default: 5000)
                - extract_metadata (bool, optional): Whether to extract metadata (default: True)

        Returns:
            Dictionary with scraped content.
        """
        url = inputs.get("url")
        if not url:
            raise ValidationError("'url' is required for scraping.")

        max_chars = inputs.get("max_chars", 5000)
        extract_metadata = inputs.get("extract_metadata", True)

        logger.info(
            f"Scraping website: {url} (max_chars={max_chars}, extract_metadata={extract_metadata})"
        )

        # Use the LimitedScrapeWebsiteTool to perform the actual scraping
        tool = LimitedScrapeWebsiteTool()
        try:
            # The tool expects named arguments
            content = tool._run(
                website_url=url,
                max_chars=max_chars,
                extract_metadata=extract_metadata,
                headers=self.headers,
            )
            if content.startswith("Error:"):
                raise ValidationError(content)
            return {"result": content}
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {str(e)}")
            raise ValidationError(f"Failed to scrape {url}: {str(e)}")

    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Provide a demo scrape result for documentation or dry-run purposes.
        """
        return {
            "result": "Title: Example Demo\nDescription: Example description.\nURL: https://example.com/demo\n\n---\n\nMain Text:\nThis is a demo of the website scraping executor.",
        }

    def get_input_schema(self) -> Dict[str, Any]:
        """
        Return the input parameter schema for this executor.
        """
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target website URL to scrape"},
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of characters to extract (default: 5000)",
                },
                "extract_metadata": {
                    "type": "boolean",
                    "description": "Whether to extract metadata like title and description (default: True)",
                },
            },
            "required": ["url"],
        }

    def get_output_schema(self) -> Dict[str, Any]:
        """
        Return the output result schema for this executor.
        """
        return {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "Scraped website content as string"},
            },
            "required": ["result"],
        }
