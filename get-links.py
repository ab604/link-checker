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
        await page.goto(url, wait_until='networkidle')
        elements = await page.query_selector_all('a')
        for element in elements:
            href = await element.get_attribute('href')
            if href and not href.startswith(('mailto:', '#', 'javascript:', 'tel:')):
                absolute_url = urljoin(url, href)
                links.add(absolute_url)
    except Exception as e:
        print(f"Error getting links from {url}: {str(e)}")
    return links

async def crawl_site(base_url, recurse=False, max_links=10000):
    """
    Crawls the site starting from the base_url.
    If recurse is True, it will follow links within the same domain.
    Limits the number of links to prevent memory issues.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        visited = set()
        to_visit = {base_url}
        all_links = []
        base_domain = urlparse(base_url).netloc

        while to_visit and len(all_links) < max_links:
            url = to_visit.pop()
            if url in visited:
                continue
            
            visited.add(url)
            links = await get_links(page, url)
            
            for link in links:
                all_links.append((link, url))
                if recurse and urlparse(link).netloc == base_domain and link not in visited:
                    to_visit.add(link)
            
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
    parser.add_argument("--format", choices=["CSV"], default="CSV", help="Output format")
    args = parser.parse_args()

    base_url = os.environ.get('BASE_URL') # "https://library.soton.ac.uk"
    if not base_url:
        print("Error: BASE_URL environment variable is not set.")
        return

    print(f"Starting link collection for {base_url}")

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    links_file = f"reports/get-links-{date}.csv"


    if args.format == "CSV":
        with open(links_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["URL", "Parent URL"])
            
            async for links_batch in crawl_site(base_url, args.recurse):
                writer.writerows(links_batch)
        
        print(f"Links saved to get-links-{date}.csv")

if __name__ == "__main__":
    asyncio.run(main())
