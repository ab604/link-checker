"""
This script scrapes links from a library website using Playwright.
It performs asynchronous web scraping and saves the collected links to a CSV file.
The script is designed to work with GitHub Actions but can run independently.
"""

# Import required libraries
import csv
import asyncio
import os
from playwright.async_api import async_playwright
from datetime import datetime

# Define the target URL for scraping
base_url = os.environ['BASE_URL'] # "https://library.soton.ac.uk/az.php?"
if not base_url:
        base_url = "https://library.soton.ac.uk/az.php?"

async def get_links_with_playwright(url):
    """
    Asynchronously scrapes links from the specified URL using Playwright.
    Returns a set of unique links found on the page.
    """
    links = set()
    async with async_playwright() as p:
        # Launch a Chromium browser instance
        browser = await p.chromium.launch()
        try:
            # Create a new page and navigate to the URL
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle')
            
            # Wait for the results container to load
            await page.wait_for_selector('.s-lg-az-result', timeout=30000)
            
            # Extract all links from the results
            elements = await page.query_selector_all('.s-lg-az-result a')
            for element in elements:
                href = await element.get_attribute('href')
                # Filter out invalid or unwanted link types
                if href and not href.startswith(('mailto:', '#', 'javascript:', 'tel:')):
                    # Convert protocol-relative URLs to absolute URLs
                    if href.startswith('//'):
                        href = 'https:' + href
                    links.add(href)
            
        except Exception as e:
            print(f"Error getting links from {url}: {str(e)}")
        finally:
            # Ensure browser is closed even if an error occurs
            await browser.close()
    
    print(f"Found {len(links)} links on {url}")
    return links

async def main():
    """
    Main function that orchestrates the link collection and saving process.
    """
    print(f"Starting link collection for {base_url}")
    
    # Collect links using Playwright
    links = await get_links_with_playwright(base_url)

    # Create reports directory if it doesn't exist
    os.makedirs('reports', exist_ok=True)
    
    # Generate filename with current date
    date = datetime.now().strftime('%Y-%m-%d')
    links_file = f"reports/az-links-{date}.csv"

    # Save links to CSV file
    with open(links_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Parent URL'])
        for link in links:
            writer.writerow([link, base_url])

    # Set environment variable for GitHub Actions
    print(f"LINKS_FILE={links_file}")
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"LINKS_FILE={links_file}\n")

    print(f"Links saved to {links_file}")

# Entry point of the script
if __name__ == "__main__":
    asyncio.run(main())
