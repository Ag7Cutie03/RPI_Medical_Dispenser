import requests
import re
import time
import json
from urllib.parse import quote_plus, urlencode
import urllib3
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings('ignore')

# Import text-to-speech functionality
import subprocess
import os

# Disable SSL warnings for web scraping
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def speak_text(text):
    """
    Convert the given text to speech using piper-tts (high-quality neural TTS).
    Works with audio jack, Bluetooth, or any audio output on Raspberry Pi.
    Args:
        text (str): The text to be spoken aloud.
    """
    try:
        temp_file = "/tmp/speech.wav"
        subprocess.run(['piper', '--model', 'en_US-amy-low.onnx', '--output_file', temp_file], 
                      input=text.encode(), check=True)
        
        # Play the generated audio file
        subprocess.run(['aplay', temp_file], check=True)
        
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    except subprocess.CalledProcessError as e:
        print(f"Error with piper-tts: {e}")
    except FileNotFoundError:
        print("piper-tts not found. Please install piper-tts first.")
        print("Installation: pip install piper-tts")
        print("Or try: pip install piper-tts[onnx]")

class MedicineLookup:
    """Comprehensive medicine lookup system for multiple sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = 10
        
    def search_mims(self, medicine_name):
        """Search MIMS (Malaysian Index of Medical Specialties) for drug information"""
        try:
            # Clean medicine name
            clean_name = self._clean_medicine_name(medicine_name)
            
            # MIMS search URL
            search_url = f"https://www.mims.com/malaysia/search?q={quote_plus(clean_name)}"
            
            print(f"Searching MIMS for: {clean_name}")
            response = self.session.get(search_url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for drug information in MIMS format
                drug_info = self._extract_mims_info(soup, clean_name)
                if drug_info:
                    return drug_info
                    
            return None
            
        except Exception as e:
            print(f"Error searching MIMS: {e}")
            return None
    
    def search_drugs_com(self, medicine_name):
        """Search Drugs.com for comprehensive drug information"""
        try:
            clean_name = self._clean_medicine_name(medicine_name)
            
            # Drugs.com search URL
            search_url = f"https://www.drugs.com/search.php?searchterm={quote_plus(clean_name)}"
            
            print(f"Searching Drugs.com for: {clean_name}")
            response = self.session.get(search_url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for drug information
                drug_info = self._extract_drugs_com_info(soup, clean_name)
                if drug_info:
                    return drug_info
                    
            return None
            
        except Exception as e:
            print(f"Error searching Drugs.com: {e}")
            return None
    
    def search_wikipedia(self, medicine_name):
        """Search Wikipedia for general drug information"""
        try:
            clean_name = self._clean_medicine_name(medicine_name)
            
            # Wikipedia API search
            api_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
            page_url = f"{api_url}{quote_plus(clean_name)}"
            
            print(f"Searching Wikipedia for: {clean_name}")
            response = self.session.get(page_url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if 'extract' in data:
                    return {
                        'source': 'Wikipedia',
                        'name': clean_name,
                        'description': data['extract'][:500] + "...",
                        'dosage': self._extract_dosage_from_text(data['extract']),
                        'url': data.get('content_urls', {}).get('desktop', {}).get('page', '')
                    }
                    
            return None
            
        except Exception as e:
            print(f"Error searching Wikipedia: {e}")
            return None
    
    def search_rxlist(self, medicine_name):
        """Search RxList for drug information"""
        try:
            clean_name = self._clean_medicine_name(medicine_name)
            
            # RxList search URL
            search_url = f"https://www.rxlist.com/search/{quote_plus(clean_name)}"
            
            print(f"Searching RxList for: {clean_name}")
            response = self.session.get(search_url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for drug information
                drug_info = self._extract_rxlist_info(soup, clean_name)
                if drug_info:
                    return drug_info
                    
            return None
            
        except Exception as e:
            print(f"Error searching RxList: {e}")
            return None
    
    def _clean_medicine_name(self, medicine_name):
        """Clean and standardize medicine name for searching"""
        if not medicine_name:
            return ""
        
        # Store original name for dosage extraction
        original_name = medicine_name
        
        # Remove common dosage suffixes
        name = medicine_name.lower().strip()
        name = re.sub(r'\s+\d+mg\b', '', name)
        name = re.sub(r'\s+\d+g\b', '', name)
        name = re.sub(r'\s+\d+ml\b', '', name)
        name = re.sub(r'\s+\d+%', '', name)
        
        # Remove common words that might interfere with search
        name = re.sub(r'\b(tablet|capsule|injection|suspension|syrup|cream|gel|ointment)\b', '', name)
        
        # Clean up extra spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name.title()
    
    def _extract_dosage_from_text(self, text):
        """Extract dosage information from text"""
        dosage_info = []
        
        # Common dosage patterns
        dosage_patterns = [
            r'(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|IU|units?)\b',  # 500mg, 1g, 10ml
            r'(\d+(?:\.\d+)?)\s*(milligram|gram|milliliter|microgram)s?\b',  # full words
            r'(\d+(?:\.\d+)?)\s*(tablet|capsule|pill|dose)s?\b',  # tablets/capsules
            r'(\d+(?:\.\d+)?)\s*(times?|x)\s*(daily|per day|a day)',  # frequency
            r'(\d+(?:\.\d+)?)\s*(hour|hr)s?\b',  # timing
        ]
        
        for pattern in dosage_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                dosage_info.append(match.group(0))
        
        # Remove duplicates and limit results
        unique_dosages = list(set(dosage_info))[:5]  # Limit to 5 unique dosages
        
        return unique_dosages if unique_dosages else None
    
    def _extract_mims_info(self, soup, medicine_name):
        """Extract drug information from MIMS search results"""
        try:
            # Look for drug cards or search results
            drug_cards = soup.find_all('div', class_=re.compile(r'drug|medicine|product'))
            
            for card in drug_cards:
                # Look for medicine name
                name_elem = card.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
                if name_elem and medicine_name.lower() in name_elem.get_text().lower():
                    # Extract description
                    desc_elem = card.find(['p', 'div', 'span'])
                    if desc_elem:
                        description = desc_elem.get_text().strip()
                        if len(description) > 50:  # Ensure we have meaningful content
                            # Extract dosage information
                            dosage = self._extract_dosage_from_text(description)
                            
                            return {
                                'source': 'MIMS',
                                'name': medicine_name,
                                'description': description[:500] + "..." if len(description) > 500 else description,
                                'dosage': dosage,
                                'url': 'https://www.mims.com/malaysia'
                            }
            
            return None
            
        except Exception as e:
            print(f"Error extracting MIMS info: {e}")
            return None
    
    def _extract_drugs_com_info(self, soup, medicine_name):
        """Extract drug information from Drugs.com search results"""
        try:
            # Look for drug information sections
            drug_sections = soup.find_all(['div', 'section'], class_=re.compile(r'drug|medicine|info'))
            
            for section in drug_sections:
                # Look for medicine name
                name_elem = section.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
                if name_elem and medicine_name.lower() in name_elem.get_text().lower():
                    # Extract description
                    desc_elem = section.find(['p', 'div', 'span'])
                    if desc_elem:
                        description = desc_elem.get_text().strip()
                        if len(description) > 50:
                            # Extract dosage information
                            dosage = self._extract_dosage_from_text(description)
                            
                            return {
                                'source': 'Drugs.com',
                                'name': medicine_name,
                                'description': description[:500] + "..." if len(description) > 500 else description,
                                'dosage': dosage,
                                'url': 'https://www.drugs.com'
                            }
            
            return None
            
        except Exception as e:
            print(f"Error extracting Drugs.com info: {e}")
            return None
    
    def _extract_rxlist_info(self, soup, medicine_name):
        """Extract drug information from RxList search results"""
        try:
            # Look for drug information sections
            drug_sections = soup.find_all(['div', 'section'], class_=re.compile(r'drug|medicine|info'))
            
            for section in drug_sections:
                # Look for medicine name
                name_elem = section.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
                if name_elem and medicine_name.lower() in name_elem.get_text().lower():
                    # Extract description
                    desc_elem = section.find(['p', 'div', 'span'])
                    if desc_elem:
                        description = desc_elem.get_text().strip()
                        if len(description) > 50:
                            # Extract dosage information
                            dosage = self._extract_dosage_from_text(description)
                            
                            return {
                                'source': 'RxList',
                                'name': medicine_name,
                                'description': description[:500] + "..." if len(description) > 500 else description,
                                'dosage': dosage,
                                'url': 'https://www.rxlist.com'
                            }
            
            return None
            
        except Exception as e:
            print(f"Error extracting RxList info: {e}")
            return None
    
    def get_comprehensive_info(self, medicine_name):
        """Get comprehensive drug information from multiple sources"""
        if not medicine_name:
            return "No medicine name provided."
        
        print(f"Starting comprehensive search for: {medicine_name}")
        
        # Try multiple sources in order of preference
        sources = [
            ('MIMS', self.search_mims),
            ('Drugs.com', self.search_drugs_com),
            ('RxList', self.search_rxlist),
            ('Wikipedia', self.search_wikipedia)
        ]
        
        for source_name, search_func in sources:
            try:
                result = search_func(medicine_name)
                if result:
                    print(f"✓ Found information from {source_name}")
                    return result
                else:
                    print(f"✗ No information found from {source_name}")
            except Exception as e:
                print(f"✗ Error with {source_name}: {e}")
                continue
        
        # If no information found, return a generic response
        return {
            'source': 'System',
            'name': medicine_name,
            'description': f"Information for {medicine_name} not found in our databases. Please consult your healthcare provider or pharmacist for accurate information.",
            'dosage': None,
            'url': ''
        }

# Global instance for easy access
medicine_lookup = MedicineLookup()

def get_directions_from_drugs_com(medicine_name):
    """Legacy function for backward compatibility"""
    result = medicine_lookup.get_comprehensive_info(medicine_name)
    if isinstance(result, dict):
        dosage_text = ""
        if result.get('dosage'):
            dosage_text = f"\n\nDosage Information:\n" + "\n".join(f"• {d}" for d in result['dosage'])
        
        return f"{result['description']}{dosage_text}\n\nSource: {result['source']}"
    return result

def get_directions_and_speak(medicine_name):
    """Get drug information and speak it aloud using text-to-speech"""
    result = medicine_lookup.get_comprehensive_info(medicine_name)
    
    if isinstance(result, dict):
        # Format for text-to-speech
        speech_text = f"Information for {result['name']}. {result['description']}"
        
        # Add dosage information if available
        if result.get('dosage'):
            dosage_text = f" Dosage information includes: {', '.join(result['dosage'][:3])}."
            speech_text += dosage_text
        
        # Add source information
        if result['source'] != 'System':
            speech_text += f" This information was obtained from {result['source']}."
        
        # Speak the information aloud
        print(f"Speaking medicine information: {speech_text[:100]}...")
        speak_text(speech_text)
        
        return speech_text
    else:
        # If no structured result, speak the error message
        error_text = f"Sorry, I could not find information for {medicine_name}. Please consult your healthcare provider."
        print(f"Speaking error message: {error_text}")
        speak_text(error_text)
        return result

def test_medicine_lookup(medicine_name):
    """Test function to verify medicine lookup functionality"""
    print(f"Testing medicine lookup for: {medicine_name}")
    print("=" * 50)
    
    result = medicine_lookup.get_comprehensive_info(medicine_name)
    
    if isinstance(result, dict):
        print(f"✓ Success! Found information from {result['source']}")
        print(f"Medicine: {result['name']}")
        print(f"Description: {result['description']}")
        
        # Display dosage information
        if result.get('dosage'):
            print(f"Dosage Information:")
            for i, dosage in enumerate(result['dosage'], 1):
                print(f"  {i}. {dosage}")
        else:
            print("Dosage Information: Not available")
        
        print(f"URL: {result['url']}")
        
        # Test text-to-speech
        print("\nTesting text-to-speech...")
        speech_text = f"Information for {result['name']}. {result['description'][:200]}..."
        if result.get('dosage'):
            speech_text += f" Dosage information includes: {', '.join(result['dosage'][:2])}."
        speak_text(speech_text)
        
    else:
        print(f"✗ No information found: {result}")
    
    return result

def test_text_to_speech():
    """Test the text-to-speech functionality"""
    print("Testing text-to-speech functionality...")
    test_text = "This is a test of the text to speech system for the medical dispenser."
    speak_text(test_text)
    print("Text-to-speech test completed!")

def get_medicine_with_dosage(medicine_name):
    """Get medicine information with detailed dosage breakdown"""
    result = medicine_lookup.get_comprehensive_info(medicine_name)
    
    if isinstance(result, dict):
        # Create detailed output with dosage
        output = {
            'medicine_name': result['name'],
            'description': result['description'],
            'source': result['source'],
            'url': result['url'],
            'dosage_info': result.get('dosage', []),
            'dosage_summary': None
        }
        
        # Create dosage summary
        if result.get('dosage'):
            dosage_types = {
                'strength': [],
                'frequency': [],
                'timing': [],
                'form': []
            }
            
            for dosage in result['dosage']:
                dosage_lower = dosage.lower()
                if any(unit in dosage_lower for unit in ['mg', 'g', 'ml', 'mcg']):
                    dosage_types['strength'].append(dosage)
                elif any(freq in dosage_lower for freq in ['daily', 'times', 'per day']):
                    dosage_types['frequency'].append(dosage)
                elif any(time in dosage_lower for time in ['hour', 'hr']):
                    dosage_types['timing'].append(dosage)
                elif any(form in dosage_lower for form in ['tablet', 'capsule', 'pill']):
                    dosage_types['form'].append(dosage)
            
            # Create summary
            summary_parts = []
            if dosage_types['strength']:
                summary_parts.append(f"Strength: {', '.join(dosage_types['strength'][:2])}")
            if dosage_types['frequency']:
                summary_parts.append(f"Frequency: {', '.join(dosage_types['frequency'][:2])}")
            if dosage_types['timing']:
                summary_parts.append(f"Timing: {', '.join(dosage_types['timing'][:2])}")
            
            output['dosage_summary'] = ' | '.join(summary_parts) if summary_parts else 'Dosage information available'
        
        return output
    else:
        return {'error': result}

# Example usage and testing
if __name__ == "__main__":
    # Test text-to-speech first
    test_text_to_speech()
    
    # Test with common medicines
    test_medicines = [
        "Paracetamol",
        "Ibuprofen", 
        "Aspirin",
        "Amoxicillin",
        "Omeprazole"
    ]
    
    for medicine in test_medicines:
        test_medicine_lookup(medicine)
        print("\n" + "="*50 + "\n")
        time.sleep(2)  # Be respectful to servers
