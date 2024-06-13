import os
import requests
from playwright.sync_api import sync_playwright


def download_pdfs(page, download_dir="downloads"):
    """Extracts and downloads all PDF links from the page."""
    # Create directory to save PDFs if it doesn't exist
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    # Extract all PDF links
    pdf_links = page.locator("a[href$='.pdf']").evaluate_all(
        "elements => elements.map(el => el.href)"
    )

    for link in pdf_links:
        download_pdf(link, download_dir)


def download_pdf(url, download_dir):
    """Downloads a PDF from the given URL to the specified directory."""
    response = requests.get(url)
    if response.status_code == 200:
        pdf_name = os.path.join(download_dir, os.path.basename(url))
        with open(pdf_name, "wb") as f:
            f.write(response.content)
        print(f"Downloaded: {pdf_name}")
    else:
        print(f"Failed to download: {url}")


def main():
    url = "https://satcomm911.com/PDFS/?fbclid=IwZXh0bgNhZW0CMTAAAR2rTIc6FAMF2-ETkcD0vaPG2qa_WwSMS5BxhKQy3yFfLQrPX5nhJj2ldm4_aem_ZmFrZWR1bW15MTZieXRlcw"  # Replace with your actual URL

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # Wait for the page to load completely
        page.wait_for_load_state("networkidle")

        # Download all PDFs
        download_pdfs(page)

        browser.close()


if __name__ == "__main__":
    main()
