import csv
import asyncio
import aiohttp
from datetime import datetime
import os
from playwright.async_api import async_playwright

base_url = "https://library.soton.ac.uk/az.php"

async def get_links_with_playwright(url):
    links = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        
        await page.wait_for_selector('.s-lg-az-result')
        
        elements = await page.query_selector_all('.s-lg-az-result a')
        for element in elements:
            href = await element.get_attribute('href')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                links.add(href)
        
        await browser.close()
    return links

async def check_link(session, url, parent_url):
    try:
        async with session.head(url, allow_redirects=True, timeout=10) as response:
            return url, response.status, response.headers.get('Content-Type'), parent_url
    except Exception as e:
        return url, str(e), None, parent_url

async def main():
    print(f"Starting link check for {base_url}")
    
    links = await get_links_with_playwright(base_url)
    print(f"Found {len(links)} links")
    
    all_results = []
    async with aiohttp.ClientSession() as session:
        tasks = [check_link(session, link, base_url) for link in links]
        all_results = await asyncio.gather(*tasks)

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    report_file = f"reports/az-links-report-{date}.csv"

    with open(report_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL'])
        for result in all_results:
            writer.writerow(result)

    print(f"REPORT_FILE={report_file}")
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")

    broken_links = [url for url, status, _, _ in all_results if isinstance(status, int) and status != 200]
    message = "Broken links have been detected. Please check attached report for all link details." if broken_links else "No broken links found. Please check attached report for all link details."

    print(f"broken_links_found={'true' if broken_links else 'false'}")
    print(f"STATUS_MESSAGE={message}")

    github_output = os.environ.get('GITHUB_OUTPUT', 'github_output.txt')
    with open(github_output, 'a') as f:
        f.write(f"broken_links_found={'true' if broken_links else 'false'}\n")

    github_env = os.environ.get('GITHUB_ENV', 'github_env.txt')
    with open(github_env, 'a') as f:
        f.write(f"STATUS_MESSAGE={message}\n")

if __name__ == "__main__":
    asyncio.run(main())
