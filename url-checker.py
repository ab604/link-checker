import asyncio
import aiohttp
import csv
import os
from datetime import datetime
from typing import List, Tuple, Any
from aiohttp import ClientTimeout, ClientResponse
from tenacity import retry, stop_after_attempt, wait_exponential

class URLChecker:
    def __init__(self, 
                 max_retries: int = 3,
                 timeout_seconds: int = 10,
                 max_concurrent: int = 50,
                 retry_delay: int = 1):
        self.max_retries = max_retries
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.max_concurrent = max_concurrent
        self.retry_delay = retry_delay
        self.semaphore = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_error_callback=lambda retry_state: (
            retry_state.args[1],  # url
            f'Failed after {retry_state.attempt_number} attempts: {str(retry_state.outcome.exception())}',
            None,  # content-type
            retry_state.args[2],  # parent_url
            retry_state.args[3]   # line_number
        )
    )
    async def check_single_url(self, session: aiohttp.ClientSession, url: str, parent_url: str, line_number: int) -> Tuple[str, Any, str, str, int]:
        """
        Check a single URL and return tuple of (url, status_code, content_type, parent_url, line_number).
        """
        print(f"Processing line {line_number}: {url}")
        async with self.semaphore:
            try:
                async with session.get(
                    url, 
                    timeout=self.timeout,
                    allow_redirects=True,
                    ssl=False,
                    headers=self.headers
                ) as response:
                    content_type = response.headers.get('Content-Type', 'Unknown')
                    return url, response.status, content_type, parent_url, line_number
            except asyncio.TimeoutError:
                return url, f"Timeout after {self.timeout.total} seconds", None, parent_url, line_number
            except aiohttp.ClientError as e:
                return url, f"Connection error: {str(e)}", None, parent_url, line_number
            except Exception as e:
                return url, f"Unexpected error: {str(e)}", None, parent_url, line_number

    async def check_urls_batch(self, links: List[List[str]], batch_size: int = 1000) -> List[Tuple[str, Any, str, str, int]]:
        """
        Process URLs in batches to prevent memory issues.
        """
        all_results = []
        for i in range(0, len(links), batch_size):
            batch = links[i:i + batch_size]
            async with aiohttp.ClientSession() as session:
                tasks = [
                    self.check_single_url(
                        session, 
                        link[0], 
                        link[1] if len(link) > 1 else "N/A",
                        i + idx + 2  # +2 because we skip header and 0-based index
                    ) 
                    for idx, link in enumerate(batch)
                ]
                batch_results = await asyncio.gather(*tasks)
                all_results.extend(batch_results)
            print(f"\nBatch complete: Processed {min(i + batch_size, len(links))}/{len(links)} URLs")
        return all_results

    async def check_all_links(self, links: List[List[str]]) -> List[Tuple[str, Any, str, str, int]]:
        """
        Main method to check all URLs.
        """
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        return await self.check_urls_batch(links)

async def main():
    # Load links from CSV
    date = datetime.now().strftime('%Y-%m-%d')
    links_file = f"reports/az-links-{date}.csv"
    #links_file = f"reports/test.csv"
    
    # Ensure reports directory exists
    os.makedirs('reports', exist_ok=True)
    
    # Read links from CSV
    links = []
    with open(links_file, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        links = list(reader)
    print(f"Checking {len(links)} links")
    
    # Initialize checker with custom configuration
    checker = URLChecker(
        max_retries=3,
        timeout_seconds=15,
        max_concurrent=50,
        retry_delay=1
    )
    
    # Check all links
    results = await checker.check_all_links(links)
    
    # Sort results by line number before writing
    results.sort(key=lambda x: x[4])  # Sort by line number
    
    # Write results to main report
    report_file = f"reports/az-links-report-{date}.csv"
    with open(report_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL', 'Input Line'])
        for url, status_code, content_type, parent_url, line_number in results:
            writer.writerow([url, status_code, content_type, parent_url, line_number])
    
    # Write 404 status links to separate report
    report_404_file = f"reports/az-links-404-report-{date}.csv"
    with open(report_404_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL', 'Input Line'])
        for result in results:
            if isinstance(result[1], int) and result[1] == 404:
                writer.writerow(result)
    
    print(f"\nREPORT_FILE={report_file}")
    print(f"REPORT_404_FILE={report_404_file}")
    
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")
        env_file.write(f"REPORT_404_FILE={report_404_file}\n")

    # Check for broken links
    broken_links = [
        (url, line_num) 
        for url, status, _, _, line_num in results 
        if isinstance(status, (int, str)) and (not isinstance(status, int) or status != 200)
    ]
    
    if broken_links:
        print("\nBroken links found in lines:")
        for url, line_num in broken_links:
            print(f"Line {line_num}: {url}")
    
    message = "Broken links have been detected. Please check attached report for all link details." if broken_links else "No broken links found. Please check attached report for all link details."
    
    print(f"\nbroken_links_found={'true' if broken_links else 'false'}")
    print(f"STATUS_MESSAGE={message}")

    github_output = os.environ.get('GITHUB_OUTPUT', 'github_output.txt')
    with open(github_output, 'a') as f:
        f.write(f"broken_links_found={'true' if broken_links else 'false'}\n")

    github_env = os.environ.get('GITHUB_ENV', 'github_env.txt')
    with open(github_env, 'a') as f:
        f.write(f"STATUS_MESSAGE={message}\n")

if __name__ == "__main__":
    asyncio.run(main())
