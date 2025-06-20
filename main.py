import re
import sys
import yaml  # Ensure PyYAML is installed
from web_crawler import WebCrawler  # Ensure web_crawler.py is in the same directory or Python path


def load_config(config_path="config.yaml"):
    """
    Load and parse the YAML configuration file.

    :param config_path: Path to the configuration file.
    :return: Dictionary containing configuration parameters.
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        print(f"✅ Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        print(f"✘ Configuration file {config_path} not found.")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"✘ Error parsing YAML file: {exc}")
        sys.exit(1)


def main():
    # Load configuration from config.yaml
    config = load_config("config.yaml")

    # Extract configurations
    start_url = config.get("start_url", "https://liquid-air.ca")  # Default URL if not specified
    max_depth = config.get("max_depth", 3)
    use_playwright = config.get("use_playwright", False)
    excluded_paths = config.get("excluded_paths", ['selecteur-de-produits'])
    download_extensions = config.get("download_extensions", {
        'PDF': ['.pdf'],
        'Image': ['.png', '.jpg', '.jpeg', '.gif', '.svg'],
        'Doc': ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
    })
    language_pattern_str = config.get("language_pattern", None)
    base_dir = config.get("base_dir", "crawler_output")

    # Compile the language pattern if provided
    language_pattern = re.compile(language_pattern_str) if language_pattern_str else None

    # Instantiate the WebCrawler with the loaded configurations
    crawler = WebCrawler(
        start_url=start_url,
        max_depth=max_depth,
        use_playwright=use_playwright,
        excluded_paths=excluded_paths,
        download_extensions=download_extensions,
        language_pattern=language_pattern,
        base_dir=base_dir
    )

    # Start crawling
    crawler.crawl()


if __name__ == "__main__":
    main()
