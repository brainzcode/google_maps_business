"""This script serves as an example on how to use Python
& Playwright to scrape/extract data from Google Search, Still a work in Progress.

Will Continue this Project Using Scrapy when I manage to get some free time, please do not use this script yet, as it's not a complete script.
"""

from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys


@dataclass
class SearchParams:
    """holds business data"""

    title: str = None
    url: str = None
    website_name: str = None
    description: str = None

    note1 = '//a[@jsname="UWckNb"]'
    title = '//a[@jsname="UWckNb"]//h3'
    to_be_excluded = '//div[@aria-level="2"]'
    description = '//div[@data-snf="nke7rc"]//div//'


@dataclass
class SearchLeads:
    search_leads: list[SearchParams] = field(default_factory=list)
    save_at = "output"

    def dataframe(self):
        """transform business_list to pandas dataframe

        Returns: pandas dataframe
        """
        return pd.json_normalize(
            (asdict(leads) for leads in self.search_leads), sep="_"
        )

    def save_to_excel(self, filename):
        """saves pandas dataframe to excel (xlsx) file

        Args:
            filename (str): filename
        """

        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"output/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        """saves pandas dataframe to csv file

        Args:
            filename (str): filename
        """

        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"output/{filename}.csv", index=False)


def main():
    ########
    # input
    ########

    # read search from arguments
    # parser = argparse.ArgumentParser()
    # parser.add_argument("-s", "--search", type=str)
    # # parser.add_argument("-t", "--total", type=int)
    # args = parser.parse_args()
    #
    # if args.search:
    #     search_list = [args.search]
    #
    # if args.total:
    #     total = args.total
    # else:
    #     # if no total is passed, we set the value to random big number
    #     total = 1_000_000
    #
    # if not args.search:
    #     search_list = []
    #     # read search from input.txt file
    #     input_file_name = 'input.txt'
    #     # Get the absolute path of the file in the current working directory
    #     input_file_path = os.path.join(os.getcwd(), input_file_name)
    #     # Check if the file exists
    #     if os.path.exists(input_file_path):
    #         # Open the file in read mode
    #         with open(input_file_path, 'r') as file:
    #             # Read all lines into a list
    #             search_list = file.readlines()
    #
    #     if len(search_list) == 0:
    #         print('Error occured: You must either pass the -s search argument, or add searches to input.txt')
    #         sys.exit()

    ###########
    # scraping
    ###########
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://www.google.com", timeout=60000)
        # wait is added for dev phase. can remove it in production
        page.wait_for_timeout(5000)

        # for search_for_index, search_for in enumerate(search_list):
        #     print(f"-----\n{search_for_index} - {search_for}".strip())

        page.locator('//div[@jsname="RNNXgb"]//textarea[@title="Search"]').fill(
            "best NextJS component library"
        )
        page.wait_for_timeout(3000)

        page.keyboard.press("Enter")
        page.wait_for_timeout(5000)

        # scrolling
        page.hover('//a[@jsname="UWckNb"]')

        # this variable is used to detect if the bot
        # scraped the same number of listings in the previous iteration
        previously_counted = 0

        browser.close()


if __name__ == "__main__":
    main()
