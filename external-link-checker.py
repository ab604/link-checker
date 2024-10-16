import csv
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import os
import sys
from urllib.parse import urlparse, urljoin

async def check_link(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            return url, response.status, response.headers.get('content-type', '')
    except Exception as e:
        return url, 'Error', str(e)

async def get_external_links(session, url):
    external_links = set()
    try:
        async with session.get(url, timeout=10) as response:
            text = await response.text()
        soup = BeautifulSoup(text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)
            if parsed_url.netloc != 'soton.ac.uk' and parsed_url.netloc != 'www.soton.ac.uk' and parsed_url.scheme in ['http', 'https']:
                external_links.add(full_url)
    except Exception as e:
        print(f"Error parsing {url}: {str(e)}", file=sys.stderr)
    return external_links

async def check_links(start_url):
    external_links = set()
    results = []

    async with aiohttp.ClientSession() as session:
        external_links = await get_external_links(session, start_url)

        for url in external_links:
            url, status_code, content_type = await check_link(session, url)
            results.append((url, status_code, content_type))
            print(f"Checked: {url} - Status: {status_code} - Content-Type: {content_type}")

    return results

async def main():
    start_url = os.environ.get('START_URL', 'https://www.library.soton.ac.uk')
    results = await check_links(start_url)

    os.makedirs('reports', exist_ok=True)
    date = datetime.now().strftime('%Y-%m-%d')
    report_file = f"reports/external-links-report-{date}.csv"

    with open(report_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type'])
        for url, status_code, content_type in results:
            writer.writerow([url, status_code, content_type])

    print(f"REPORT_FILE={report_file}")
    with open(os.environ['GITHUB_ENV'], 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")

    broken_links = [url for url, status, _ in results if status != 200]
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
