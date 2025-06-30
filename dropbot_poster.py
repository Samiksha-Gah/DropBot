#!/usr/bin/env python3
"""
dropbot_poster.py

Fetches the full HTML of a CJdropshipping or DHGate product page,
asks Dobby to extract key fields as JSON, then asks Dobby again to
generate your Facebook listing (title, description, upsell price,
tags, category). Downloads images, saves everything into per‑listing
folders, updates the CSV, and opens FB Marketplace for your UI Vision macro.

Run with:
    python3 dropbot_poster.py
"""

import os
import csv
import json
import requests
import time
import webbrowser

# === CONFIGURATION ===
DOBBY_API_KEY  = ""  # ← your Fireworks key
DOBBY_ENDPOINT = "https://api.fireworks.ai/inference/v1/chat/completions"
DOBBY_MODEL    = "accounts/sentientfoundation/models/dobby-unhinged-llama-3-3-70b-new"

LISTINGS_CSV = "/Users/samiksha/Desktop/DropBot/listings.csv"
LISTINGS_DIR = "/Users/samiksha/Desktop/DropBot/listings"

REQUEST_TIMEOUT = 30  # seconds
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/15.1 Safari/605.1.15"
    )
}
MAX_IMAGES = 4


def read_listings(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def write_listings(csv_path, rows):
    fieldnames = ['product_name', 'cj_link', 'tags', 'posted']
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def call_dobby_api(prompt_text):
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {DOBBY_API_KEY}'
    }
    payload = {
        'model': DOBBY_MODEL,
        'messages': [{'role': 'user', 'content': prompt_text}],
        'max_tokens': 2048,
        'temperature': 0.7,
        'top_p': 1.0
    }
    resp = requests.post(DOBBY_ENDPOINT, headers=headers, json=payload)
    if resp.status_code != 200:
        print("❌ Fireworks API error:", resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()


def parse_product_page(url):
    print("🔍 Fetching raw page…")
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    raw_html = resp.text

    parser_prompt = f"""
You are a JSON extractor.
Here is the full HTML of a product page:
---
{raw_html}
---

Extract exactly the following fields and return a single JSON object:
  scraped_title: the product title
  price: the base price (include currency symbol)
  shipping_fee: the numeric shipping fee
  overview: the product overview description text
  image_urls: a JSON array of up to {MAX_IMAGES} full image URLs

Respond with valid JSON ONLY.
"""
    print("🤖 Asking Dobby to parse the page…")
    resp_text = call_dobby_api(parser_prompt)

    # strip code fences
    if resp_text.startswith("```"):
        resp_text = "\n".join(resp_text.strip().splitlines()[1:-1])

    try:
        data = json.loads(resp_text)
    except json.JSONDecodeError:
        print("❌ JSON parse failed, response was:\n", resp_text)
        raise

    # ensure list
    imgs = data.get('image_urls',[])
    data['image_urls'] = imgs if isinstance(imgs, list) else []

    return data


def generate_fb_listing(product_info, manual_name, tags_hint):
    product_info['manual_name'] = manual_name or product_info.get('scraped_title','')
    fb_prompt = f"""
You are helping a seller post a product on Facebook Marketplace.

Here is the extracted product info as JSON:
{json.dumps(product_info, indent=2)}

Write me a JSON object with keys:
  title: catchy listing title
  description: friendly but compelling post copy
  final_price: upsell price (include shipping in amount, don’t mention it)
  tags: array of 5–10 keywords
  category: best-fit Marketplace category

Tone: formal yet friendly, say "brand new, packaged", "non-sale price is [higher number]", and "direct free shipping".
"""
    print("🤖 Asking Dobby to write the Facebook listing…")
    resp_text = call_dobby_api(fb_prompt)

    # extract JSON between first { and last }
    start = resp_text.find('{')
    end   = resp_text.rfind('}')
    if start == -1 or end == -1:
        print("❌ No JSON object found in:\n", resp_text)
        raise ValueError("Invalid JSON reply")

    json_str = resp_text[start:end+1]
    listing = json.loads(json_str)

    # normalize tags
    tags = listing.get('tags',[])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    listing['tags'] = tags

    return listing


def process_listing(idx, listing):
    url = listing['cj_link']
    print(f"[{idx:03d}] Parsing page: {url}")
    product = parse_product_page(url)

    fb = generate_fb_listing(product,
                             listing.get('product_name','').strip(),
                             listing.get('tags',''))

    folder = os.path.join(LISTINGS_DIR, f"{idx:03d}")
    os.makedirs(folder, exist_ok=True)

    # save parser output
    with open(os.path.join(folder,'parsed.json'),'w') as f:
        json.dump(product, f, indent=2)

    # save listing files
    open(os.path.join(folder,'title.txt'),'w').write(fb.get('title',''))
    open(os.path.join(folder,'description.txt'),'w').write(fb.get('description',''))
    open(os.path.join(folder,'final_price.txt'),'w').write(fb.get('final_price',''))
    open(os.path.join(folder,'tags.txt'),'w').write(','.join(fb.get('tags',[])))
    open(os.path.join(folder,'category.txt'),'w').write(fb.get('category',''))

    # download images
    for i, img_url in enumerate(product['image_urls'][:MAX_IMAGES], start=1):
        try:
            data = requests.get(img_url, headers=HEADERS, timeout=REQUEST_TIMEOUT).content
            with open(os.path.join(folder,f'image_{i}.jpg'),'wb') as imgf:
                imgf.write(data)
        except Exception as e:
            print(f"⚠️ Image {img_url} failed:", e)

    return folder


def main():
    os.makedirs(LISTINGS_DIR, exist_ok=True)
    rows = read_listings(LISTINGS_CSV)
    did_any = False

    for idx, r in enumerate(rows, start=1):
        if r.get('posted','').lower() != 'no': continue
        folder = process_listing(idx, r)
        print("→ Saved to", folder)
        r['posted'] = 'yes'
        write_listings(LISTINGS_CSV, rows)
        did_any = True
        webbrowser.open('https://www.facebook.com/marketplace/create/item')
        print("Opened FB Marketplace – now run your UI Vision macro and hit Post.")
        time.sleep(5)

    if not did_any:
        print("✅ All listings are already posted.")


if __name__ == "__main__":
    main()
