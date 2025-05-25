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

def get_product_urls(page):
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

def scrape_all_product_urls():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        base_url = "https://www.madewithnestle.ca/search/products?t=&page="
        start_url = base_url + "0"
        print(f"Loading first page: {start_url}")
        page.goto(start_url, wait_until='domcontentloaded')
        time.sleep(2)

        total_pages = get_total_pages(page)
        if total_pages == 0:
            print("Could not find total pages, defaulting to only first page.")
            total_pages = 0

        total_pages = min(total_pages, 0)  # Limit to 5 pages for now

        all_urls = set()
        for i in range(0, total_pages + 1):
            page_url = base_url + str(i)
            print(f"Scraping page {i+1}/{total_pages+1}: {page_url}")
            page.goto(page_url, wait_until='domcontentloaded')
            time.sleep(1)
            urls = get_product_urls(page)
            print(f"  Found {len(urls)} product URLs on this page.")
            all_urls.update(urls)

        print(f"\nTotal unique product URLs scraped: {len(all_urls)}")
        browser.close()
        return list(all_urls)

def extract_description(page):
    try:
        desc = page.locator('div.product-description p').first.inner_text()
        return desc.strip()
    except:
        try:
            desc = page.locator('div.field--name-field-description p').first.inner_text()
            return desc.strip()
        except:
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
                    return content_div.evaluate("el => el.innerText")
                nextdiv = h2.evaluate_handle("el => el.nextElementSibling")
                if nextdiv:
                    return nextdiv.evaluate("el => el.innerText")
        return None
    except Exception as e:
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
                        return lis
        return extract_accordion_section(page, "Features and Benefits")
    except:
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
            return None

        # Serving size
        try:
            serving_size = page.locator('.coh-container.nutrients-container .coh-container.serving-size').inner_text().strip()
        except Exception:
            serving_size = None

        table_wrapper = page.query_selector('.nutrients-table-wrapper')
        if not table_wrapper:
            return None

        rows = table_wrapper.query_selector_all("div.row-depth-0, div.row-depth-1")
        nutrients = []
        current_main = None

        for row in rows:
            # Label
            label_div = row.query_selector('div.label-column')
            name = label_div.inner_text().strip() if label_div else ""
            # Value and unit (e.g. "250", "mg", "g")
            value = ""
            if row.query_selector('div.first-column .amount-value'):
                value = row.query_selector('div.first-column .amount-value').inner_text().strip()
                # Add extra unit/symbols if present, after the value
                rest = row.query_selector('div.first-column').inner_text().strip()
                rest = rest.replace(value, '', 1).strip()
                if rest:
                    value = value + " " + rest
            # Percent (grab entire column, e.g. "12 %")
            percent = ""
            if row.query_selector('div.second-column .nutrient-value'):
                percent = row.query_selector('div.second-column .nutrient-value').inner_text().strip()
                # Add extra unit/symbols after percent, if present
                percent_rest = row.query_selector('div.second-column').inner_text().strip()
                percent_rest = percent_rest.replace(percent, '', 1).strip()
                if percent_rest:
                    percent = percent + " " + percent_rest

            # Class logic
            row_class = row.get_attribute('class')
            if 'row-depth-0' in row_class:
                if current_main:
                    nutrients.append(current_main)
                current_main = {"name": name, "value": value, "percent": percent, "sub": []}
            elif 'row-depth-1' in row_class and current_main:
                current_main["sub"].append({"name": name, "value": value, "percent": percent})

        if current_main:
            nutrients.append(current_main)

        # Build the paragraph
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
        return "\n".join(lines) if lines else None
    except Exception as e:
        print("Error extracting nutrition info:", e)
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
                        return ingredients
                div = h2.evaluate_handle("el => el.parentElement.querySelector('.sub-ingredients')")
                if div:
                    ingredients = div.evaluate("el => el.innerText")
                    if ingredients:
                        return ingredients
        return extract_accordion_section(page, "Ingredients")
    except:
        return None

def scrape_all_product_details(product_urls):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        for idx, url in enumerate(product_urls):
            print(f"[{idx+1}/{len(product_urls)}] Scraping: {url}")
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=25000)
                time.sleep(1)
            except Exception as e:
                print(f"Failed to load {url}: {e}")
                continue

            product = {"url": url}

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

            print("  Sections found:", list(product.keys()))
            results.append(product)
        browser.close()
    return results

if __name__ == "__main__":
    urls = scrape_all_product_urls()
    print(f"Found {len(urls)} product URLs. Extracting details...\n")
    details = scrape_all_product_details(urls)
    with open("nestle_product_details.json", "w", encoding="utf-8") as f:
        json.dump(details, f, indent=2, ensure_ascii=False)
    print("Saved all product details to 'nestle_product_details.json'")