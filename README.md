
Last Updated on 2024-11-06

# Link Checkers

This has all the original workflows and scripts for now.

## Overview

This GitHub Actions workflow automates the process of checking links on
a library’s A-Z resources page. It performs web scraping, link
collection, and link validation to check resources are accessible.

It may produce false positives or false negatives, so doesn’t entirely
remove the need for manual validation, but should catch most broken
links.

## Features

- 🕷️ Web Scraping: Uses Playwright to collect links from the library’s
  A-Z page
- 🔗 Link Validation: Checks the status of each collected link
- 📊 Reporting: Generates detailed CSV reports of link statuses
- 📧 Notifications: Sends email alerts about broken links
- ⏰ Scheduled Runs: Automatically checks links weekly

## Workflow Components

### Scripts

1.  `get-az-links.py`
    - Scrapes links from the library’s A-Z page
    - Saves links to a dated CSV file
    - Uses Playwright for robust web scraping
2.  `url-checker.py` (not shown in provided code)
    - Validates collected links
    - Checks HTTP status codes
    - Generates link status reports

### GitHub Actions Workflow

- **Trigger**: Weekly on Mondays at 06:00 UTC
- **Manual Dispatch**: Can be triggered manually
- **Caching**: Implements caching for pip packages and Playwright
  browsers
- **Reporting**: Commits link reports to the repository
- **Notification**: Sends email with link status

## Prerequisites

- Python 3.x
- Playwright
- GitHub Actions enabled repository

## Configuration

### Required Secrets

Configure the following secrets in your GitHub repository:

- `AZ_URL`: Base URL of the library A-Z page
- `GMAIL_USERNAME`: SMTP email username
- `GMAIL_PASSWORD`: Your App Password. See [Create App
  passwords](https://knowledge.workspace.google.com/kb/how-to-create-app-passwords-000009237)
- `LL_EMAIL_RECIPIENT`: Primary email recipient
- `EMAIL_RECIPIENT`: CC email recipient
- `EMAIL_SENDER`: Sender email address

## Usage

1.  Fork the repository
2.  Set up required secrets
3.  The workflow will run automatically or can be manually triggered

## Output

- CSV files in `reports/` directory
  - `az-links-{date}.csv`: Collected links
  - `link-report-{date}.csv`: Link validation results
  - `404-report-{date}.csv`: Broken link details (if applicable)

## Contributing

Contributions are welcome! Please: - Fork the repository - Create a
feature branch - Submit a pull request

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## Support

For issues or questions, please create a GitHub issue and/or check the
existing documentation.
