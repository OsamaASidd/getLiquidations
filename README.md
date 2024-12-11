# getLiquidations

A micro Flask application designed to fetch **liquidation data** from marketplace (Coinank) in real-time. This tool functions as a **data scraper** (using Selenium) and extracts key liquidation metrics as per the real-time liquidation map.

## Key Features

- **Real-Time Data**: Fetches liquidation details dynamically based on live market conditions.
- **Data Scraping with Selenium**: Utilizes Selenium to scrape and interact with marketplace web pages.
- **JSON Output**: Returns scraped data in a structured JSON format.

### Example JSON Response

```json
{
    "Symbol": "BTCUSD",
    "Price": 43000,
    "Value": 1000000,
    "Time": "2024-12-11T12:34:56",
    "Signal": "BUY"
}
