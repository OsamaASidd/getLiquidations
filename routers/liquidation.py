from flask import Blueprint, jsonify, request
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

bp = Blueprint('liquidation', __name__)

@bp.route("/liquidations")
def get_liquidations():
    # Set up the WebDriver
    driver = webdriver.Chrome()
    driver.maximize_window()
    driver.get("https://coinank.com/liquidation")

    wait = WebDriverWait(driver, 20)
    try:
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".order-box")))

        real_time_section = driver.find_element(By.CSS_SELECTOR, ".order-box")

        dropdowns = real_time_section.find_elements(By.CSS_SELECTOR, ".ant-select.ant-select-enabled")

        print("Found dropdowns:", len(dropdowns))

        if len(dropdowns) < 3:
            raise Exception("Could not find all three dropdowns in the 'Real-Time Liquidations' section.")

        amount_dropdown = dropdowns[2]

        amount_dropdown.click()

        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".ant-select-dropdown-menu")))

        dropdown_menu = driver.find_element(By.CSS_SELECTOR, ".ant-select-dropdown-menu")
        amount_options = dropdown_menu.find_elements(By.CSS_SELECTOR, ".ant-select-dropdown-menu-item")

        print("Number of options in 'Amount' dropdown:", len(amount_options))

        if len(amount_options) < 3:
            raise Exception("Not enough options in the 'Amount' dropdown")

        desired_option = amount_options[2]
        desired_option.click()


        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".main-B02UUUN3 .order-item")))

    except Exception as e:
        print(f"An error occurred while interacting with the dropdown: {e}")
        driver.quit()
        return jsonify({"error": "Failed to interact with the dropdown"}), 500

    data = []

    rows = driver.find_elements(By.CSS_SELECTOR, ".main-B02UUUN3 .order-item")

    for row in rows:
        try:
            symbol = row.find_element(By.CSS_SELECTOR, ".time").text
            price = row.find_element(By.CSS_SELECTOR, ".large-price").text
            turnover = row.find_element(By.CSS_SELECTOR, ".large-turnover").text
            time_data = row.find_element(By.CSS_SELECTOR, ".amount:last-child").text

            turnover_value = turnover.strip()
            if 'K' in turnover_value:
                turnover_float = float(turnover_value.replace('K', '').strip()) * 1000
            elif 'M' in turnover_value:
                turnover_float = float(turnover_value.replace('M', '').strip()) * 1000000
            else:
                turnover_float = float(turnover_value.replace(',', '').strip())

            if turnover_float > 20000:
                data.append({
                    "Symbol": symbol,
                    "Price": price,
                    "Value": turnover,
                    "Time": time_data
                })
        except Exception as e:
            print(f"An error occurred while scraping a row: {e}")
            continue

    driver.quit()
    return jsonify(data), 200

