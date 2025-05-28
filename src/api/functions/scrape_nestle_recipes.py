from playwright.sync_api import sync_playwright
import re
import time
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# --- Centralized logging ---
from functions.log_utils import get_blob_logger
logger = get_blob_logger(__name__)

load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob="nestle_recipes.txt")

def get_total_pages(page):
    try:
        last_page_link = page.locator('a[title="Go to last page"]')
        href = last_page_link.get_attribute("href")
        match = re.search(r'page=(\d+)', href)
        if match:
            total_pages = int(match.group(1))
            logger.info(f"Detected {total_pages} total pages for recipes.")
            return total_pages
    except Exception as e:
        logger.error(f"Error determining total recipe pages: {e}")
    return 0

def get_recipe_urls(page):
    urls = []
    anchors = page.locator('div.views-field-title a')
    count = anchors.count()
    logger.info(f"Found {count} recipe anchors on current page.")
    for i in range(count):
        url = anchors.nth(i).get_attribute('href')
        if url:
            if not url.startswith("http"):
                url = "https://www.madewithnestle.ca" + url
            urls.append(url)
    logger.info(f"Extracted {len(urls)} recipe URLs from page.")
    return urls

def extract_text(page, selector, timeout=3000):
    try:
        val = page.locator(selector).first.inner_text(timeout=timeout).strip()
        logger.info(f"Extracted text from selector '{selector}'.")
        return val
    except Exception as e:
        logger.warning(f"Failed to extract text for selector '{selector}': {e}")
        return ""

def extract_all_text(page, selector, timeout=3000):
    try:
        vals = page.eval_on_selector_all(selector, "els => els.map(e => e.innerText.trim())")
        logger.info(f"Extracted {len(vals)} entries from selector '{selector}'.")
        return vals
    except Exception as e:
        logger.warning(f"Failed to extract all text for selector '{selector}': {e}")
        return []

def extract_tip(page):
    tip_selectors = ["h3.coh-heading:has-text('Tips')", "h3.coh-heading:has-text('Alternatively')"]
    for selector in tip_selectors:
        try:
            heading = page.locator(selector).first
            if heading:
                parent = heading.locator('..')
                tip = parent.locator('p.coh-paragraph').first.inner_text(timeout=2000).strip()
                if tip:
                    logger.info("Extracted tip for recipe.")
                    return tip
        except Exception:
            continue
    logger.warning("No tip found for recipe.")
    return ""

def collect_recipe_urls():
    logger.info("Starting recipe URL collection...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale='en-US'
        )
        page = context.new_page()
        base_url = "https://www.madewithnestle.ca/search/recipes?t=&page="
        start_url = base_url + "0"
        logger.info(f"Visiting first recipe search page: {start_url}")
        page.goto(start_url, wait_until='domcontentloaded')
        time.sleep(2)
        total_pages = get_total_pages(page)
        if total_pages == 0:
            logger.warning("Could not determine total recipe pages, defaulting to 0.")
            total_pages = 0
        total_pages = min(total_pages, 0)  # Consider changing this if you want more pages
        all_urls = []
        for i in range(0, total_pages + 1):
            page_url = base_url + str(i)
            logger.info(f"Scraping recipe listing page {i}: {page_url}")
            page.goto(page_url, wait_until='domcontentloaded')
            time.sleep(1)
            urls = get_recipe_urls(page)
            all_urls.extend(urls)
        browser.close()
        logger.info(f"Total recipe URLs collected: {len(all_urls)}")
        return all_urls

def scrape_recipe_details(urls):
    logger.info("Starting recipe details scraping...")
    data = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale='en-US'
        )
        for idx, url in enumerate(urls):
            try:
                recipe_page = context.new_page()
                logger.info(f"Scraping recipe {idx+1}/{len(urls)}: {url}")
                response = recipe_page.goto(url, wait_until='domcontentloaded', timeout=30000)
                if hasattr(response, 'status') and response.status == 403:
                    logger.error(f"Access forbidden (403) for recipe URL: {url}")
                    recipe_page.close()
                    continue
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to load recipe page {url}: {e}")
                continue

            title = extract_text(recipe_page, 'h1.coh-heading.global-recipe-title')
            description = extract_text(recipe_page, '.coh-paragraph')
            prep_time = extract_text(recipe_page, '.prep-time .prep-time-value')
            cook_time = extract_text(recipe_page, '.cook-time .cook-time-value')
            servings = extract_text(recipe_page, '.serving .serving-value')
            skill_level = extract_text(recipe_page, '.skill-level .skill-level-value')
            ingredients = extract_all_text(recipe_page, "div.field.field--name-field-ingredient-fullname.field__item")
            instructions = extract_all_text(recipe_page, ".coh-container.coh-ce-767596f7 .coh-paragraph")
            if not instructions:
                instructions = extract_all_text(recipe_page, ".coh-paragraph")
            tags = extract_all_text(recipe_page, ".field--name-field-recipe-tag-free-tag .field__item a")
            tip = extract_tip(recipe_page)
            recipe_data = {
                "title": title,
                "link": url,
                "description": description,
                "prep_time": prep_time,
                "cook_time": cook_time,
                "servings": servings,
                "skill_level": skill_level,
                "ingredients": ingredients,
                "instructions": instructions,
                "tags": tags,
                "tip": tip
            }
            logger.info(f"Scraped details for recipe: {title if title else url}")
            data.append(recipe_data)
            recipe_page.close()
        browser.close()
    logger.info(f"Scraped details for {len(data)} recipes.")
    return data

def recipe_to_paragraph(recipe):
    lines = []
    if recipe.get('title'):
        lines.append(f"Title: {recipe['title']}")
    if recipe.get('link'):
        lines.append(f"URL: {recipe['link']}")
    if recipe.get('description'):
        lines.append(f"Description: {recipe['description']}")
    if recipe.get('prep_time'):
        lines.append(f"Prep Time: {recipe['prep_time']}")
    if recipe.get('cook_time'):
        lines.append(f"Cook Time: {recipe['cook_time']}")
    if recipe.get('servings'):
        lines.append(f"Servings: {recipe['servings']}")
    if recipe.get('skill_level'):
        lines.append(f"Skill Level: {recipe['skill_level']}")
    if recipe.get('ingredients'):
        lines.append("Ingredients:")
        for ing in recipe['ingredients']:
            lines.append(f" - {ing}")
    if recipe.get('instructions'):
        lines.append("Instructions:")
        for idx, step in enumerate(recipe['instructions'], 1):
            lines.append(f"  {idx}. {step}")
    if recipe.get('tags'):
        lines.append("Tags: " + ", ".join(recipe['tags']))
    if recipe.get('tip'):
        lines.append(f"Tip: {recipe['tip']}")
    return "\n".join(lines) + "\n\n"

def main():
    try:
        logger.info("Recipe scraping main() started.")
        all_urls = collect_recipe_urls()
        logger.info(f"Collected {len(all_urls)} recipe URLs. Limiting to 3 for demo.")
        urls = all_urls[:3]
        recipes = scrape_recipe_details(urls)
        logger.info(f"Formatting scraped recipes to text paragraphs.")
        paragraphs = [recipe_to_paragraph(recipe) for recipe in recipes]
        full_text = "".join(paragraphs)
        logger.info("Uploading recipes text to blob 'nestle_recipes.txt'.")
        blob_client.upload_blob(full_text, overwrite=True)
        logger.info("Recipe scraping and upload completed successfully.")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()