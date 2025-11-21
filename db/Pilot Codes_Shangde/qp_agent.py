"""
Query Processing Agent (QP)
Processes human queries and generates structured analysis specifications
"""

import json
import ollama
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS
from typing import Dict, List, Any, Optional
from datetime import datetime


class QueryProcessingAgent:
    """Main QP class that handles query understanding and analysis generation"""

    def __init__(self,
                 knowledge_base_file: str,
                 ontology_file: str = "planning_ontology.ttl",
                 model_name: str = "gpt-oss:20b"):
        """
        Initialize QP agent

        Args:
            knowledge_base_file: Path to MDA's knowledge_base.json
            ontology_file: Path to planning ontology RDF file
            model_name: Ollama model name
        """
        self.model_name = model_name

        # Load knowledge base
        print(f"[QP] Loading knowledge base: {knowledge_base_file}")
        with open(knowledge_base_file, 'r', encoding='utf-8') as f:
            self.knowledge_base = json.load(f)

        # Load ontology
        print(f"[QP] Loading planning ontology: {ontology_file}")
        self.ontology = Graph()
        self.ontology.parse(ontology_file, format='turtle')
        self.onto = Namespace("http://urbanplanning.org/ontology#")

        print(f"[QP] Loaded {len(self.knowledge_base['datasets'])} datasets")
        print(f"[QP] Loaded {len(self.ontology)} ontology triples")

    def process_query(self, query: str, output_file: str = "outputs/analysis_spec.json") -> Dict[str, Any]:
        """
        Main query processing pipeline

        Args:
            query: Human language query
            output_file: Path to save analysis specification

        Returns:
            Structured analysis specification
        """
        print(f"\n[QP] Processing query: '{query}'")
        print("=" * 60)

        # Step 1: Parse query and extract key concepts
        print("[QP] Step 1: Parsing query...")
        parsed_query = self._parse_query(query)

        # Step 2: Activate relevant ontology subgraph
        print("[QP] Step 2: Activating ontology...")
        ontology_context = self._activate_ontology(parsed_query)

        # Step 3: Find relevant datasets from knowledge base
        print("[QP] Step 3: Searching for relevant data...")
        relevant_data = self._search_knowledge_base(parsed_query)

        # Step 4: Generate analysis specification
        print("[QP] Step 4: Generating analysis specification...")
        analysis_spec = self._generate_analysis_spec(
            query, parsed_query, ontology_context, relevant_data
        )

        # Save output
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_spec, f, indent=2, ensure_ascii=False)

        print(f"\n[QP] Analysis specification saved to: {output_file}")
        return analysis_spec

    def _parse_query(self, query: str) -> Dict[str, Any]:
        """Parse query to extract concepts, entities, filters, and intent"""

        prompt = f"""Parse this urban planning query and extract key components:

Query: "{query}"

Extract:
1. Planning concepts (e.g., density, accessibility, land use)
2. Urban entities (e.g., parcels, census tracts, transit stops)
3. Filters/constraints (e.g., residential only, high-income areas)
4. Spatial relationships (e.g., near, within, adjacent to)
5. Analysis intent (what they want to know/calculate)

Format your response as:
CONCEPTS: concept1, concept2, concept3
ENTITIES: entity1, entity2
FILTERS: filter1, filter2
SPATIAL: relationship
INTENT: <one sentence describing what they want>"""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )

            content = response['message']['content']

            # Parse response
            parsed = {
                'original_query': query,
                'concepts': [],
                'entities': [],
                'filters': [],
                'spatial_relationships': [],
                'intent': ''
            }

            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('CONCEPTS:'):
                    parsed['concepts'] = [c.strip() for c in line.split('CONCEPTS:')[1].split(',')]
                elif line.startswith('ENTITIES:'):
                    parsed['entities'] = [e.strip() for e in line.split('ENTITIES:')[1].split(',')]
                elif line.startswith('FILTERS:'):
                    parsed['filters'] = [f.strip() for f in line.split('FILTERS:')[1].split(',')]
                elif line.startswith('SPATIAL:'):
                    parsed['spatial_relationships'] = [line.split('SPATIAL:')[1].strip()]
                elif line.startswith('INTENT:'):
                    parsed['intent'] = line.split('INTENT:')[1].strip()

            return parsed

        except Exception as e:
            print(f"  Warning: Query parsing failed - {str(e)}")
            return {
                'original_query': query,
                'concepts': [],
                'entities': [],
                'filters': [],
                'spatial_relationships': [],
                'intent': query
            }

    def _activate_ontology(self, parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        """Query ontology to find relevant relationships and methods"""

        concepts = parsed_query['concepts']
        entities = parsed_query['entities']

        activated_context = {
            'relevant_concepts': [],
            'relevant_entities': [],
            'relevant_methods': [],
            'relationships': []
        }

        # Find matching concepts in ontology
        for concept in concepts:
            concept_matches = self._fuzzy_match_ontology_term(concept, "PlanningConcept")
            activated_context['relevant_concepts'].extend(concept_matches)

        # Find matching entities
        for entity in entities:
            entity_matches = self._fuzzy_match_ontology_term(entity, "UrbanEntity")
            activated_context['relevant_entities'].extend(entity_matches)

        # Query relationships between activated concepts/entities
        for concept_uri in activated_context['relevant_concepts']:
            # Find what this concept relates to
            relations = self.ontology.query(f"""
                PREFIX : <http://urbanplanning.org/ontology#>
                SELECT ?relation ?target
                WHERE {{
                    <{concept_uri}> ?relation ?target .
                }}
            """)

            for row in relations:
                activated_context['relationships'].append({
                    'subject': str(concept_uri),
                    'predicate': str(row.relation),
                    'object': str(row.target)
                })

        # Find applicable analysis methods
        for entity_uri in activated_context['relevant_entities']:
            methods = self.ontology.query(f"""
                PREFIX : <http://urbanplanning.org/ontology#>
                SELECT ?method
                WHERE {{
                    ?method a :AnalysisMethod .
                    ?method :appliesTo <{entity_uri}> .
                }}
            """)

            for row in methods:
                method_name = str(row.method).split('#')[-1]
                if method_name not in activated_context['relevant_methods']:
                    activated_context['relevant_methods'].append(method_name)

        return activated_context

    def _fuzzy_match_ontology_term(self, term: str, term_type: str) -> List[str]:
        """Fuzzy match query term to ontology concepts/entities"""

        term_lower = term.lower()
        matches = []

        # Query for all terms of given type
        query_result = self.ontology.query(f"""
            PREFIX : <http://urbanplanning.org/ontology#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?term ?label
            WHERE {{
                ?term a :{term_type} .
                ?term rdfs:label ?label .
            }}
        """)

        for row in query_result:
            label = str(row.label).lower()
            # Simple fuzzy matching
            if term_lower in label or label in term_lower:
                matches.append(str(row.term))

        return matches

    def _search_knowledge_base(self, parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search knowledge base for datasets matching query requirements"""

        relevant_datasets = []

        concepts = [c.lower() for c in parsed_query['concepts']]
        entities = [e.lower() for e in parsed_query['entities']]
        intent = parsed_query['intent'].lower()

        for dataset in self.knowledge_base['datasets']:
            relevance_score = 0
            reasons = []

            # Check semantic context match
            semantic = dataset.get('semantic_context', {})
            represents = semantic.get('represents', '').lower()
            domain = semantic.get('domain', '').lower()

            # Match concepts with domain
            for concept in concepts:
                if concept in domain or concept in represents:
                    relevance_score += 2
                    reasons.append(f"Matches concept: {concept}")

            # Match entities with semantic representation
            for entity in entities:
                if entity in represents:
                    relevance_score += 2
                    reasons.append(f"Contains entity: {entity}")

            # Check geometry type match
            spatial_ctx = dataset.get('spatial_context', {})
            geometry = spatial_ctx.get('geometry_type', '').lower()

            for entity in entities:
                if ('parcel' in entity or 'building' in entity) and 'polygon' in geometry:
                    relevance_score += 1
                    reasons.append("Geometry matches entity type")
                elif ('transit' in entity or 'stop' in entity) and 'point' in geometry:
                    relevance_score += 1
                    reasons.append("Geometry matches entity type")

            # Check capable tasks
            capable_tasks = dataset.get('capable_tasks', [])
            for task in capable_tasks:
                task_lower = task.lower()
                if any(concept in task_lower for concept in concepts):
                    relevance_score += 1
                    reasons.append(f"Capable of related task: {task}")

            # Add dataset if relevant
            if relevance_score > 0:
                relevant_datasets.append({
                    'dataset': dataset,
                    'relevance_score': relevance_score,
                    'reasons': reasons
                })

        # Sort by relevance
        relevant_datasets.sort(key=lambda x: x['relevance_score'], reverse=True)

        return relevant_datasets

    def _generate_analysis_spec(self,
                                original_query: str,
                                parsed_query: Dict[str, Any],
                                ontology_context: Dict[str, Any],
                                relevant_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate final structured analysis specification"""

        # Prepare context for LLM
        context = {
            'query': original_query,
            'intent': parsed_query['intent'],
            'concepts': parsed_query['concepts'],
            'entities': parsed_query['entities'],
            'filters': parsed_query['filters'],
            'available_methods': ontology_context['relevant_methods'],
            'available_datasets': [
                {
                    'name': d['dataset']['file_name'],
                    'type': d['dataset']['data_type'],
                    'relevance': d['relevance_score'],
                    'reasons': d['reasons'][:2]
                }
                for d in relevant_data[:5]
            ]
        }

        # Use LLM to generate analysis steps
        prompt = f"""Design a step-by-step analysis workflow for this planning query.

Query: {context['query']}
Intent: {context['intent']}

Available datasets:
{json.dumps(context['available_datasets'], indent=2)}

Available analysis methods: {', '.join(context['available_methods'])}

Generate a detailed analysis workflow with:
1. Specific sequential steps
2. Which dataset to use for each step
3. What operation/method to apply
4. Any data gaps or limitations

Format as JSON:
{{
  "steps": [
    {{"step": 1, "operation": "...", "data_source": "...", "method": "..."}},
    {{"step": 2, "operation": "...", "data_source": "...", "method": "..."}}
  ],
  "data_sufficiency": "sufficient/partial/insufficient",
  "missing_data": ["..."],
  "alternatives": "..."
}}

Provide only valid JSON, no additional text."""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )

            content = response['message']['content'].strip()

            # Extract JSON from response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            workflow = json.loads(content)

        except Exception as e:
            print(f"  Warning: Workflow generation failed - {str(e)}")
            workflow = {
                'steps': [],
                'data_sufficiency': 'unknown',
                'missing_data': [],
                'alternatives': 'Manual workflow design needed'
            }

        # Build final specification
        analysis_spec = {
            'timestamp': datetime.now().isoformat(),
            'query': original_query,
            'parsed_query': parsed_query,
            'ontology_context': {
                'concepts': ontology_context['relevant_concepts'],
                'entities': ontology_context['relevant_entities'],
                'methods': ontology_context['relevant_methods']
            },
            'required_data': [
                {
                    'dataset': d['dataset']['file_name'],
                    'file_path': d['dataset']['file_path'],
                    'status': 'available',
                    'relevance_score': d['relevance_score'],
                    'why_relevant': d['reasons']
                }
                for d in relevant_data[:10]
            ],
            'analysis_workflow': workflow.get('steps', []),
            'sufficiency_check': {
                'can_complete': workflow.get('data_sufficiency') == 'sufficient',
                'status': workflow.get('data_sufficiency', 'unknown'),
                'missing_data': workflow.get('missing_data', []),
                'alternatives': workflow.get('alternatives', '')
            }
        }

        return analysis_spec


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description='Query Processing Agent')
    parser.add_argument('knowledge_base', help='Path to knowledge_base.json')
    parser.add_argument('query', help='Human language query')
    parser.add_argument('-o', '--output', help='Output analysis spec file',
                       default='outputs/analysis_spec.json')
    parser.add_argument('--ontology', help='Path to planning ontology',
                       default='planning_ontology.ttl')
    parser.add_argument('-m', '--model', help='Ollama model name',
                       default='gpt-oss:20b')

    args = parser.parse_args()

    print("=" * 60)
    print("Query Processing Agent (QP)")
    print("=" * 60)

    qp = QueryProcessingAgent(
        knowledge_base_file=args.knowledge_base,
        ontology_file=args.ontology,
        model_name=args.model
    )

    analysis_spec = qp.process_query(args.query, args.output)

    print("\n" + "=" * 60)
    print("Analysis Specification Generated")
    print("=" * 60)
    print(f"Steps: {len(analysis_spec['analysis_workflow'])}")
    print(f"Required datasets: {len(analysis_spec['required_data'])}")
    print(f"Sufficiency: {analysis_spec['sufficiency_check']['status']}")


if __name__ == '__main__':
    main()
