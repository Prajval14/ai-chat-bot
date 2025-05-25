from playwright.sync_api import sync_playwright
import json
import re
import time

def get_total_pages(page):
    try:
        last_page_link = page.locator('a[title="Go to last page"]')
        href = last_page_link.get_attribute("href")
        match = re.search(r'page=(\d+)', href)
        if match:
            total_pages = int(match.group(1))
            print(f"Total pages found: {total_pages}")
            return total_pages
    except Exception as e:
        print("Error extracting total pages:", e)
    return 0

def get_recipe_urls(page):
    urls = []
    anchors = page.locator('div.views-field-title a')
    count = anchors.count()
    for i in range(count):
        url = anchors.nth(i).get_attribute('href')
        if url:
            if not url.startswith("http"):
                url = "https://www.madewithnestle.ca" + url
            urls.append(url)
    return urls

def extract_text(page, selector, timeout=3000):
    try:
        return page.locator(selector).first.inner_text(timeout=timeout).strip()
    except:
        return ""

def extract_all_text(page, selector, timeout=3000):
    try:
        return page.eval_on_selector_all(selector, "els => els.map(e => e.innerText.trim())")
    except:
        return []

def extract_tip(page):
    # Look for h3 with text 'Tips' or 'Alternatively', then grab the next p.coh-paragraph
    tip_selectors = ["h3.coh-heading:has-text('Tips')", "h3.coh-heading:has-text('Alternatively')"]
    for selector in tip_selectors:
        try:
            heading = page.locator(selector).first
            if heading:
                # Find first sibling <p> under the same parent or next container
                parent = heading.locator('..')
                # Try to get first paragraph in same parent
                tip = parent.locator('p.coh-paragraph').first.inner_text(timeout=2000).strip()
                if tip:
                    return tip
        except:
            continue
    return ""

def scrape_all_recipe_details():
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
        print(f"Loading first page: {start_url}")
        page.goto(start_url, wait_until='domcontentloaded')
        time.sleep(2)

        total_pages = get_total_pages(page)
        if total_pages == 0:
            print("Could not find total pages, defaulting to only first page.")
            total_pages = 0
        # For testing, only scrape 5 pages max
        total_pages = min(total_pages, 0)  # comment out or set higher for production

        # Collect all recipe URLs
        all_urls = set()
        for i in range(0, total_pages + 1):
            page_url = base_url + str(i)
            print(f"Scraping page {i+1}/{total_pages+1}: {page_url}")
            page.goto(page_url, wait_until='domcontentloaded')
            time.sleep(1)
            urls = get_recipe_urls(page)
            print(f"  Found {len(urls)} recipe URLs on this page.")
            all_urls.update(urls)

        print(f"\nTotal unique recipe URLs scraped: {len(all_urls)}")

        all_data = []
        for idx, url in enumerate(all_urls):
            print(f"\n[{idx+1}/{len(all_urls)}] Visiting: {url}")
            try:
                recipe_page = context.new_page()
                response = recipe_page.goto(url, wait_until='domcontentloaded', timeout=30000)
                print(f"Recipe page status: {response.status}")
                if response.status == 403:
                    print("Got 403 Forbidden on recipe page. Skipping.")
                    recipe_page.close()
                    continue
                time.sleep(2)
            except Exception as e:
                print(f"Error loading recipe page: {e}")
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
            all_data.append(recipe_data)
            recipe_page.close()

        browser.close()
        return all_data

if __name__ == "__main__":
    data = scrape_all_recipe_details()
    with open("nestle_recipes.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\nDone! Data saved as 'nestle_recipes.json' in root directory.")