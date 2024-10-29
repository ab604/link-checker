"""
URL Checker Script
-----------------
This script performs asynchronous checking of URLs from a CSV file. It:
- Reads URLs from a CSV file
- Checks each URL's status using concurrent requests
- Generates reports for all links and specifically for 404 errors
- Supports batch processing to manage memory usage
- Implements retry logic for failed requests
- Uses semaphores to control concurrent connections
"""

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
        """
        Initialize URL checker with configurable parameters for request handling
        """
        self.max_retries = max_retries
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.max_concurrent = max_concurrent
        self.retry_delay = retry_delay
        self.semaphore = None
        # Set standard headers for requests to mimic browser behavior
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
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
        Check a single URL with retry logic and error handling
        Returns: Tuple of (url, status_code, content_type, parent_url, line_number)
        """
        print(f"Processing line {line_number}: {url}")
        async with self.semaphore:  # Control concurrent connections
            try:
                # Make the HTTP request with configured parameters
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
        Process URLs in batches to prevent memory issues
        """
        all_results = []
        for i in range(0, len(links), batch_size):
            batch = links[i:i + batch_size]
            async with aiohttp.ClientSession() as session:
                # Create tasks for each URL in the batch
                tasks = [
                    self.check_single_url(
                        session, 
                        link[0], 
                        link[1] if len(link) > 1 else "N/A",
                        i + idx + 2
                    ) 
                    for idx, link in enumerate(batch)
                ]
                batch_results = await asyncio.gather(*tasks)
                all_results.extend(batch_results)
            print(f"\nBatch complete: Processed {min(i + batch_size, len(links))}/{len(links)} URLs")
        return all_results

    async def check_all_links(self, links: List[List[str]]) -> List[Tuple[str, Any, str, str, int]]:
        """
        Main method to initialize semaphore and process all URLs
        """
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        return await self.check_urls_batch(links)

async def main():
    # Set up file paths and ensure directories exist
    date = datetime.now().strftime('%Y-%m-%d')
    links_file = f"reports/az-links-{date}.csv"
    os.makedirs('reports', exist_ok=True)
    
    # Read URLs from input CSV
    links = []
    with open(links_file, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header row
        links = list(reader)
    print(f"Checking {len(links)} links")
    
    # Initialize and run URL checker
    checker = URLChecker(
        max_retries=3,
        timeout_seconds=15,
        max_concurrent=50,
        retry_delay=1
    )
    results = await checker.check_all_links(links)
    results.sort(key=lambda x: x[4])  # Sort by line number
    
    # Generate main report
    report_file = f"reports/az-links-report-{date}.csv"
    with open(report_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL', 'Input Line'])
        writer.writerows(results)
    
    # Generate 404-specific report
    report_404_file = f"reports/az-links-404-report-{date}.csv"
    with open(report_404_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL', 'Input Line'])
        writer.writerows(result for result in results if isinstance(result[1], int) and result[1] == 404)
    
    # Set environment variables for GitHub Actions
    print(f"\nREPORT_FILE={report_file}")
    print(f"REPORT_404_FILE={report_404_file}")
    
    # Write environment variables to GitHub environment file
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")
        env_file.write(f"REPORT_404_FILE={report_404_file}\n")

    # Analyze results for broken links
    broken_links = [
        (url, line_num) 
        for url, status, _, _, line_num in results 
        if isinstance(status, (int, str)) and (not isinstance(status, int) or status != 200)
    ]
    
    # Output results and set GitHub Actions environment variables
    if broken_links:
        print("\nBroken links found in lines:")
        for url, line_num in broken_links:
            print(f"Line {line_num}: {url}")
    
    message = "Broken links detected." if broken_links else "No broken links found."
    
    # Write outputs for GitHub Actions
    github_output = os.environ.get('GITHUB_OUTPUT', 'github_output.txt')
    with open(github_output, 'a') as f:
        f.write(f"broken_links_found={'true' if broken_links else 'false'}\n")

    github_env = os.environ.get('GITHUB_ENV', 'github_env.txt')
    with open(github_env, 'a') as f:
        f.write(f"STATUS_MESSAGE={message}\n")

if __name__ == "__main__":
    asyncio.run(main())
