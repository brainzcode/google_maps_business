# Hotel Scraper

This project is a web scraper built with Python using the Playwright library. It extracts hotel information from Booking.com for specified dates and destinations, and saves the data into Excel and CSV files.

## Table of Contents
- [Hotel Scraper](#hotel-scraper)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Project Structure](#project-structure)
  - [Contributing](#contributing)
  - [License](#license)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/brainzcode/hotel-scraper.git
   cd hotel-scraper
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Playwright and its dependencies:
   ```bash
   playwright install
   ```

## Usage

1. Open the `main.py` file and update the `checkin_date` and `checkout_date` variables to the desired future dates. The script won't work with past dates.

2. Run the script:
   ```bash
   python main.py
   ```

3. The script will open a browser window, navigate to the specified Booking.com search results page, and scrape hotel data.

4. After completion, the data will be saved into `hotels_list.xlsx` and `hotels_list.csv` files in the project directory.

## Project Structure

```
hotel-scraper/
├── main.py
├── requirements.txt
├── hotels_list.xlsx
├── hotels_list.csv
└── README.md
```

- `main.py`: The main script that runs the web scraper.
- `requirements.txt`: File containing the list of dependencies.
- `hotels_list.xlsx`: The output Excel file with scraped hotel data.
- `hotels_list.csv`: The output CSV file with scraped hotel data.
- `README.md`: Project documentation.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

Feel free to update the README.md file with more details as the project evolves.