import csv
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import os
import sys
from urllib.parse import urlparse, urljoin
import chardet

SKIP_DOMAINS = [
    'eprints.soton.ac.uk',
    'facebook.com',
    'google.com'
    # Add more domains here
]

SKIP_URLS = [
    'https://www.specific-page-to-skip.com/page',
    'https://another-specific-page.org/skip-this',
    # Add more specific URLs here
]

async def check_link(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            return url, response.status, response.headers.get('content-type', '')
    except Exception as e:
        return url, 'Error', str(e)

def decode_content(content):
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        detected = chardet.detect(content)
        try:
            return content.decode(detected['encoding'])
        except:
            return content.decode('latin-1')

from urllib.parse import urlparse, urljoin

async def get_links(session, url):
    internal_links = set()
    external_links = set()
    try:
        async with session.get(url, timeout=10) as response:
            content = await response.read()
            text = decode_content(content)
        soup = BeautifulSoup(text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)
            
            # Check if the URL should be skipped
            if any(domain in parsed_url.netloc for domain in SKIP_DOMAINS) or full_url in SKIP_URLS:
                continue
            
            if parsed_url.netloc.endswith('soton.ac.uk') and parsed_url.scheme in ['http', 'https']:
                internal_links.add(full_url)
            elif parsed_url.scheme in ['http', 'https']:
                external_links.add(full_url)
    except Exception as e:
        print(f"Error parsing {url}: {str(e)}", file=sys.stderr)
    return internal_links, external_links

async def crawl_and_check_links(start_url, max_pages=100):
    visited = set()
    to_visit = {start_url}
    all_external_links = {}
    results = []

    async with aiohttp.ClientSession() as session:
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop()
            if url in visited:
                continue
            
            # Check if the URL should be skipped
            parsed_url = urlparse(url)
            if any(domain in parsed_url.netloc for domain in SKIP_DOMAINS) or url in SKIP_URLS:
                continue
            
            visited.add(url)
            print(f"Crawling: {url}")

            internal, external = await get_links(session, url)
            to_visit.update(internal - visited)
            for ext_link in external:
                if ext_link not in all_external_links:
                    all_external_links[ext_link] = url

        print(f"Checking {len(all_external_links)} external links...")
        for ext_url, parent_url in all_external_links.items():
            # Check if the external URL should be skipped
            parsed_ext_url = urlparse(ext_url)
            if any(domain in parsed_ext_url.netloc for domain in SKIP_DOMAINS) or ext_url in SKIP_URLS:
                continue
            
            url, status_code, content_type = await check_link(session, ext_url)
            results.append((url, status_code, content_type, parent_url))
            print(f"Checked: {url} - Status: {status_code} - Content-Type: {content_type} - Parent: {parent_url}")

    return results

async def main():
    start_url = os.environ.get('START_URL', 'https://www.library.soton.ac.uk')
    
    try:
        max_pages = int(os.environ.get('MAX_PAGES', ''))
    except ValueError:
        print("Invalid or missing MAX_PAGES value. Using default of 500.")
        max_pages = 500

    print(f"Starting crawl from {start_url} with max pages set to {max_pages}")
    
    results = await crawl_and_check_links(start_url, max_pages)

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    report_file = f"reports/external-links-report-{date}.csv"

    with open(report_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL'])
        for url, status_code, content_type, parent_url in results:
            writer.writerow([url, status_code, content_type, parent_url])

    print(f"REPORT_FILE={report_file}")
    with open(os.environ['GITHUB_ENV'], 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")

    broken_links = [url for url, status, _, _ in results if status != 200]
    if broken_links:
        print("broken_links_found=true")
        print("STATUS_MESSAGE=Broken external links have been detected. Please check attached report for all link details.")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write("broken_links_found=true\n")
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write("STATUS_MESSAGE=Broken external links have been detected. Please check attached report for all link details.\n")
    else:
        print("broken_links_found=false")
        print("STATUS_MESSAGE=No broken external links found. Please check attached report for all link details.")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write("broken_links_found=false\n")
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write("STATUS_MESSAGE=No broken external links found. Please check attached report for all link details.\n")

if __name__ == "__main__":
    asyncio.run(main())
