"""
This script crawls a website and collects links, similar to the linkinator tool.
It performs recursive crawling and saves the collected links to a CSV file.
Usage: python script.py [--recurse] [--format CSV]
"""

import asyncio
import csv
import os
import argparse
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from datetime import datetime

async def get_links(page, url):
    """
    Asynchronously scrapes links from the specified URL using Playwright.
    Returns a set of unique links found on the page.
    """
    links = set()
    try:
        # Navigate to the URL and wait for the network to be idle
        await page.goto(url, wait_until='networkidle')
        # Find all <a> elements on the page
        elements = await page.query_selector_all('a')
        for element in elements:
            # Get the 'href' attribute of each <a> element
            href = await element.get_attribute('href')
            # Filter out links that start with 'mailto:', '#', 'javascript:', or 'tel:'
            if href and not href.startswith(('mailto:', '#', 'javascript:', 'tel:')):
                # Convert the relative URL to an absolute URL
                absolute_url = urljoin(url, href)
                # Skip URLs that contain "ld.php?content_id="
                if "ld.php?content_id=" not in absolute_url:
                    links.add(absolute_url)
    except Exception as e:
        print(f"Error getting links from {url}: {str(e)}")
    return links

async def crawl_site(base_url, recurse=False, max_links=10000, max_depth=5):
    """
    Crawls the site starting from the base_url.
    If recurse is True, it will follow links within the same domain.
    Limits the number of links to prevent memory issues.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        visited = set()
        to_visit = [(base_url, 0)]  # (url, depth)
        all_links = []
        base_domain = urlparse(base_url).netloc

        while to_visit and len(all_links) < max_links:
            url, depth = to_visit.pop(0)
            
            # Skip URLs that have already been visited, contain "ld.php?content_id=", or exceed the maximum depth
            if url in visited or "ld.php?content_id=" in url or depth >= max_depth:
                continue
            
            visited.add(url)
            links = await get_links(page, url)
            
            for link in links:
                all_links.append((link, url))
                # If recursing, add new links to the to_visit list if they are within the same domain and haven't been visited
                if recurse and urlparse(link).netloc == base_domain and link not in visited:
                    to_visit.append((link, depth + 1))
            
            # Write links to file in batches to save memory
            if len(all_links) >= 1000:
                yield all_links
                all_links = []

        # Yield any remaining links
        if all_links:
            yield all_links

        await browser.close()

async def main():
    parser = argparse.ArgumentParser(description="Crawl a website and collect links.")
    parser.add_argument("--recurse", action="store_true", help="Recursively crawl the site")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum depth for recursive crawling")
    parser.add_argument("--format", choices=["CSV"], default="CSV", help="Output format")
    args = parser.parse_args()

    # Get the base URL from the environment variable, or use a default value
    base_url = os.environ.get('BASE_URL') or "https://library.soton.ac.uk"

    print(f"Starting link collection for {base_url}")

    # Create the 'reports' directory if it doesn't exist
    os.makedirs('reports', exist_ok=True)
    # Generate the filename for the CSV file based on the current date
    date = datetime.now().strftime('%Y-%m-%d')
    links_file = f"reports/get-links-{date}.csv"


    if args.format == "CSV":
        with open(links_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["URL", "Parent URL"])
            
            # Crawl the site and write the collected links to the CSV file in batches
            async for links_batch in crawl_site(base_url, args.recurse, max_depth=args.max_depth):
                writer.writerows(links_batch)
    
    # Set the LINKS_FILE environment variable for GitHub Actions
    print(f"LINKS_FILE={links_file}")
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"LINKS_FILE={links_file}\n")
        
        print(f"Links saved to get-links-{date}.csv")

if __name__ == "__main__":
    asyncio.run(main())
