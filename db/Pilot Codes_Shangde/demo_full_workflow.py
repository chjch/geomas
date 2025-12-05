"""
Complete Two-Agent Workflow Demo
Demonstrates the full pipeline: Scanner → MDA → QP
"""

import json
from pathlib import Path
from metadata_scanner import MetadataScanner
from mda_agent import MetadataDiscoveryAgent
from qp_agent import QueryProcessingAgent


def demo_full_workflow():
    """Run complete workflow demonstration"""

    print("=" * 80)
    print(" Two-Agent Data Discovery System - Complete Workflow Demo")
    print("=" * 80)

    # ========== STEP 1: Metadata Scanning ==========
    print("\n[STEP 1] Running Metadata Scanner...")
    print("-" * 80)

    data_directory = r"C:\Users\gaosh\UFL Dropbox\Shangde Gao\BMPO Ranking Tool\GIS Data\Regional Activity Centers"

    # Check if metadata already exists
    metadata_file = "metadata_output.json"

    if Path(metadata_file).exists():
        print(f"Using existing metadata file: {metadata_file}")
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    else:
        print(f"Scanning directory: {data_directory}")
        scanner = MetadataScanner()
        metadata = scanner.scan_directory(data_directory, metadata_file)

    print(f"✓ Found {metadata['total_files']} datasets")

    # ========== STEP 2: Metadata Discovery Agent (MDA) ==========
    print("\n[STEP 2] Running Metadata Discovery Agent (MDA)...")
    print("-" * 80)

    knowledge_base_file = "outputs/knowledge_base.json"

    if Path(knowledge_base_file).exists():
        print(f"Using existing knowledge base: {knowledge_base_file}")
        with open(knowledge_base_file, 'r') as f:
            knowledge_base = json.load(f)
    else:
        print("Analyzing metadata with AI agent (max 3 fields per dataset)...")
        mda = MetadataDiscoveryAgent(model_name="gpt-oss:20b", max_fields=3)
        knowledge_base = mda.discover(metadata_file, knowledge_base_file)

    print(f"✓ Knowledge base created with {knowledge_base['total_datasets']} analyzed datasets")

    # Display sample knowledge
    print("\nSample Dataset Knowledge:")
    if knowledge_base['datasets']:
        sample = knowledge_base['datasets'][0]
        print(f"  File: {sample['file_name']}")
        print(f"  Classification: {sample['classification']}")
        print(f"  Represents: {sample['semantic_context']['represents']}")
        print(f"  Domain: {sample['semantic_context']['domain']}")

    # ========== STEP 3: Query Processing Agent (QP) ==========
    print("\n[STEP 3] Running Query Processing Agent (QP)...")
    print("-" * 80)

    # Example queries to demonstrate
    example_queries = [
        "Analyze residential density near transit stops",
        "Find areas with high accessibility to activity centers",
        "Calculate land use distribution in redevelopment areas"
    ]

    print("\nExample queries:")
    for i, q in enumerate(example_queries, 1):
        print(f"  {i}. {q}")

    # Process first query as demo
    selected_query = example_queries[0]
    print(f"\nProcessing query: '{selected_query}'")

    qp = QueryProcessingAgent(
        knowledge_base_file=knowledge_base_file,
        ontology_file="planning_ontology.ttl",
        model_name="gpt-oss:20b"
    )

    analysis_spec = qp.process_query(selected_query, "outputs/analysis_spec.json")

    print(f"\n✓ Analysis specification generated")

    # ========== STEP 4: Display Results ==========
    print("\n[STEP 4] Analysis Results Summary")
    print("-" * 80)

    print("\nParsed Query:")
    print(f"  Intent: {analysis_spec['parsed_query']['intent']}")
    print(f"  Concepts: {', '.join(analysis_spec['parsed_query']['concepts'])}")
    print(f"  Entities: {', '.join(analysis_spec['parsed_query']['entities'])}")

    print("\nActivated Ontology:")
    print(f"  Relevant methods: {', '.join(analysis_spec['ontology_context']['methods'][:5])}")

    print("\nRequired Data:")
    for i, data in enumerate(analysis_spec['required_data'][:5], 1):
        print(f"  {i}. {data['dataset']} (relevance: {data['relevance_score']})")

    print("\nAnalysis Workflow:")
    for step in analysis_spec['analysis_workflow']:
        print(f"  Step {step.get('step', '?')}: {step.get('operation', 'N/A')}")
        print(f"    Data: {step.get('data_source', 'N/A')}")
        print(f"    Method: {step.get('method', 'N/A')}")

    print("\nData Sufficiency Check:")
    sufficiency = analysis_spec['sufficiency_check']
    print(f"  Status: {sufficiency['status']}")
    print(f"  Can complete: {sufficiency['can_complete']}")
    if sufficiency['missing_data']:
        print(f"  Missing: {', '.join(sufficiency['missing_data'])}")
    if sufficiency['alternatives']:
        print(f"  Alternatives: {sufficiency['alternatives']}")

    # ========== OUTPUT FILES ==========
    print("\n" + "=" * 80)
    print("Output Files Generated:")
    print("=" * 80)
    print(f"  1. {metadata_file} - Raw metadata from scanner")
    print(f"  2. {knowledge_base_file} - AI-enhanced knowledge base (MDA)")
    print(f"  3. outputs/analysis_spec.json - Structured analysis spec (QP)")
    print("\nThese outputs are ready for downstream processing (e.g., text2sql)")

    print("\n" + "=" * 80)
    print(" Demo Complete!")
    print("=" * 80)


def interactive_query_demo():
    """Interactive demo allowing user to input custom queries"""

    print("\n" + "=" * 80)
    print(" Interactive Query Processing Demo")
    print("=" * 80)

    # Check prerequisites
    knowledge_base_file = "outputs/knowledge_base.json"

    if not Path(knowledge_base_file).exists():
        print("\nError: Knowledge base not found!")
        print("Please run demo_full_workflow() first to generate the knowledge base.")
        return

    # Initialize QP
    print("\nInitializing Query Processing Agent...")
    qp = QueryProcessingAgent(
        knowledge_base_file=knowledge_base_file,
        ontology_file="planning_ontology.ttl",
        model_name="gpt-oss:20b"
    )

    print("\nReady! Enter your urban planning queries.")
    print("Type 'quit' to exit.\n")

    query_count = 0

    while True:
        try:
            query = input("Query: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                break

            if not query:
                continue

            query_count += 1
            output_file = f"outputs/analysis_spec_{query_count}.json"

            analysis_spec = qp.process_query(query, output_file)

            # Quick summary
            print("\n--- Quick Summary ---")
            print(f"Required datasets: {len(analysis_spec['required_data'])}")
            print(f"Workflow steps: {len(analysis_spec['analysis_workflow'])}")
            print(f"Saved to: {output_file}\n")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {str(e)}\n")

    print(f"\nProcessed {query_count} queries. Goodbye!")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'interactive':
        interactive_query_demo()
    else:
        demo_full_workflow()
