# Project: Google Maps Scraper

## Description: This Python project demonstrates how to use Playwright for automating web interactions and extracting data from Google Maps. It provides a flexible solution  for gathering business listings information. You need Python >= 3.10.14 installed on your computer to run this script.

### Features:

*   Searches Google Maps for specified terms
*   Efficiently scrolls through results for expanded data collection
*   Extracts the following information for each business listing:
    *   Name
    *   Address
    *   Website
    *   Phone Number
    *   Reviews Count
    *   Reviews Average
    *   Latitude
    *   Longitude
*   Saves results in both Excel (.xlsx) and CSV formats.

**Dependencies:**

*   Playwright: For browser automation. Install with `pip install playwright`
*   Pandas:  For data manipulation and saving to Excel. Install with `pip install pandas`
*   argparse: For command-line argument parsing. Install with `pip install argparse`

**Usage:**

Out Of Five businesses Scraped, only one business is valid.

1. **Install Dependencies:**
    - For Easy Install, Run 
    ```bash
        pip install -r requirements.txt
    ```
2. **Install Dependencies:**
   ```bash
   python -m venv scraper

   [Mac Users]
   source scraper/bin/activate

   [Windows Users on CMD]
   .\venv\Scripts\activate.bat

   pip install playwright pandas argparse

   playwright install

   pip install openpyxl
   ```

3. **Prepare Input:**
    *   **Passing Search Term as Argument:**
        ```bash
        python main.py -s="restaurants in New York City" -t=50
        ```
    `This will search for restaurants in New York City and collect up to 50 listings.`


3.  **Running the script:**
    The script will launch a browser instance, perform the specified searches, scrape data, and save the results into `output.xlsx` and `output.csv` files within an automatically created 'output' folder.

**Example Output:**

The saved Excel and CSV files will contain a structured table with the collected business information.

**Additional Notes**

*   Playwright's asynchronous functionality can be used for further performance optimization.  See Playwright documentation for how to do this: [invalid URL removed]
*   To avoid being detected by anti-scraping measures, consider:
    *   Introducing random delays between actions.
    *   Changing browser settings (user agent, etc.).
    *   Rotating IP addresses using proxies.

**Contact:**

If you have questions or suggestions, feel free to reach out on LinkedIn or Twitter! 

**Disclaimer**

Please use this script responsibly and check the Google Maps Terms of Service before large-scale scraping. 

