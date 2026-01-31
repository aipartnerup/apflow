"""
Debug script to check executor selection for website analysis requirement
"""

from apflow.extensions.generate.schema_formatter import SchemaFormatter

formatter = SchemaFormatter()
requirement = "please analyze aipartnerup.com and give a report with json format"

# Extract keywords
keywords = formatter._extract_keywords(requirement.lower())
print("="*80)
print(f"Requirement: {requirement}")
print("="*80)
print(f"\nExtracted keywords: {keywords}")
print()

# Get all executors and calculate scores
all_executors = formatter.registry.list_executors()
scored = []
for exec in all_executors:
    score = formatter._calculate_relevance_score(exec, keywords, requirement.lower())
    if score > 0 or exec.id in ["scrape_executor", "system_info_executor", "crewai_executor"]:
        scored.append((score, exec))

scored.sort(key=lambda x: x[0], reverse=True)

print("\n" + "="*80)
print("Top 15 Executors by Relevance Score:")
print("="*80)
for i, (score, exec) in enumerate(scored[:15], 1):
    print(f"\n{i}. {exec.id} (Score: {score})")
    print(f"   Name: {exec.name}")
    print(f"   Description: {exec.description[:100]}...")
    print(f"   Tags: {exec.tags}")

# Check specific executors
print("\n" + "="*80)
print("Specific Executor Analysis:")
print("="*80)

for exec_id in ["scrape_executor", "system_info_executor", "crewai_executor"]:
    for score, exec in scored:
        if exec.id == exec_id:
            print(f"\n{exec_id}:")
            print(f"  Score: {score}")
            print(f"  Description: {exec.description}")
            print(f"  Tags: {exec.tags}")
            break

# Show what LLM sees
print("\n" + "="*80)
print("What LLM Sees (formatted):")
print("="*80)
formatted = formatter.format_for_requirement(requirement, max_executors=10, include_examples=False)
print(formatted[:2000])  # First 2000 chars
print("\n... (truncated)")
