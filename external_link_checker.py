import csv
import asyncio
import aiohttp
from datetime import datetime
import os
import sys
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright

base_url = "https://library.soton.ac.uk/az.php?"
urls = [f"{base_url}a={chr(i)}" for i in range(97, 123)]
urls.append(f"{base_url}a=other")

async def get_links_with_playwright(url):
    links = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle')
            
            # Wait for the content to load
            await page.wait_for_selector('.s-lg-az-result', timeout=30000)
            
            # Get all links from the result div
            elements = await page.query_selector_all('.s-lg-az-result a')
            for element in elements:
                href = await element.get_attribute('href')
                # Skip mailto: links and other unwanted protocols
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

async def check_link(session, url, parent_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with session.get(url, allow_redirects=True, timeout=10, headers=headers) as response:
            return url, response.status, response.headers.get('Content-Type'), parent_url
    except aiohttp.ClientError as e:
        return url, f"Error: {type(e).__name__}", None, parent_url
    except asyncio.TimeoutError:
        return url, "Error: Timeout", None, parent_url
    except Exception as e:
        return url, f"Error: {type(e).__name__}", None, parent_url

async def check_all_links(urls):
    all_results = []
    connector = aiohttp.TCPConnector(limit=10)
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for url in urls:
            print(f"Processing page: {url}")
            links = await get_links_with_playwright(url)
            
            tasks = []
            for link in links:
                tasks.append(check_link(session, link, url))
                await asyncio.sleep(0.1)  # Small delay between starting each request
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            valid_results = []
            for result in results:
                if isinstance(result, tuple):
                    valid_results.append(result)
                else:
                    print(f"Error checking link: {result}")
            
            all_results.extend(valid_results)
            await asyncio.sleep(1)  # Delay between pages
    
    return all_results

async def main():
    print(f"Starting link check for {len(urls)} pages")
    
    results = await check_all_links(urls)

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    report_file = f"reports/az-links-report-{date}.csv"

    with open(report_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL'])
        for url, status_code, content_type, parent_url in results:
            writer.writerow([url, status_code, content_type, parent_url])

    print(f"REPORT_FILE={report_file}")
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")

    broken_links = [url for url, status, _, _ in results if isinstance(status, (int, str)) and (not isinstance(status, int) or status != 200)]
    if broken_links:
        message = "Broken links have been detected. Please check attached report for all link details."
    else:
        message = "No broken links found. Please check attached report for all link details."

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
    