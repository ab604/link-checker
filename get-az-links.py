import csv
import asyncio
import os
from playwright.async_api import async_playwright
from datetime import datetime

base_url = "https://library.soton.ac.uk/az.php?"

async def get_links_with_playwright(url):
    links = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle')
            
            await page.wait_for_selector('.s-lg-az-result', timeout=30000)
            
            elements = await page.query_selector_all('.s-lg-az-result a')
            for element in elements:
                href = await element.get_attribute('href')
                if href and not href.startswith(('mailto:', '#', 'javascript:', 'tel:')):
                    if href.startswith('//'):
                        href = 'https:' + href
                    links.add(href)
            
        except Exception as e:
            print(f"Error getting links from {url}: {str(e)}")
        finally:
            await browser.close()
    
    print(f"Found {len(links)} links on {url}")
    return links

async def main():
    print(f"Starting link collection for {base_url}")
    
    links = await get_links_with_playwright(base_url)

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    links_file = f"reports/az-links-{date}.csv"

    with open(links_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Parent URL'])
        for link in links:
            writer.writerow([link, base_url])

    print(f"Links saved to {links_file}")

    # Set output for GitHub Actions
    print(f"::set-output name=links_file::{links_file}")

    # Set environment variable for GitHub Actions
    print(f"::set-env name=LINKS_FILE::{links_file}")

if __name__ == "__main__":
    asyncio.run(main())
