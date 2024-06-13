# PDF Downloader using Playwright and Requests

This script allows you to scrape a webpage for PDF links and download all the PDFs to a specified directory. It leverages `playwright` to navigate and extract links from dynamic web content and `requests` to handle the file downloads.

## Prerequisites

- Python 3.7+
- Install necessary Python packages:
  ```sh
  pip install playwright requests
  playwright install
  ```

## How to Use

### 1. Clone the Repository

Clone this repository to your local machine.

```sh
git clone https://github.com/brainzcode/google_maps_business.git
cd /scraper/pdfs
```

### 2. Install Dependencies

Ensure you have the necessary Python packages installed:

```sh
pip install playwright requests
playwright install
```

### 3. Configure the URL

Open the `main.py` script and replace the URL in the `main()` function with the actual URL of the webpage containing the PDFs you want to download:

```python
def main():
    url = "http://example.com/your_page_with_pdfs"  # Replace with your actual URL
    download_pdfs_from_page(url)
```

### 4. Run the Script

Execute the script to start downloading PDFs:

```sh
python main.py
```

### 5. Check the Downloads

The downloaded PDFs will be saved in the `downloads` directory by default. You can change this directory by modifying the `download_dir` parameter in the `download_pdfs_from_page` function.

## Script Details

### Functions

- `download_pdfs_from_page(url, download_dir="downloads")`: Navigates to the specified URL, extracts all PDF links, and downloads them.
- `download_pdf(url, download_dir)`: Downloads a single PDF from the given URL to the specified directory.
- `main()`: Entry point of the script. Sets the target URL and initiates the PDF download process.

### Dependencies

- `playwright`: Used for navigating and extracting content from dynamic web pages.
- `requests`: Used for downloading PDF files from extracted links.
- `os`: Standard Python libraries for file handling.

## Example HTML Structure

The script looks for links ending with `.pdf` within anchor tags. Below is an example of the expected HTML structure:

```html
<a class="jstree-anchor" href="./PDFS/0000 AA- 6 HUD Insurance Claim Instructions.pdf" tabindex="-1" role="treeitem" aria-selected="false" aria-level="1" id="./PDFS/0000 AA- 6 HUD Insurance Claim Instructions.pdf_anchor">
  <i class="jstree-icon jstree-themeicon jstree-file jstree-themeicon-custom" role="presentation"></i>
  0000 AA- 6 HUD Insurance Claim Instructions.pdf
</a>
```

---

**Note**: Replace `"http://example.com/your_page_with_pdfs"` with the actual URL you want to scrape PDFs from. Make sure to test the script with different webpages to ensure compatibility.

---

Happy scraping! 🚀