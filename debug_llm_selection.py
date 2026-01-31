"""
Debug script to test LLM-based executor selection
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import and initialize extensions
import apflow.extensions  # noqa: F401
from apflow.core.extensions.manager import initialize_extensions
initialize_extensions()

from apflow.extensions.generate.schema_formatter import SchemaFormatter
from apflow.core.extensions.registry import get_registry

def test_executor_selection():
    """Test executor selection for website analysis requirement"""
    
    requirement = "please analyze aipartnerup.com and give a report with json format"
    
    print(f"Testing requirement: '{requirement}'")
    print("=" * 80)
    
    registry = get_registry()
    all_executors = registry.list_executors()
    print(f"Total executors available: {len(all_executors)}")
    
    # Test with LLM filtering
    print("\n1. Testing with LLM semantic matching:")
    print("-" * 80)
    formatter_llm = SchemaFormatter(use_llm_filter=True)
    
    try:
        relevant_executors = formatter_llm._filter_relevant_executors(
            requirement, all_executors, max_count=5
        )
        print(f"\n✓ LLM selected {len(relevant_executors)} executors:")
        for i, executor in enumerate(relevant_executors, 1):
            print(f"  {i}. {executor.id} - {executor.name}")
    except Exception as e:
        print(f"\n✗ LLM filtering failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test with keyword filtering (fallback)
    print("\n\n2. Testing with keyword matching (fallback):")
    print("-" * 80)
    formatter_keyword = SchemaFormatter(use_llm_filter=False)
    
    relevant_executors_kw = formatter_keyword._filter_relevant_executors(
        requirement, all_executors, max_count=5
    )
    print(f"\n✓ Keyword matching selected {len(relevant_executors_kw)} executors:")
    for i, executor in enumerate(relevant_executors_kw, 1):
        print(f"  {i}. {executor.id} - {executor.name}")
    
    # Compare results
    print("\n\n3. Comparison:")
    print("-" * 80)
    try:
        llm_ids = [e.id for e in relevant_executors]
        kw_ids = [e.id for e in relevant_executors_kw]
        
        print(f"LLM method:     {llm_ids}")
        print(f"Keyword method: {kw_ids}")
        
        if llm_ids == kw_ids:
            print("\n✓ Both methods selected the same executors in the same order")
        else:
            common = set(llm_ids) & set(kw_ids)
            print(f"\n✓ Common executors: {common}")
            if set(llm_ids) - set(kw_ids):
                print(f"  LLM-only: {set(llm_ids) - set(kw_ids)}")
            if set(kw_ids) - set(llm_ids):
                print(f"  Keyword-only: {set(kw_ids) - set(llm_ids)}")
    except Exception as e:
        print(f"(Could not compare - LLM filtering may have failed: {e})")

if __name__ == "__main__":
    test_executor_selection()
