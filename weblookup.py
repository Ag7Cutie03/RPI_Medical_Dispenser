import re
import time
import requests
from bs4 import BeautifulSoup

# Simple in-memory cache for medicine instructions
MEDICINE_CACHE = {}
CACHE_DURATION = 3600  # Cache for 1 hour

def get_web_instructions(medicine_name):
    """
    Scrape the 'Directions' section from https://www.drugs.com/dosage/{brand_name}.html
    Returns:
    Directions
    > content
    """
    start_time = time.perf_counter()
    try:
        brand_name = medicine_name.split()[0].strip().lower()
        url = f"https://www.drugs.com/dosage/{brand_name}.html"
        print(f"[DEBUG] Drugs.com Dosage URL: {url}")
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch {url} (status {response.status_code})")
            return "No relevant sections found."
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find the 'Directions' heading
        directions_heading = soup.find(lambda tag: tag.name in ['h2', 'h3', 'h4', 'strong', 'b'] and tag.get_text(strip=True).lower() == 'directions')
        if not directions_heading:
            print(f"[BENCHMARK] Drugs.com scraping for '{medicine_name}' took {time.perf_counter() - start_time:.2f} seconds. No relevant sections found.")
            return "No relevant sections found."
        # Collect all sibling <ul>, <ol>, <p>, or text until the next heading
        content = []
        for sib in directions_heading.find_next_siblings():
            sib_name = getattr(sib, 'name', None)
            if sib_name and sib_name.startswith('h'):
                break
            text = sib.get_text(strip=True)
            if text:
                content.append(text)
        if content:
            result = 'Directions\n> ' + '\n> '.join(content)
            print(f"[BENCHMARK] Drugs.com scraping for '{medicine_name}' took {time.perf_counter() - start_time:.2f} seconds.")
            print(f"[WEBSCRAPED INSTRUCTIONS] {result}")
            return result
        else:
            print(f"[BENCHMARK] Drugs.com scraping for '{medicine_name}' took {time.perf_counter() - start_time:.2f} seconds. No relevant sections found.")
            return "No relevant sections found."
    except Exception as e:
        print(f"Error fetching Drugs.com directions: {e}")
        return "No relevant sections found."

def fetch_intake_instructions(medicine_name):
    """
    Fetch medicine instructions using Drugs.com web lookup. Returns instruction string or fallback message if no information is found.
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
    # Always use only the brand name for scraping
    brand_name = medicine_name.split()[0].strip().lower()
    instructions = get_web_instructions(brand_name)
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