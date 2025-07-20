#!/usr/bin/env python3
"""
Integration test for weblookup and text-to-speech functionality with dosage information
"""

import sys
import time

def test_integration():
    """Test the integrated weblookup and text-to-speech functionality"""
    print("=" * 60)
    print("INTEGRATION TEST: WEBLOOKUP + TEXT-TO-SPEECH + DOSAGE")
    print("=" * 60)
    
    try:
        # Import the integrated functionality
        from weblookup import get_directions_and_speak, test_text_to_speech, get_medicine_with_dosage
        
        # Test 1: Text-to-speech functionality
        print("\n1. Testing text-to-speech functionality...")
        test_text_to_speech()
        
        # Test 2: Medicine lookup with speech and dosage
        print("\n2. Testing medicine lookup with speech and dosage...")
        test_medicines = ["Paracetamol", "Ibuprofen", "Aspirin"]
        
        for medicine in test_medicines:
            print(f"\nTesting: {medicine}")
            print("-" * 40)
            
            try:
                # Test basic functionality
                result = get_directions_and_speak(medicine)
                print(f"✓ SUCCESS: Information retrieved and spoken for {medicine}")
                print(f"  Result length: {len(result)} characters")
                
                # Test detailed dosage information
                detailed_result = get_medicine_with_dosage(medicine)
                if 'error' not in detailed_result:
                    print(f"  Medicine: {detailed_result['medicine_name']}")
                    print(f"  Source: {detailed_result['source']}")
                    
                    if detailed_result['dosage_info']:
                        print(f"  Dosage Information:")
                        for i, dosage in enumerate(detailed_result['dosage_info'], 1):
                            print(f"    {i}. {dosage}")
                        
                        if detailed_result['dosage_summary']:
                            print(f"  Dosage Summary: {detailed_result['dosage_summary']}")
                    else:
                        print(f"  Dosage Information: Not available")
                else:
                    print(f"  Detailed dosage info: {detailed_result['error']}")
                
            except Exception as e:
                print(f"✗ ERROR with {medicine}: {e}")
            
            # Wait between tests
            if medicine != test_medicines[-1]:
                print("Waiting 5 seconds before next test...")
                time.sleep(5)
        
        print("\n" + "=" * 60)
        print("✓ INTEGRATION TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"✗ IMPORT ERROR: {e}")
        print("Please ensure all dependencies are installed:")
        print("pip install -r requirements.txt")
        return False
        
    except Exception as e:
        print(f"✗ UNEXPECTED ERROR: {e}")
        return False

def test_specific_medicine():
    """Test a specific medicine with speech and dosage"""
    print("\n" + "=" * 60)
    print("SPECIFIC MEDICINE TEST WITH SPEECH AND DOSAGE")
    print("=" * 60)
    
    try:
        from weblookup import get_directions_and_speak, get_medicine_with_dosage
        
        medicine_name = input("Enter medicine name to test: ").strip()
        
        if not medicine_name:
            print("No medicine name provided. Exiting.")
            return
        
        print(f"\nTesting: {medicine_name}")
        print("-" * 40)
        
        # Test basic functionality
        result = get_directions_and_speak(medicine_name)
        
        if result:
            print(f"\n✓ SUCCESS! Information retrieved and spoken.")
            print(f"Text length: {len(result)} characters")
            
            # Test detailed dosage information
            detailed_result = get_medicine_with_dosage(medicine_name)
            if 'error' not in detailed_result:
                print(f"\n📋 DETAILED INFORMATION:")
                print(f"  Medicine: {detailed_result['medicine_name']}")
                print(f"  Source: {detailed_result['source']}")
                print(f"  Description: {detailed_result['description'][:100]}...")
                
                if detailed_result['dosage_info']:
                    print(f"\n💊 DOSAGE INFORMATION:")
                    for i, dosage in enumerate(detailed_result['dosage_info'], 1):
                        print(f"  {i}. {dosage}")
                    
                    if detailed_result['dosage_summary']:
                        print(f"\n📝 DOSAGE SUMMARY:")
                        print(f"  {detailed_result['dosage_summary']}")
                else:
                    print(f"\n💊 DOSAGE INFORMATION: Not available")
            else:
                print(f"\n✗ Detailed dosage info: {detailed_result['error']}")
        else:
            print(f"\n✗ No information found.")
            
    except Exception as e:
        print(f"✗ ERROR: {e}")

def test_dosage_extraction():
    """Test dosage extraction functionality specifically"""
    print("\n" + "=" * 60)
    print("DOSAGE EXTRACTION TEST")
    print("=" * 60)
    
    try:
        from weblookup import medicine_lookup
        
        # Test medicines that typically have dosage information
        test_medicines = [
            "Paracetamol 500mg",
            "Ibuprofen 400mg",
            "Aspirin 100mg",
            "Amoxicillin 500mg"
        ]
        
        for medicine in test_medicines:
            print(f"\nTesting dosage extraction for: {medicine}")
            print("-" * 40)
            
            result = medicine_lookup.get_comprehensive_info(medicine)
            
            if isinstance(result, dict):
                print(f"✓ Found information from {result['source']}")
                print(f"  Medicine: {result['name']}")
                
                if result.get('dosage'):
                    print(f"  Extracted Dosage Information:")
                    for i, dosage in enumerate(result['dosage'], 1):
                        print(f"    {i}. {dosage}")
                else:
                    print(f"  Dosage Information: Not extracted")
            else:
                print(f"✗ No information found")
            
            time.sleep(2)
        
        print("\n✓ Dosage extraction test completed!")
        
    except Exception as e:
        print(f"✗ ERROR in dosage extraction test: {e}")

if __name__ == "__main__":
    try:
        # Run integration test
        success = test_integration()
        
        # Run dosage extraction test
        test_dosage_extraction()
        
        # Ask if user wants to test a specific medicine
        if success:
            print("\nWould you like to test a specific medicine? (y/n): ", end="")
            response = input().strip().lower()
            
            if response in ['y', 'yes']:
                test_specific_medicine()
        
        print("\nTest completed!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1) 