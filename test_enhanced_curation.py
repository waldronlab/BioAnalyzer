#!/usr/bin/env python3
"""
Test script for enhanced curation analysis functionality.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

from models.gemini_qa import GeminiQA

async def test_enhanced_curation_analysis():
    """Test the enhanced curation analysis with a sample paper."""
    
    # Initialize the Gemini QA system
    qa_system = GeminiQA()
    
    # Sample paper content for testing
    sample_paper = {
        "title": "Gut Microbiome Changes in Inflammatory Bowel Disease: A Meta-Analysis",
        "abstract": """
        Background: Inflammatory bowel disease (IBD) is characterized by chronic inflammation of the gastrointestinal tract. 
        Recent studies have shown that the gut microbiome plays a crucial role in IBD pathogenesis.
        
        Methods: We conducted a meta-analysis of 25 studies involving 1,200 IBD patients and 800 healthy controls. 
        Fecal samples were collected and analyzed using 16S rRNA gene sequencing. Differential abundance analysis 
        was performed using DESeq2 and LEfSe.
        
        Results: We identified significant differences in microbial composition between IBD patients and controls. 
        Several bacterial taxa were significantly enriched in IBD patients, including Escherichia coli (p < 0.001), 
        Enterococcus faecalis (p < 0.01), and Clostridium difficile (p < 0.05). Conversely, beneficial bacteria 
        such as Faecalibacterium prausnitzii (p < 0.001) and Bifidobacterium spp. (p < 0.01) were significantly 
        depleted in IBD patients.
        
        Conclusions: Our findings demonstrate clear microbial signatures associated with IBD, with specific taxa 
        showing consistent patterns of enrichment or depletion. These signatures may serve as potential biomarkers 
        for disease diagnosis and monitoring.
        """
    }
    
    print("Testing Enhanced Curation Analysis...")
    print("=" * 50)
    
    try:
        # Analyze the paper
        result = await qa_system.analyze_paper(sample_paper)
        
        print("Analysis completed successfully!")
        print(f"Status: {result.get('status', 'Unknown')}")
        print(f"Confidence: {result.get('confidence', 0.0):.2f}")
        
        # Check if enhanced curation analysis is present
        if 'curation_analysis' in result:
            curation = result['curation_analysis']
            print("\nEnhanced Curation Analysis Results:")
            print("-" * 30)
            print(f"Readiness: {curation.get('readiness', 'Unknown')}")
            print(f"Microbial Signatures: {curation.get('microbial_signatures', 'Unknown')}")
            print(f"Data Quality: {curation.get('data_quality', 'Unknown')}")
            print(f"Statistical Significance: {curation.get('statistical_significance', 'Unknown')}")
            print(f"Data Completeness: {curation.get('data_completeness', 'Unknown')}")
            
            if curation.get('explanation'):
                print(f"\nDetailed Explanation:")
                print(curation['explanation'])
            
            if curation.get('specific_reasons'):
                print(f"\nSpecific Reasons:")
                for reason in curation['specific_reasons']:
                    print(f"- {reason}")
            
            if curation.get('missing_fields'):
                print(f"\nMissing Fields: {', '.join(curation['missing_fields'])}")
            
            if curation.get('examples'):
                print(f"\nExamples and Evidence:")
                for example in curation['examples']:
                    print(f"- {example}")
        else:
            print("\nNo enhanced curation analysis found in results.")
        
        # Show key findings
        if result.get('key_findings'):
            print(f"\nKey Findings:")
            for finding in result['key_findings']:
                print(f"- {finding}")
        
        # Show suggested topics
        if result.get('suggested_topics'):
            print(f"\nSuggested Topics:")
            for topic in result['suggested_topics']:
                print(f"- {topic}")
                
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_enhanced_curation_analysis()) 