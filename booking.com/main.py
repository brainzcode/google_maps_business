from playwright.sync_api import sync_playwright
import pandas as pd


def main():
    with sync_playwright() as p:
        # IMPORTANT: Change dates to future dates, otherwise it won't work
        checkin_date = "2024-04-25"
        checkout_date = "2024-04-26"

        # page_url = f"https://www.booking.com/searchresults.en-us.html?checkin={checkin_date}&checkout={checkout_date}&selected_currency=USD&ss=Paris&ssne=Paris&ssne_untouched=Paris&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_type=city&group_adults=1&no_rooms=1&group_children=0&sb_travel_purpose=leisure"

        page_url2 = f"https://www.booking.com/searchresults.html?ss=London&ssne=London&ssne_untouched=London&efdco=1&label=gen173bo-1DCAQoggJCDXNlYXJjaF9sb25kb25IM1gDaKcBiAEBmAExuAEHyAEM2AED6AEB-AEDiAIBmAICqAIDuAK1raqwBsACAdICJGIwZDA5MzEzLTE4YjktNGVlNS05MmRiLWFhZjczNmRlMDJkOdgCBOACAQ&aid=304142&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_id=-2601889&dest_type=city&checkin={checkin_date}&checkout={checkout_date}&group_adults=1&no_rooms=1&group_children=0"

        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(page_url2, timeout=100000)

        hotels = page.locator('//div[@data-testid="property-card"]').all()
        print(f"There are: {len(hotels)} hotels.")

        hotels_list = []
        for hotel in hotels:
            hotel_dict = {}
            hotel_dict["hotel"] = hotel.locator(
                '//div[@data-testid="title"]'
            ).inner_text()
            hotel_dict["price"] = hotel.locator(
                '//span[@data-testid="price-and-discounted-price"]'
            ).inner_text()
            hotel_dict["score"] = hotel.locator(
                '//div[@data-testid="review-score"]/div[1]'
            ).inner_text()
            hotel_dict["avg review"] = hotel.locator(
                '//div[@data-testid="review-score"]/div[2]/div[1]'
            ).inner_text()
            hotel_dict["reviews count"] = (
                hotel.locator('//div[@data-testid="review-score"]/div[2]/div[2]')
                .inner_text()
                .split()[0]
            )

            hotels_list.append(hotel_dict)

        df = pd.DataFrame(hotels_list)
        df.to_excel("hotels_list.xlsx", index=False)
        df.to_csv("hotels_list.csv", index=False)

        browser.close()


if __name__ == "__main__":
    main()
