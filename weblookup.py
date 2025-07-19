try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise ImportError("Playwright is not installed. Please install it with 'pip install playwright' and run 'playwright install'.")
import re
import time

# Simple in-memory cache for medicine instructions
MEDICINE_CACHE = {}
CACHE_DURATION = 3600  # Cache for 1 hour

def get_web_instructions(medicine_name):
    """
    Scrape only the 'Indications/Uses', 'Dosage/Direction for Use', and 'Administration' sections from the MIMS Philippines drug info page for the given medicine.
    Returns a structured summary as a string, formatted as:
    Indications/Uses
    > content
    Dosage/Direction for Use
    > content
    Administration
    > content
    """
    start_time = time.perf_counter()
    try:
        # Use only the brand name (first word) for the MIMS URL
        brand_name = medicine_name.split()[0].strip().lower()
        url_name = brand_name.replace(' ', '-').replace('/', '-')
        url = f"https://www.mims.com/philippines/drug/info/{url_name}"
        print(f"[DEBUG] MIMS URL: {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            # Remove script/style/nav/header/footer via JS
            page.evaluate('''() => {
                for (const tag of ['script', 'style', 'nav', 'header', 'footer']) {
                    document.querySelectorAll(tag).forEach(e => e.remove());
                }
            }''')
            # Find all headings and their following content
            sections = {}
            headings = page.query_selector_all('h1, h2, h3, h4, h5, h6, strong, b')
            for heading in headings:
                title = heading.inner_text().strip().lower()
                if not title or len(title) > 100:
                    continue
                # Only match exact section titles (case-insensitive)
                if title in ['indications/uses', 'dosage/direction for use', 'administration']:
                    sib = heading.evaluate_handle('el => el.nextElementSibling')
                    content = ""
                    if sib:
                        content = sib.evaluate('el => el.innerText').strip()
                    if content and len(content) > 20:
                        sections[title] = content
            browser.close()
            # Format output in the requested style
            output = []
            for key in ['indications/uses', 'dosage/direction for use', 'administration']:
                if key in sections:
                    output.append(f"{key.title().replace('/', '/')}\n> {sections[key]}")
            elapsed = time.perf_counter() - start_time
            if output:
                result = '\n'.join(output)
                print(f"[BENCHMARK] Web scraping for '{medicine_name}' took {elapsed:.2f} seconds.")
                print(f"[WEBSCRAPED INSTRUCTIONS] {result}")
                return result
            else:
                print(f"[BENCHMARK] Web scraping for '{medicine_name}' took {elapsed:.2f} seconds. No relevant sections found.")
                return "No relevant sections found."
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"Error fetching MIMS instructions: {e} (Elapsed: {elapsed:.2f}s)")
    return None

def fetch_intake_instructions(medicine_name):
    """
    Fetch medicine instructions using Playwright-based web lookup. Returns instruction string or fallback message if no information is found.
    Waits 5 seconds before searching to allow servo to finish dispensing.
    """
    time.sleep(5)  # Wait for servo to finish dispensing
    start_time = time.perf_counter()
    current_time = time.time()
    if medicine_name in MEDICINE_CACHE:
        cache_time, cached_instructions = MEDICINE_CACHE[medicine_name]
        if current_time - cache_time < CACHE_DURATION:
            print(f"[BENCHMARK] fetch_intake_instructions for '{medicine_name}' (CACHED) took {time.perf_counter() - start_time:.2f} seconds.")
            print(f"[INSTRUCTIONS] {cached_instructions}")
            return cached_instructions
    instructions = get_web_instructions(medicine_name)
    elapsed = time.perf_counter() - start_time
    if instructions:
        MEDICINE_CACHE[medicine_name] = (current_time, instructions)
        print(f"[BENCHMARK] fetch_intake_instructions for '{medicine_name}' took {elapsed:.2f} seconds.")
        print(f"[INSTRUCTIONS] {instructions}")
        return instructions
    fallback_message = f"Instructions for {medicine_name}: No specific dosage information found online. Please consult your doctor or pharmacist for proper dosage instructions. Always follow your healthcare provider's recommendations."
    MEDICINE_CACHE[medicine_name] = (current_time, fallback_message)
    print(f"[BENCHMARK] fetch_intake_instructions for '{medicine_name}' (FALLBACK) took {elapsed:.2f} seconds.")
    print(f"[INSTRUCTIONS] {fallback_message}")
    return fallback_message

def clear_cache():
    """Clear the medicine instruction cache"""
    global MEDICINE_CACHE
    MEDICINE_CACHE.clear()
    print("Medicine instruction cache cleared")

def get_cache_info():
    """Get information about the cache"""
    return {
        'cache_size': len(MEDICINE_CACHE),
        'cached_medicines': list(MEDICINE_CACHE.keys()),
        'cache_duration': CACHE_DURATION
    } 