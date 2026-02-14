#!/usr/bin/env python3
"""
Test script to verify AI provider integration.

This script tests both Gemini and Ollama providers (if available) to ensure
the abstraction layer is working correctly.
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from services.service_factory import MoodServiceFactory

def test_provider(provider_name: str):
    """Test a specific AI provider."""
    print(f"\n{'='*60}")
    print(f"Testing {provider_name.upper()} Provider")
    print(f"{'='*60}")

    # Create service
    if provider_name == 'gemini':
        if not Config.GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY not set, skipping")
            return False

        service = MoodServiceFactory.create_service(
            provider='gemini',
            gemini_api_key=Config.GEMINI_API_KEY,
            gemini_config=Config._config_data.get('gemini')
        )
    elif provider_name == 'ollama':
        ollama_config = Config._config_data.get('ai_provider', {}).get('ollama', {})
        service = MoodServiceFactory.create_service(
            provider='ollama',
            ollama_config=ollama_config
        )
    else:
        print(f"❌ Unknown provider: {provider_name}")
        return False

    if not service:
        print(f"❌ Failed to create {provider_name} service")
        return False

    print(f"✓ Service created successfully")

    # Test connection
    print("\n1. Testing connection...")
    try:
        connected = service.test_connection()
        if connected:
            print("   ✓ Connection test passed")
        else:
            print("   ❌ Connection test failed")
            return False
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return False

    # Test mood analysis
    print("\n2. Testing mood analysis...")
    try:
        test_query = "upbeat indie rock for a road trip"
        test_emojis = ["🚗", "🎸"]

        result = service.analyze_mood(test_query, test_emojis)

        if 'analysis' in result:
            analysis = result['analysis']
            print(f"   ✓ Analysis successful")
            print(f"   Mood: {analysis.get('mood', 'N/A')}")
            print(f"   Criteria: {analysis.get('matched_criteria', [])}")
        else:
            print("   ❌ Invalid analysis result format")
            return False
    except Exception as e:
        print(f"   ❌ Analysis error: {e}")
        return False

    # Test song recommendations
    print("\n3. Testing song recommendations...")
    try:
        songs_result = service.recommend_songs(
            text_description=test_query,
            analysis=result['analysis'],
            num_songs=5,
            emojis=test_emojis
        )

        if 'songs' in songs_result:
            songs = songs_result['songs']
            print(f"   ✓ Recommendations successful")
            print(f"   Songs returned: {len(songs)}")
            if songs:
                print(f"\n   Sample song:")
                song = songs[0]
                print(f"   - {song.get('title', 'N/A')} by {song.get('artist', 'N/A')}")
                print(f"   - Why: {song.get('why', 'N/A')}")
        else:
            print("   ❌ Invalid recommendations result format")
            return False
    except Exception as e:
        print(f"   ❌ Recommendations error: {e}")
        return False

    print(f"\n{'='*60}")
    print(f"✓ All tests passed for {provider_name.upper()}")
    print(f"{'='*60}")
    return True


def main():
    """Run provider tests."""
    print("AI Provider Integration Test")
    print(f"Environment: {Config._config_data.get('environment', 'unknown')}")
    print(f"Default provider: {Config.get_ai_provider()}")

    results = {}

    # Test Gemini if API key is available
    if Config.GEMINI_API_KEY:
        results['gemini'] = test_provider('gemini')
    else:
        print("\nSkipping Gemini tests (no API key)")

    # Test Ollama (will fail gracefully if not running)
    print("\nTesting Ollama...")
    results['ollama'] = test_provider('ollama')

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for provider, success in results.items():
        status = "✓ PASSED" if success else "❌ FAILED"
        print(f"{provider.upper()}: {status}")

    # Exit with error if any tests failed
    if not all(results.values()):
        sys.exit(1)


if __name__ == '__main__':
    main()
