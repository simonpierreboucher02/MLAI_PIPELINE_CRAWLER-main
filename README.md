# MLAI Pipeline Crawler

![GitHub stars](https://img.shields.io/github/stars/simonpierreboucher/MLAI_PIPELINE_CRAWLER.svg?style=social&label=Star)
![GitHub forks](https://img.shields.io/github/forks/simonpierreboucher/MLAI_PIPELINE_CRAWLER.svg?style=social&label=Fork)
![GitHub issues](https://img.shields.io/github/issues/simonpierreboucher/MLAI_PIPELINE_CRAWLER.svg)
![GitHub license](https://img.shields.io/github/license/simonpierreboucher/MLAI_PIPELINE_CRAWLER.svg)


## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Output](#output)
- [Logging and Reports](#logging-and-reports)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)
- [Acknowledgements](#acknowledgements)

## Introduction

**MLAI Pipeline Crawler** is a comprehensive and flexible web crawler designed to extract content and downloadable files from websites. Whether you need to gather textual data, images, PDFs, or various document types, this crawler leverages modern Python libraries to facilitate efficient data collection. 

## Features

- **Recursive Crawling**: Navigate through a website up to a specified depth.
- **Download Support**: Automatically download PDFs, images, and documents with proper naming and tracking.
- **Content Extraction**: Extract and convert main page content to Markdown for easy readability.
- **Playwright Integration**: Optionally use Playwright for rendering JavaScript-heavy websites.
- **Configurable Settings**: Externalize configurations using a YAML file for flexibility.
- **Robust Logging**: Enhanced logging with colored outputs and detailed logs saved to files.
- **Progress Indicators**: Real-time progress bars and indicators to monitor crawling and downloading.
- **Report Generation**: Generate comprehensive reports and summaries post-crawl.
- **Resumable Crawls**: Track downloaded files to prevent redundant downloads in future runs.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- **Operating System**: Windows, macOS, or Linux.
- **Python**: Python 3.7 or higher installed. Download from [Python.org](https://www.python.org/downloads/).
- **Git**: For cloning the repository. Download from [Git-SCM.com](https://git-scm.com/downloads).

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/simonpierreboucher/MLAI_PIPELINE_CRAWLER.git
   cd MLAI_PIPELINE_CRAWLER
   ```

2. **Create a Virtual Environment (Optional but Recommended)**

   ```bash
   python3 -m venv venv
   ```

3. **Activate the Virtual Environment**

   - **Windows**

     ```bash
     venv\Scripts\activate
     ```

   - **macOS/Linux**

     ```bash
     source venv/bin/activate
     ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Install Playwright Browsers (If Using Playwright)**

   If you intend to use Playwright for rendering JavaScript-heavy websites, install the necessary browsers:

   ```bash
   playwright install
   ```

## Configuration

The crawler utilizes a YAML configuration file (`config.yaml`) to manage its settings. This allows for easy adjustments without modifying the core code.

**`config.yaml`**

```yaml
# Configuration for WebCrawler

start_url: "https://liquid-air.ca"  # Replace with the URL you want to crawl
max_depth: 3
use_playwright: true  # Set to false if you don't want to use Playwright

excluded_paths:
  - "selecteur-de-produits"  # Add other path segments to exclude if necessary

download_extensions:
  PDF:
    - ".pdf"
  Image:
    - ".png"
    - ".jpg"
    - ".jpeg"
    - ".gif"
    - ".svg"
  Doc:
    - ".doc"
    - ".docx"
    - ".xls"
    - ".xlsx"
    - ".ppt"
    - ".pptx"

language_pattern: "/(fr|en)-(ca|us)/"  # Adjust the pattern according to language/culture

base_dir: "crawler_output"  # Optional: Define the base directory for outputs
```

### Configuration Parameters

- **start_url**: The initial URL from which the crawler begins its operation.
- **max_depth**: The maximum depth the crawler will traverse through internal links.
- **use_playwright**: Boolean flag to enable or disable Playwright for rendering JavaScript.
- **excluded_paths**: List of URL path segments to exclude from crawling.
- **download_extensions**: Defines the file types to download categorized by their type (PDF, Image, Doc).
- **language_pattern**: Regular expression to target specific language or regional URL structures.
- **base_dir**: The base directory where outputs, logs, and downloads will be stored.

## Usage

After completing the installation and configuration, you can start the crawler using the provided `main.py` script.

```bash
python main.py
```

### Steps Performed by the Crawler

1. **Load Configuration**: Reads settings from `config.yaml`.
2. **Initialize Crawler**: Sets up directories, logging, and session configurations.
3. **URL Extraction (Phase 1)**: Recursively extracts URLs up to the specified depth while respecting exclusions and language patterns.
4. **Content Extraction (Phase 2)**: Fetches and processes content from extracted URLs, converts it to Markdown, and downloads specified file types.
5. **Report Generation**: Compiles a comprehensive report and summary of the crawling session.
6. **Cleanup**: Stops indicators, saves tracking files, and closes Playwright sessions if used.

## Project Structure

```
MLAI_PIPELINE_CRAWLER/
├── config.yaml
├── main.py
├── web_crawler.py
├── requirements.txt
├── README.md
├── crawler_output/          # Created after running the crawler
│   ├── content/
│   ├── PDF/
│   ├── Image/
│   ├── Doc/
│   ├── logs/
│   │   ├── crawler.log
│   │   └── downloaded_files.txt
│   ├── crawler_report.txt
│   └── summary.txt
└── venv/                    # If virtual environment is used
    └── ...
```

## Output

Upon running the crawler, the following outputs are generated in the `base_dir` (default is `crawler_output`):

- **content/**: Contains extracted main content in Markdown (`.txt`) format.
- **PDF/**: Contains downloaded PDF files.
- **Image/**: Contains downloaded image files.
- **Doc/**: Contains downloaded document files (e.g., `.docx`, `.xlsx`).
- **logs/**: Contains log files and tracking of downloaded files.
- **crawler_report.txt**: A comprehensive report detailing the crawl session.
- **summary.txt**: A concise summary of the crawling process.

## Logging and Reports

- **Logging**: Detailed logs are stored in `crawler_output/logs/crawler.log`. The logs include informational messages, warnings, errors, and debugging information with colored outputs for enhanced readability.
  
- **Downloaded Files Tracking**: `crawler_output/logs/downloaded_files.txt` keeps track of all downloaded files to prevent redundant downloads in subsequent runs.

- **Reports**:
  - **crawler_report.txt**: Contains a full report of the crawling session, including configurations, statistics, processed URLs, and generated files.
  - **summary.txt**: Provides a quick overview of the crawl, including the number of URLs processed, files downloaded, and the duration of the session.

## Troubleshooting

- **Playwright Issues**:
  - Ensure that Playwright browsers are installed by running `playwright install`.
  - If encountering issues with Playwright integration, consider setting `use_playwright: false` in `config.yaml` to use the Requests library instead.

- **SSL Certificate Issues**:
  - The crawler is configured to disable SSL verification (`session.verify = False`). If you encounter SSL-related warnings or errors, ensure that the target website's certificates are valid or consider enabling SSL verification if necessary.

- **Missing Dependencies**:
  - Ensure all dependencies are installed by running `pip install -r requirements.txt`.
  - If you encounter import errors, verify that you are using the correct Python environment.

- **Permission Errors**:
  - Ensure that the script has the necessary permissions to create and write to directories specified in `base_dir`.

## Contributing

Contributions are welcome! If you have suggestions for improvements, bug fixes, or new features, feel free to open an issue or submit a pull request.

1. **Fork the Repository**
2. **Create a New Branch**

   ```bash
   git checkout -b feature/YourFeature
   ```

3. **Commit Your Changes**

   ```bash
   git commit -m "Add your message here"
   ```

4. **Push to the Branch**

   ```bash
   git push origin feature/YourFeature
   ```

5. **Open a Pull Request**

## License

This project is licensed under the [MIT License](LICENSE). You are free to use, modify, and distribute this software as per the license terms.

## Author

**Simon-Pierre Boucher**

- [GitHub](https://github.com/simonpierreboucher)
- [LinkedIn](https://www.linkedin.com/in/simon-pierre-boucher/) *(Replace with actual link if available)*
- Contact: simon@example.com *(Replace with actual contact if desired)*

## Acknowledgements

- [Requests](https://docs.python-requests.org/en/latest/)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Playwright](https://playwright.dev/python/)
- [Colorama](https://pypi.org/project/colorama/)
- [TQDM](https://tqdm.github.io/)
- [Rich](https://rich.readthedocs.io/en/stable/)
- [HTML2Text](https://github.com/Alir3z4/html2text)
- [PyYAML](https://pyyaml.org/)
- [Python Logging Module](https://docs.python.org/3/library/logging.html)
