import csv
import asyncio
import os
from collections import deque
from playwright.async_api import async_playwright
from datetime import datetime
from urllib.parse import urljoin, urlparse

base_url = "https://library.soton.ac.uk/"
max_depth = 3  # Set a maximum depth for crawling

async def get_links_with_playwright(url):
    links = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle')
            
            await page.wait_for_selector('a', timeout=30000)
            
            elements = await page.query_selector_all('a')
            for element in elements:
                href = await element.get_attribute('href')
                if href and not href.startswith(('mailto:', '#', 'javascript:', 'tel:')):
                    full_url = urljoin(base_url, href)
                    if urlparse(full_url).netloc == urlparse(base_url).netloc:
                        links.add(full_url)
            
        except Exception as e:
            print(f"Error getting links from {url}: {str(e)}")
        finally:
            await browser.close()
    
    print(f"Found {len(links)} links on {url}")
    return links

async def crawl_site(start_url, max_depth):
    visited = set()
    queue = deque([(start_url, 0)])
    all_links = set()

    while queue:
        url, depth = queue.popleft()
        if depth > max_depth or url in visited:
            continue
        visited.add(url)
        links = await get_links_with_playwright(url)
        all_links.update(links)
        for link in links:
            if link not in visited:
                queue.append((link, depth + 1))
    
    return all_links

async def main():
    print(f"Starting link collection for {base_url}")
    
    links = await crawl_site(base_url, max_depth)

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    links_file = f"reports/links-{date}.csv"

    with open(links_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Parent URL'])
        for link in links:
            writer.writerow([link, base_url])

    print(f"LINKS_FILE={links_file}")
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"LINKS_FILE={links_file}\n")

    print(f"Links saved to {links_file}")

if __name__ == "__main__":
    asyncio.run(main())
