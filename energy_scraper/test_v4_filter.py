import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from energy_scraper.ai_extractor import AsyncAIExtractor

async def test_v4_filter():
    extractor = AsyncAIExtractor()
    
    test_cases = [
        ("AZIO Secures Binding Customer Deposits Covering ~42% of $108M GPU Infrastructure Pipeline", "High-performance computing and GPU clusters for AI workloads."),
        ("Independence Energy and Contango Oil and Gas Company Complete Merger", "Formation of Crescent Energy Company."),
        ("Stryten Energy Strengthens Battery Production Capacity with Acquisition of Tulip Richardson", "Lead-acid and lithium battery manufacturing."),
        ("ASP Isotopes Completes Well Drilling Required for Phase 1", "Operational update on the isotope enrichment facility drilling."),
        ("The Home Depot Subsidiary SRS Distribution Enters into Agreement to Acquire Wholesale HVAC Distributor Mingledorff's", "Distribution of heating, ventilation and air conditioning systems."),
        ("Green Cement Market to Reach US$ 74.4 Billion by 2033", "Market research report on decarbonization in construction.")
    ]
    
    print("\n--- Testing v4.0 AI-Native Agentic Filter ---\n")
    
    for headline, body in test_cases:
        print(f"Testing: {headline[:80]}...")
        result = await extractor.verify_is_deal(headline, body)
        is_deal = result.get('is_deal', False)
        reason = result.get('reason', 'N/A')
        
        status = "✅ REJECTED (Correct)" if not is_deal else "❌ ACCEPTED (Wrong)"
        if "Merger" in headline and is_deal: status = "✅ ACCEPTED (Correct)"
        if "Battery" in headline and is_deal: status = "✅ ACCEPTED (Correct - Energy Storage)"
        
        print(f"Result: {status}")
        print(f"Reasoning: {reason}\n")

if __name__ == "__main__":
    asyncio.run(test_v4_filter())
