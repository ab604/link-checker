import csv
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import os
import sys
from urllib.parse import urlparse, urljoin

base_url = "https://library.soton.ac.uk/az.php?"
# Create URLs for a-z using list comprehension
urls = [f"{base_url}a={chr(i)}" for i in range(97, 123)]
# Add the "other" URL
urls.append(f"{base_url}a=other")

def decode_content(content):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('iso-8859-1')

async def get_links(session, url):
    links = set()
    try:
        async with session.get(url, timeout=10) as response:
            content = await response.read()
            text = decode_content(content)
        soup = BeautifulSoup(text, 'html.parser')
        
        main_content = soup.find('div', {'id': 's-lg-az-cols'})
        
        if main_content:
            for link in main_content.find_all('a', href=True):
                href = link['href']
                if href.startswith('#') or href.startswith('javascript:'):
                    continue
                full_url = urljoin(url, href)
                parsed_url = urlparse(full_url)
                if parsed_url.scheme in ['http', 'https']:
                    links.add(full_url)
        
        print(f"Found {len(links)} unique links on {url}")
        
    except Exception as e:
        print(f"Error parsing {url}: {str(e)}", file=sys.stderr)
    return links

async def check_link(session, url, parent_url):
    try:
        async with session.head(url, allow_redirects=True, timeout=10) as response:
            return url, response.status, response.headers.get('Content-Type'), parent_url
    except Exception as e:
        return url, str(e), None, parent_url

async def check_all_links(urls):
    all_results = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            links = await get_links(session, url)
            tasks = [check_link(session, link, url) for link in links]
            results = await asyncio.gather(*tasks)
            all_results.extend(results)
    return all_results

async def main():
    print(f"Starting link check for {len(urls)} pages")
    
    results = await check_all_links(urls)

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    report_file = f"reports/az-links-report-{date}.csv"

    with open(report_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL'])
        for url, status_code, content_type, parent_url in results:
            writer.writerow([url, status_code, content_type, parent_url])

    print(f"REPORT_FILE={report_file}")
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")

    broken_links = [url for url, status, _, _ in results if status != 200]
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
