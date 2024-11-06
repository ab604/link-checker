import asyncio
import aiohttp
import csv
import os
from datetime import datetime, timedelta
from typing import List, Tuple, Any
from aiohttp import ClientTimeout
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
        self.semaphore = asyncio.Semaphore(max_concurrent)  # Initialize semaphore

        # Get GitHub Actions context
        run_id = os.environ.get('GITHUB_RUN_ID', 'unknown')
        workflow_name = os.environ.get('GITHUB_WORKFLOW', 'unknown')
        repository = os.environ.get('GITHUB_REPOSITORY', 'unknown')

        # Set headers for requests to mimic browser and provide server log tracking
        self.headers = {
            'User-Agent': f'GitHubActionAZLinkChecker/1.0 (Run:{run_id}; Workflow:{workflow_name}; Repo:{repository})',
            'X-GitHub-Action-Run': run_id,
            'X-Workflow-Source': workflow_name,
            'X-GitHub-Repository': repository,
            # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
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
            retry_state.args[0],  # url
            f'Failed after {retry_state.attempt_number} attempts: {str(retry_state.outcome.exception())}',
            None,  # content-type
            retry_state.args[1],  # parent_url
            retry_state.args[2]   # line_number
        )
    )
    async def check_single_url(self, url: str, parent_url: str, line_number: int) -> Tuple[str, Any, str, str, int]:
        """
        Check a single URL with retry logic and error handling
        Returns: Tuple of (url, status_code, content_type, parent_url, line_number)
        """
        print(f"Processing line {line_number}: {url}")
        async with self.semaphore:  # Control concurrent connections
            try:
                async with aiohttp.ClientSession() as session:
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
            tasks = [
                self.check_single_url(
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

async def process_and_write_batch(checker: URLChecker, batch: List[List[str]], writers: dict, batch_number: int, total_batches: int) -> List[Tuple[str, Any, str, str, int]]:
    print(f"\nProcessing batch {batch_number}/{total_batches}")
    results = await checker.check_urls_batch(batch)
    
    for result in results:
        url, status, content_type, parent_url, line_number = result
        writers['main'].writerow([url, status, content_type, parent_url, line_number])
        if isinstance(status, int) and status == 404:
            writers['404'].writerow([url, status, content_type, parent_url, line_number])
    
    return results

async def main():
    # Set up file paths and ensure directories exist
    date = datetime.now().strftime('%Y-%m-%d')
    old_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    links_file = os.environ.get('LINKS_FILE')
    if not links_file:
        links_file = f"reports/get-links-{old_date}.csv"
    os.makedirs('reports', exist_ok=True)
    
    # Initialize URL checker
    checker = URLChecker(
        max_retries=3,
        timeout_seconds=15,
        max_concurrent=50,
        retry_delay=1
    )

    # Open report files and create CSV writers
    report_file = f"reports/check-links-report-{date}.csv"
    report_404_file = f"reports/check-links-404-report-{date}.csv"
    
    with open(report_file, 'w', newline='', encoding='utf-8') as main_csvfile, \
         open(report_404_file, 'w', newline='', encoding='utf-8') as file_404_csvfile:
        
        writers = {
            'main': csv.writer(main_csvfile),
            '404': csv.writer(file_404_csvfile)
        }
        
        # Write headers
        for writer in writers.values():
            writer.writerow(['URL', 'Status Code', 'Content-Type', 'Parent URL', 'Input Line'])

        # Process links in batches
        batch_size = 1000
        broken_links = []
        batch_number = 0
        total_links = 0

        with open(links_file, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip header row

            batch = []
            for row in reader:
                batch.append(row)
                total_links += 1
                
                if len(batch) == batch_size:
                    batch_number += 1
                    results = await process_and_write_batch(checker, batch, writers, batch_number, (total_links + batch_size - 1) // batch_size)
                    
                    # Check for broken links in the batch
                    broken_links.extend([
                        (url, line_num) 
                        for url, status, _, _, line_num in results 
                        if isinstance(status, (int, str)) and (not isinstance(status, int) or status != 200)
                    ])
                    
                    batch = []  # Reset batch

            # Process any remaining links
            if batch:
                batch_number += 1
                results = await process_and_write_batch(checker, batch, writers, batch_number, (total_links + batch_size - 1) // batch_size)
                
                # Check for broken links in the final batch
                broken_links.extend([
                    (url, line_num) 
                    for url, status, _, _, line_num in results 
                    if isinstance(status, (int, str)) and (not isinstance(status, int) or status != 200)
                ])

    # Set environment variables and output results
    print(f"\nREPORT_FILE={report_file}")
    print(f"REPORT_404_FILE={report_404_file}")
    
    with open(os.environ.get('GITHUB_ENV', 'env.txt'), 'a') as env_file:
        env_file.write(f"REPORT_FILE={report_file}\n")
        env_file.write(f"REPORT_404_FILE={report_404_file}\n")

    if broken_links:
        print("\nBroken links found in lines:")
        for url, line_num in broken_links:
            print(f"Line {line_num}: {url}")
    
    message = "Broken links detected." if broken_links else "No broken links found."
    
    github_output = os.environ.get('GITHUB_OUTPUT', 'github_output.txt')
    with open(github_output, 'a') as f:
        f.write(f"broken_links_found={'true' if broken_links else 'false'}\n")

    github_env = os.environ.get('GITHUB_ENV', 'github_env.txt')
    with open(github_env, 'a') as f:
        f.write(f"STATUS_MESSAGE={message}\n")

if __name__ == "__main__":
    asyncio.run(main())
