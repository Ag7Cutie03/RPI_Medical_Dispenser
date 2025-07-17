import requests
from bs4 import BeautifulSoup
import re
import time
import os
import openai
import google.generativeai as genai

# Simple in-memory cache for medicine instructions
MEDICINE_CACHE = {}
CACHE_DURATION = 3600  # Cache for 1 hour

GEMINI_API_KEY = "AIzaSyDUElsMrbJ8ye3L5YFPOB2GNC9FC-yRlLA"
genai.configure(api_key=GEMINI_API_KEY)

def get_mims_instructions(medicine_name):
    """
    Get Administration and Dosage/Direction for Use from MIMS Philippines website for the given medicine brand.
    Returns a string with both sections, or just one if only one is found.
    """
    try:
        # Clean medicine name for search
        clean_name = re.sub(r'\d+mg|\d+ml|\d+mg/\d+ml', '', medicine_name).strip().lower()
        url_name = clean_name.replace(' ', '-').replace('/', '-')
        url = f"https://www.mims.com/philippines/drug/info/{url_name}?type=full"
        print(f"Fetching MIMS info from: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        def extract_section(section_title):
            # Find the heading for the section (MIMS may use <h3> or <h4> for sections in full view)
            heading = soup.find(lambda tag: tag.name in ['h1','h2','h3','h4','h5','h6'] and section_title.lower() in tag.get_text().lower())
            if not heading:
                # Try to find section by strong/bold text (sometimes used in MIMS)
                heading = soup.find(lambda tag: tag.name in ['strong', 'b'] and section_title.lower() in tag.get_text().lower())
            if not heading:
                return None
            # Collect all text until the next heading or strong/bold section
            section_text = ""
            current = heading.find_next_sibling()
            while current and not (current.name in ['h1','h2','h3','h4','h5','h6'] or (current.name in ['strong', 'b'] and current.get_text().strip())):
                if current.name in ['p', 'div', 'span', 'li'] and current.get_text().strip():
                    section_text += current.get_text().strip() + " "
                current = current.find_next_sibling()
            return section_text.strip() if section_text else None
        
        admin_text = extract_section('Administration')
        dosage_text = extract_section('Dosage/Direction for Use')
        
        result = []
        if admin_text:
            result.append(f"Administration: {admin_text}")
        if dosage_text:
            result.append(f"Dosage/Direction for Use: {dosage_text}")
        if result:
            return f"Instructions for {medicine_name}:\n" + "\n".join(result)
        else:
            print(f"No Administration or Dosage/Direction for Use found for {medicine_name}")
    except requests.exceptions.Timeout:
        print(f"Timeout fetching MIMS info for {medicine_name}")
    except requests.exceptions.RequestException as e:
        print(f"Request error fetching MIMS info for {medicine_name}: {e}")
    except Exception as e:
        print(f"Error fetching MIMS info for {medicine_name}: {e}")
    return None

def get_web_instructions(medicine_name):
    """
    Get medicine instructions from web sources.
    Returns instructions string or None if not found.
    """
    try:
        # Clean medicine name for search
        clean_name = re.sub(r'\d+mg|\d+ml|\d+mg/\d+ml', '', medicine_name).strip()
        search_query = f"{clean_name} medication instructions dosage how to take"
        
        # Use Google search with better headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Try multiple sources for better results
        sources = [
            f"https://www.drugs.com/search.php?searchterm={search_query.replace(' ', '+')}",
            f"https://www.webmd.com/search/search_results/default.aspx?query={search_query.replace(' ', '%20')}",
            f"https://www.rxlist.com/search/{search_query.replace(' ', '-')}",
            f"https://www.medicinenet.com/search/search_results/default.aspx?query={search_query.replace(' ', '%20')}",
            f"https://www.mayoclinic.org/search/search-results?q={search_query.replace(' ', '%20')}",
            f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        ]
        
        for source in sources:
            try:
                response = requests.get(source, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract relevant text content
                text_content = ""
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                
                # Get text from paragraphs and divs
                for tag in soup.find_all(['p', 'div', 'span', 'li']):
                    if tag.get_text().strip():
                        text_content += tag.get_text().strip() + " "
                
                # Look for instruction-related keywords
                instruction_keywords = [
                    'take with', 'take on empty stomach', 'take with food',
                    'dosage', 'instructions', 'how to take', 'directions',
                    'every', 'hours', 'daily', 'twice', 'three times',
                    'before meals', 'after meals', 'with meals', 'recommended',
                    'prescribed', 'consult', 'doctor', 'pharmacist'
                ]
                
                # Find sentences containing instruction keywords
                sentences = re.split(r'[.!?]', text_content)
                instruction_sentences = []
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) > 15 and len(sentence) < 200 and any(keyword in sentence.lower() for keyword in instruction_keywords):
                        # Clean up the sentence
                        sentence = re.sub(r'\s+', ' ', sentence)  # Remove extra whitespace
                        instruction_sentences.append(sentence)
                
                if instruction_sentences:
                    # Take first 2-3 relevant sentences
                    relevant_instructions = '. '.join(instruction_sentences[:3])
                    return relevant_instructions
                
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException as e:
                continue
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"Error fetching web instructions: {e}")
    
    return None

def fetch_intake_instructions(medicine_name):
    """
    Fetch medicine instructions using Google Gemini API. Returns instruction string or fallback message if no information is found.
    Waits 5 seconds before searching to allow servo to finish dispensing.
    """
    time.sleep(5)  # Wait for servo to finish dispensing
    # Check cache first
    current_time = time.time()
    if medicine_name in MEDICINE_CACHE:
        cache_time, cached_instructions = MEDICINE_CACHE[medicine_name]
        if current_time - cache_time < CACHE_DURATION:
            return cached_instructions
    prompt = (
        "You are a doctor talking to me as a patient. I want clear, simple instructions in layman's terms with the following format:\n"
        "- Take 1 [tablet/capsule] by mouth every [X] hours\n"
        "- Do not take more than [Y] [tablets/capsules] in 24 hours (this prevents any overdose) ([source1], [source2])\n"
        "- If you miss a dose, don’t double up—just take the next dose at the regular time\n"
        "- You can take it with or without food\n\n"
        f"Now give me instructions for **{medicine_name}** with the correct values."
    )
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        answer = response.text.strip()
        if answer:
            MEDICINE_CACHE[medicine_name] = (current_time, answer)
            return answer
    except Exception as e:
        print(f"Gemini API error: {e}")
        fallback_message = f"Instructions for {medicine_name}: No specific dosage information found online. Please consult your doctor or pharmacist for proper dosage instructions. Always follow your healthcare provider's recommendations."
        MEDICINE_CACHE[medicine_name] = (current_time, fallback_message)
        return fallback_message

def test_mims(medicine_name):
    """Test route to manually test MIMS scraping for a specific medicine"""
    try:
        instructions = get_mims_instructions(medicine_name)
        if instructions:
            return {
                'status': 'success',
                'medicine': medicine_name,
                'instructions': instructions,
                'source': 'MIMS Philippines'
            }
        else:
            return {
                'status': 'not_found',
                'medicine': medicine_name,
                'message': 'No instructions found on MIMS'
            }
    except Exception as e:
        return {
            'status': 'error',
            'medicine': medicine_name,
            'error': str(e)
        }

def test_all_sources(medicine_name):
    """Test route to check all web sources for a specific medicine"""
    results = {
        'medicine': medicine_name,
        'sources': {}
    }
    
    # Test MIMS first
    try:
        mims_instructions = get_mims_instructions(medicine_name)
        results['sources']['mims'] = {
            'status': 'success' if mims_instructions else 'not_found',
            'instructions': mims_instructions
        }
    except Exception as e:
        results['sources']['mims'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Test other web sources
    try:
        web_instructions = get_web_instructions(medicine_name)
        results['sources']['web'] = {
            'status': 'success' if web_instructions else 'not_found',
            'instructions': web_instructions
        }
    except Exception as e:
        results['sources']['web'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Test final fetch function
    try:
        final_instructions = fetch_intake_instructions(medicine_name)
        results['final_result'] = {
            'status': 'success',
            'instructions': final_instructions
        }
    except Exception as e:
        results['final_result'] = {
            'status': 'error',
            'error': str(e)
        }
    
    return results

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