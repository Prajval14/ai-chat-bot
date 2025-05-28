from playwright.sync_api import sync_playwright
import json
import re
import time
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# --- Import centralized logger ---
from functions.log_utils import get_blob_logger
logger = get_blob_logger(__name__)

load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob="nestle_products.txt")

def get_total_pages(page):
    try:
        last_page_link = page.locator('a[title="Go to last page"]')
        href = last_page_link.get_attribute("href")
        match = re.search(r'page=(\d+)', href)
        if match:
            total_pages = int(match.group(1))
            logger.info(f"Detected {total_pages} total pages of products.")
            return total_pages
    except Exception as e:
        logger.error(f"Failed to get total pages: {e}")
    return 0

def get_product_urls(page):
    products = []
    anchors = page.locator('div.views-field-title a')
    count = anchors.count()
    logger.info(f"Found {count} product anchors on the page.")
    for i in range(count):
        a = anchors.nth(i)
        url = a.get_attribute('href')
        heading = a.inner_text().strip()
        if url and heading:
            if not url.startswith("http"):
                url = "https://www.madewithnestle.ca" + url
            products.append({"url": url, "heading": heading})
    logger.info(f"Extracted {len(products)} products from page.")
    return products

def scrape_all_product_urls():
    logger.info("Starting product URL scraping...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        base_url = "https://www.madewithnestle.ca/search/products?t=&page="
        start_url = base_url + "0"
        logger.info(f"Navigating to first products page: {start_url}")
        page.goto(start_url, wait_until='domcontentloaded')
        time.sleep(2)

        total_pages = get_total_pages(page)
        if total_pages == 0:
            logger.warning("Could not determine total pages, defaulting to 0.")
            total_pages = 0

        total_pages = min(total_pages, 0)  # Looks like this always sets to 0; probably you want "total_pages, 20" or similar

        all_products = []
        for i in range(0, total_pages + 1):
            page_url = base_url + str(i)
            logger.info(f"Scraping page {i}: {page_url}")
            page.goto(page_url, wait_until='domcontentloaded')
            time.sleep(1)
            products = get_product_urls(page)
            all_products.extend(products)
        browser.close()
        logger.info(f"Total products collected: {len(all_products)}")
        return all_products

def extract_description(page):
    try:
        desc = page.locator('div.product-description p').first.inner_text()
        logger.info("Extracted product description.")
        return desc.strip()
    except Exception:
        try:
            desc = page.locator('div.field--name-field-description p').first.inner_text()
            logger.info("Extracted fallback product description.")
            return desc.strip()
        except Exception:
            logger.warning("Failed to extract product description.")
            return None

def extract_accordion_section(page, section_keyword):
    try:
        h2s = page.locator('h2.coh-heading')
        for i in range(h2s.count()):
            h2 = h2s.nth(i)
            text = h2.inner_text().strip().lower()
            if section_keyword.lower() in text:
                parent = h2.evaluate_handle("el => el.parentElement.parentElement")
                content_div = parent.evaluate_handle("el => el.querySelector('.coh-accordion-tabs-content.is-active')")
                if content_div:
                    logger.info(f"Extracted accordion section '{section_keyword}' from active content.")
                    return content_div.evaluate("el => el.innerText")
                nextdiv = h2.evaluate_handle("el => el.nextElementSibling")
                if nextdiv:
                    logger.info(f"Extracted accordion section '{section_keyword}' from next sibling.")
                    return nextdiv.evaluate("el => el.innerText")
        logger.warning(f"Accordion section '{section_keyword}' not found.")
        return None
    except Exception as e:
        logger.error(f"Error extracting accordion section '{section_keyword}': {e}")
        return None

def extract_features_and_benefits(page):
    try:
        uls = page.locator('h2.coh-heading span.coh-inline-element')
        for i in range(uls.count()):
            el = uls.nth(i)
            text = el.inner_text().strip().lower()
            if 'features and benefits' in text:
                h2 = el.evaluate_handle("el => el.closest('h2')")
                nextul = h2.evaluate_handle("el => el.parentElement.querySelector('ul')")
                if nextul:
                    lis = nextul.evaluate("el => Array.from(el.querySelectorAll('li'), li => li.innerText)")
                    if lis:
                        logger.info("Extracted features and benefits as list.")
                        return lis
        logger.warning("Features and benefits list not found; trying fallback.")
        return extract_accordion_section(page, "Features and Benefits")
    except Exception as e:
        logger.error(f"Error extracting features and benefits: {e}")
        return None

def extract_nutrition_info(page):
    try:
        panels = page.locator('h2.coh-heading span.coh-inline-element')
        nutrition_panel = None
        for i in range(panels.count()):
            el = panels.nth(i)
            text = el.inner_text().strip().lower()
            if 'nutrition information' in text:
                h2 = el.evaluate_handle("el => el.closest('h2')")
                parent = h2.evaluate_handle("el => el.parentElement.parentElement")
                nutrition_panel = parent

        if not nutrition_panel:
            logger.warning("Nutrition information section not found.")
            return None

        try:
            serving_size = page.locator('.coh-container.nutrients-container .coh-container.serving-size').inner_text().strip()
        except Exception:
            serving_size = None

        table_wrapper = page.query_selector('.nutrients-table-wrapper')
        if not table_wrapper:
            logger.warning("Nutrition table not found.")
            return None

        rows = table_wrapper.query_selector_all("div.row-depth-0, div.row-depth-1")
        nutrients = []
        current_main = None

        for row in rows:
            label_div = row.query_selector('div.label-column')
            name = label_div.inner_text().strip() if label_div else ""
            value = ""
            if row.query_selector('div.first-column .amount-value'):
                value = row.query_selector('div.first-column .amount-value').inner_text().strip()
                rest = row.query_selector('div.first-column').inner_text().strip()
                rest = rest.replace(value, '', 1).strip()
                if rest:
                    value = value + " " + rest
            percent = ""
            if row.query_selector('div.second-column .nutrient-value'):
                percent = row.query_selector('div.second-column .nutrient-value').inner_text().strip()
                percent_rest = row.query_selector('div.second-column').inner_text().strip()
                percent_rest = percent_rest.replace(percent, '', 1).strip()
                if percent_rest:
                    percent = percent + " " + percent_rest

            row_class = row.get_attribute('class')
            if 'row-depth-0' in row_class:
                if current_main:
                    nutrients.append(current_main)
                current_main = {"name": name, "value": value, "percent": percent, "sub": []}
            elif 'row-depth-1' in row_class and current_main:
                current_main["sub"].append({"name": name, "value": value, "percent": percent})

        if current_main:
            nutrients.append(current_main)

        lines = []
        if serving_size:
            lines.append(f"Serving size: {serving_size}")
        for n in nutrients:
            main_str = f"{n['name']}: {n['value']}"
            if n['percent']:
                main_str += f" ({n['percent']})"
            if n["sub"]:
                subparts = []
                for s in n["sub"]:
                    part = f"{s['name']}: {s['value']}"
                    if s['percent']:
                        part += f" ({s['percent']})"
                    subparts.append(part)
                main_str += f" [Sub-nutrients: " + "; ".join(subparts) + "]"
            lines.append(main_str)
        logger.info("Extracted nutrition information.")
        return "\n".join(lines) if lines else None
    except Exception as e:
        logger.error(f"Error extracting nutrition info: {e}")
        return None

def extract_ingredients(page):
    try:
        panels = page.locator('h2.coh-heading span.coh-inline-element')
        for i in range(panels.count()):
            el = panels.nth(i)
            text = el.inner_text().strip().lower()
            if 'ingredients' == text:
                h2 = el.evaluate_handle("el => el.closest('h2')")
                ptag = h2.evaluate_handle("el => el.parentElement.querySelector('p')")
                if ptag:
                    ingredients = ptag.evaluate("el => el.innerText")
                    if ingredients:
                        logger.info("Extracted ingredients (p tag).")
                        return ingredients
                div = h2.evaluate_handle("el => el.parentElement.querySelector('.sub-ingredients')")
                if div:
                    ingredients = div.evaluate("el => el.innerText")
                    if ingredients:
                        logger.info("Extracted ingredients (sub-ingredients div).")
                        return ingredients
        logger.warning("Ingredients section not found; trying fallback.")
        return extract_accordion_section(page, "Ingredients")
    except Exception as e:
        logger.error(f"Error extracting ingredients: {e}")
        return None

def scrape_all_product_details(product_entries):
    logger.info("Starting detailed product scraping...")
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        for idx, prod in enumerate(product_entries):
            url = prod["url"]
            heading = prod["heading"]
            logger.info(f"Scraping product {idx + 1}/{len(product_entries)}: {heading} | {url}")
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=25000)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Failed to load product page {url}: {e}")
                continue

            product = {"url": url, "heading": heading}

            desc = extract_description(page)
            if desc:
                product['description'] = desc
            feats = extract_features_and_benefits(page)
            if feats:
                product['features_and_benefits'] = feats
            nutri = extract_nutrition_info(page)
            if nutri:
                product['nutrition_information'] = nutri
            ingred = extract_ingredients(page)
            if ingred:
                product['ingredients'] = ingred

            logger.info(f"Scraped details for product: {heading}")
            results.append(product)
        browser.close()
    logger.info(f"Completed scraping details for {len(results)} products.")
    return results

def product_to_paragraph(product):
    lines = []
    if product.get('heading'):
        lines.append(f"Product: {product['heading']}")
    if product.get('url'):
        lines.append(f"URL: {product['url']}")
    if product.get('description'):
        lines.append(f"Description: {product['description']}")
    if product.get('features_and_benefits'):
        feats = product['features_and_benefits']
        if isinstance(feats, list):
            lines.append(f"Features and Benefits: {', '.join(feats)}")
        else:
            lines.append(f"Features and Benefits: {feats}")
    if product.get('nutrition_information'):
        lines.append(f"Nutrition Information: {product['nutrition_information']}")
    if product.get('ingredients'):
        lines.append(f"Ingredients: {product['ingredients']}")
    return "\n".join(lines) + "\n\n"

def main():
    try:
        logger.info("Web scraping main() started.")
        products = scrape_all_product_urls()
        logger.info(f"Got {len(products)} products for details scraping. Limiting to 3 for demo.")
        products = products[:3]
        details = scrape_all_product_details(products)
        logger.info(f"Formatting scraped products to text paragraphs.")
        paragraphs = [product_to_paragraph(prod) for prod in details]
        full_text = "".join(paragraphs)
        logger.info(f"Uploading full product text to blob 'nestle_products.txt'.")
        blob_client.upload_blob(full_text, overwrite=True)
        logger.info("Scraping and upload completed successfully.")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()