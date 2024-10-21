import csv
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import os
import sys
from urllib.parse import urlparse, urljoin
import chardet

base_url = "https://library.soton.ac.uk/az.php?"
# Create URLs for a-z using list comprehension
urls = [f"{base_url}a={chr(i)}" for i in range(97, 123)]
# Add the "other" URL
urls.append(f"{base_url}a=other")

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

async def get_links(session, url):
    links = set()
    try:
        async with session.get(url, timeout=10) as response:
            content = await response.read()
            text = decode_content(content)
        soup = BeautifulSoup(text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)
            if parsed_url.scheme in ['http', 'https']:
                links.add(full_url)
    except Exception as e:
        print(f"Error parsing {url}: {str(e)}", file=sys.stderr)
    return links

async def check_all_links(urls):
    results = []
    async with aiohttp.ClientSession() as session:
        for start_url in urls:
            print(f"Checking links on: {start_url}")
            links = await get_links(session, start_url)
            
            tasks = [check_link(session, link) for link in links]
            link_results = await asyncio.gather(*tasks)
            
            for url, status_code, content_type in link_results:
                results.append((url, status_code, content_type, start_url))
                print(f"Checked: {url} - Status: {status_code} - Content-Type: {content_type} - Parent: {start_url}")

    return results

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
    with open(os.environ['GITHUB_ENV'], 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")

    broken_links = [url for url, status, _, _ in results if status != 200]
    if broken_links:
        print("broken_links_found=true")
        print("STATUS_MESSAGE=Broken links have been detected. Please check attached report for all link details.")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write("broken_links_found=true\n")
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write("STATUS_MESSAGE=Broken links have been detected. Please check attached report for all link details.\n")
    else:
        print("broken_links_found=false")
        print("STATUS_MESSAGE=No broken links found. Please check attached report for all link details.")
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write("broken_links_found=false\n")
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write("STATUS_MESSAGE=No broken links found. Please check attached report for all link details.\n")

if __name__ == "__main__":
    asyncio.run(main())
