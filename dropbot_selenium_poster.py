#!/usr/bin/env python3
"""
dropbot_selenium_poster.py

Automates most of a Facebook Marketplace listing via Selenium,
using a dedicated Chrome profile. Keeps the browser open at the end.

Run with:
    pip install selenium webdriver-manager
    python3 dropbot_selenium_poster.py
"""

import os, time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# === CONFIGURATION ===
LISTING_FOLDER   = "/Users/samiksha/Desktop/DropBot/listings/001"
SELENIUM_PROFILE = os.path.expanduser("~/selenium_profile")
LOCATION_CITY    = "New York"   # change as needed

def load_text(fname):
    with open(os.path.join(LISTING_FOLDER, fname), "r", encoding="utf-8") as f:
        return f.read().strip()

# Load generated content
title       = load_text("title.txt")
description = load_text("description.txt")
price       = load_text("final_price.txt")

# Collect up to 4 images
images = [
    p for p in (
        os.path.join(LISTING_FOLDER, f"image_{i}.jpg") for i in range(1,5)
    )
    if os.path.exists(p)
]

# === SELENIUM SETUP ===
options = Options()
# keep Chrome open after script ends
options.add_experimental_option("detach", True)
# use your own profile so you're already logged in
options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
wait = WebDriverWait(driver, 20)

# === AUTOMATION ===

# 1) Open the “Create new listing” page
driver.get("https://www.facebook.com/marketplace/create/item")
time.sleep(5)  # allow React UI to load

# 2) Title (first text input)
inp = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input[type='text']")))[0]
inp.clear(); inp.send_keys(title)

# 3) Description (first textarea)
ta = wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
ta.clear(); ta.send_keys(description)

# 4) Price (second text input)
inp2 = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input[type='text']")))[1]
inp2.clear(); inp2.send_keys(price)

# 5) Condition → New
cond = wait.until(EC.element_to_be_clickable((
    By.XPATH,
    "//span[normalize-space(text())='Condition']/ancestor::label[@role='combobox']"
)))
cond.click()
new_opt = wait.until(EC.element_to_be_clickable((
    By.XPATH,
    "//div[@role='listbox']//span[normalize-space(text())='New']"
)))
new_opt.click()

# 6) Manual Category
print("🔔 Please choose Category in the browser UI now.")
input("After selecting Category, press Enter here to continue...")

# 7) Expand “More details” if needed
try:
    more = driver.find_element(By.XPATH, "//span[normalize-space(text())='More details']")
    more.click()
    time.sleep(1)
except:
    pass

# 8) Set Location
loc_inp = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@aria-label='Location']")))
loc_inp.clear()
loc_inp.send_keys(LOCATION_CITY)
loc_inp.send_keys("\n")

# 9) Upload images
file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))
file_input.send_keys("\n".join(images))

# 10) Final pause
print("✅ All fields filled. Browser will stay open so you can review.")
input("Press Enter here when you’ve clicked POST and are ready to close...")
# Note: because of `detach=True`, driver.quit() is not needed to keep window open.
