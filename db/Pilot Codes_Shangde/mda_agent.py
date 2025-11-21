"""
Metadata Discovery Agent (MDA)
Autonomously explores data directory and builds comprehensive knowledge base
"""

import json
import ollama
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class MetadataDiscoveryAgent:
    """Main MDA class that orchestrates data understanding"""

    def __init__(self, model_name: str = "gpt-oss:20b", max_fields: int = 10):
        """
        Initialize MDA with Ollama model

        Args:
            model_name: Name of Ollama model to use
            max_fields: Maximum number of fields to analyze per dataset
        """
        self.model_name = model_name
        self.max_fields = max_fields
        self.metadata_cache = None

    def discover(self, metadata_file: str, output_file: str = "outputs/knowledge_base.json") -> Dict[str, Any]:
        """
        Main discovery process

        Args:
            metadata_file: Path to metadata_output.json from scanner
            output_file: Path to save knowledge base

        Returns:
            Complete knowledge base dictionary
        """
        print(f"[MDA] Loading metadata from: {metadata_file}")
        with open(metadata_file, 'r', encoding='utf-8') as f:
            self.metadata_cache = json.load(f)

        print(f"[MDA] Analyzing {len(self.metadata_cache['files'])} datasets...")

        knowledge_base = {
            "discovery_timestamp": datetime.now().isoformat(),
            "source_metadata": metadata_file,
            "total_datasets": len(self.metadata_cache['files']),
            "datasets": []
        }

        for idx, file_meta in enumerate(self.metadata_cache['files'], 1):
            print(f"[MDA] Processing {idx}/{knowledge_base['total_datasets']}: {file_meta['file_name']}")

            dataset_knowledge = self._analyze_dataset(file_meta)
            knowledge_base['datasets'].append(dataset_knowledge)

        # Save knowledge base
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge_base, f, indent=2, ensure_ascii=False)

        print(f"\n[MDA] Knowledge base saved to: {output_file}")
        return knowledge_base

    def _analyze_dataset(self, file_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive analysis of a single dataset"""

        dataset_knowledge = {
            "file_name": file_meta['file_name'],
            "file_path": file_meta['file_path'],
            "data_type": file_meta['data_type'],
            "classification": self._classify_primary_secondary(file_meta),
            "spatial_context": self._extract_spatial_context(file_meta),
            "temporal_context": self._extract_temporal_context(file_meta),
            "semantic_context": self._extract_semantic_context(file_meta),
            "fields": self._analyze_fields(file_meta),
            "capable_tasks": self._identify_capable_tasks(file_meta)
        }

        return dataset_knowledge

    def _classify_primary_secondary(self, file_meta: Dict[str, Any]) -> str:
        """Classify dataset as primary or secondary using LLM"""

        prompt = f"""Classify this dataset as either "primary" or "secondary":

Primary data = Original/raw data collected from sources (e.g., census, surveys, satellite imagery)
Secondary data = Derived/processed data generated from other datasets (e.g., aggregated, dissolved, clipped, calculated)

Dataset name: {file_meta['file_name']}
Data type: {file_meta.get('data_type', 'unknown')}
File size: {file_meta.get('file_size', {}).get('readable', 'unknown')}

Analyze the filename and context. Respond with ONLY one word: "primary" or "secondary"."""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )

            classification = response['message']['content'].strip().lower()

            # Validate response
            if 'primary' in classification:
                return 'primary'
            elif 'secondary' in classification:
                return 'secondary'
            else:
                return 'unknown'

        except Exception as e:
            print(f"  Warning: Classification failed - {str(e)}")
            return 'unknown'

    def _extract_spatial_context(self, file_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and interpret spatial context"""

        spatial_context = {}

        if file_meta['data_type'] == 'geospatial':
            # Extract technical spatial info
            spatial_context['geometry_type'] = file_meta.get('geometry_type', 'unknown')
            spatial_context['crs'] = file_meta.get('crs', 'unknown')

            # Geographic extent interpretation
            if 'bounds_latlon' in file_meta:
                bounds = file_meta['bounds_latlon']
                spatial_context['extent_coords'] = bounds

                # Use LLM to interpret geographic location
                prompt = f"""What geographic area/region is represented by these coordinates?
West: {bounds.get('west')}, South: {bounds.get('south')}, East: {bounds.get('east')}, North: {bounds.get('north')}

Provide a concise location description (e.g., "Miami-Dade County, Florida" or "Southern California Coast"). Response in 5 words or less."""

                try:
                    response = ollama.chat(
                        model=self.model_name,
                        messages=[{'role': 'user', 'content': prompt}]
                    )
                    spatial_context['extent_description'] = response['message']['content'].strip()
                except:
                    spatial_context['extent_description'] = 'Unknown region'

            spatial_context['feature_count'] = file_meta.get('feature_count', 0)

        return spatial_context

    def _extract_temporal_context(self, file_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and interpret temporal context"""

        temporal_context = {}

        # File modification date
        temporal_context['file_modified'] = file_meta.get('last_modified', 'unknown')

        # Check for temporal fields
        if 'features' in file_meta:
            date_fields = [
                f['name'] for f in file_meta['features']
                if 'date' in f.get('type', '').lower() or 'date' in f.get('name', '').lower()
            ]

            if date_fields:
                temporal_context['temporal_fields'] = date_fields
                temporal_context['has_temporal_dimension'] = True
            else:
                temporal_context['has_temporal_dimension'] = False

        # LLM inference of reference year/period
        prompt = f"""Based on the filename and context, what year or time period does this dataset likely represent?

Filename: {file_meta['file_name']}
Modified: {temporal_context['file_modified']}

Respond with just the year (e.g., "2024") or period (e.g., "2020-2023"). If uncertain, say "unknown"."""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            temporal_context['reference_period'] = response['message']['content'].strip()
        except:
            temporal_context['reference_period'] = 'unknown'

        return temporal_context

    def _extract_semantic_context(self, file_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Extract semantic meaning using LLM"""

        # Prepare context for LLM
        context_info = {
            'filename': file_meta['file_name'],
            'data_type': file_meta.get('data_type', 'unknown'),
            'geometry': file_meta.get('geometry_type', 'N/A'),
            'sample_fields': []
        }

        # Get sample field names
        if 'features' in file_meta:
            context_info['sample_fields'] = [f['name'] for f in file_meta['features'][:5]]

        # Get sample data if available
        sample_data_preview = ""
        if 'sample_data' in file_meta and file_meta['sample_data']:
            sample_items = list(file_meta['sample_data'].items())[:3]
            sample_data_preview = "\n".join([f"{k}: {v}" for k, v in sample_items])

        prompt = f"""Analyze this dataset and describe what it represents in urban planning context.

Filename: {context_info['filename']}
Type: {context_info['data_type']}
Geometry: {context_info['geometry']}
Fields: {', '.join(context_info['sample_fields'])}

Sample data:
{sample_data_preview}

Provide:
1. What this dataset represents (one sentence)
2. Urban planning domain (e.g., "land use", "transportation", "demographics")

Format your response as:
REPRESENTS: <one sentence>
DOMAIN: <domain name>"""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )

            content = response['message']['content']

            # Parse response
            represents = "Unknown"
            domain = "Unknown"

            for line in content.split('\n'):
                if 'REPRESENTS:' in line:
                    represents = line.split('REPRESENTS:')[1].strip()
                elif 'DOMAIN:' in line:
                    domain = line.split('DOMAIN:')[1].strip()

            return {
                'represents': represents,
                'domain': domain
            }

        except Exception as e:
            print(f"  Warning: Semantic extraction failed - {str(e)}")
            return {
                'represents': 'Unknown',
                'domain': 'Unknown'
            }

    def _analyze_fields(self, file_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze field meanings using LLM (batch mode for speed)"""

        if 'features' not in file_meta or not file_meta['features']:
            return []

        # Get sample data for context
        sample_data = file_meta.get('sample_data', {})

        # Prepare all fields info (limit based on max_fields setting)
        fields_to_analyze = file_meta['features'][:self.max_fields]

        # Build batch prompt with all fields
        fields_info = []
        for idx, field in enumerate(fields_to_analyze, 1):
            field_name = field['name']
            field_type = field.get('type', 'unknown')
            sample_values = sample_data.get(field_name, [])
            sample_str = str(sample_values[:3]) if sample_values else "No samples"

            fields_info.append(f"{idx}. {field_name} | Type: {field_type} | Samples: {sample_str}")

        prompt = f"""Analyze these data fields and provide interpretation for each.

Fields:
{chr(10).join(fields_info)}

For EACH field, respond in this format:
FIELD: <field_name>
MEANING: <brief description>
CATEGORY: <categorical/numerical/temporal/spatial>
---"""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )

            content = response['message']['content']

            # Parse batch response
            analyzed_fields = []
            current_field = {}

            for line in content.split('\n'):
                line = line.strip()

                if line.startswith('FIELD:'):
                    # Save previous field if exists
                    if current_field:
                        analyzed_fields.append(current_field)
                    # Start new field
                    field_name = line.split('FIELD:')[1].strip()
                    current_field = {
                        'name': field_name,
                        'type': next((f.get('type', 'unknown') for f in fields_to_analyze if f['name'] == field_name), 'unknown'),
                        'meaning': 'Unknown',
                        'category': 'unknown'
                    }
                elif line.startswith('MEANING:') and current_field:
                    current_field['meaning'] = line.split('MEANING:')[1].strip()
                elif line.startswith('CATEGORY:') and current_field:
                    current_field['category'] = line.split('CATEGORY:')[1].strip().lower()
                elif line == '---' and current_field:
                    # End of current field
                    analyzed_fields.append(current_field)
                    current_field = {}

            # Add last field if not yet added
            if current_field:
                analyzed_fields.append(current_field)

            # Ensure we have results for all fields (fallback)
            if len(analyzed_fields) < len(fields_to_analyze):
                for field in fields_to_analyze:
                    if not any(af['name'] == field['name'] for af in analyzed_fields):
                        analyzed_fields.append({
                            'name': field['name'],
                            'type': field.get('type', 'unknown'),
                            'meaning': 'Parse failed',
                            'category': 'unknown'
                        })

            return analyzed_fields

        except Exception as e:
            print(f"  Warning: Batch field analysis failed - {str(e)}")
            # Fallback: return basic info
            return [{
                'name': field['name'],
                'type': field.get('type', 'unknown'),
                'meaning': 'Analysis failed',
                'category': 'unknown'
            } for field in fields_to_analyze]

    def _identify_capable_tasks(self, file_meta: Dict[str, Any]) -> List[str]:
        """Identify what analysis tasks this dataset can support"""

        # Start with operations from metadata scanner
        base_operations = file_meta.get('applicable_operations', [])

        # Use LLM to identify higher-level planning tasks
        context = {
            'filename': file_meta['file_name'],
            'type': file_meta.get('data_type'),
            'geometry': file_meta.get('geometry_type', 'N/A')
        }

        prompt = f"""Based on this dataset characteristics, what urban planning analysis tasks can it support?

Filename: {context['filename']}
Type: {context['type']}
Geometry: {context['geometry']}

List 3-5 specific planning analysis tasks (e.g., "Transit accessibility analysis", "Zoning compliance checking").

Format: One task per line, no numbering."""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )

            content = response['message']['content'].strip()

            # Parse tasks (each line is a task)
            llm_tasks = [
                line.strip().lstrip('•-*').strip()
                for line in content.split('\n')
                if line.strip() and not line.strip().startswith('#')
            ]

            # Combine base operations with LLM-identified tasks
            all_tasks = base_operations[:5] + llm_tasks  # Limit base ops to 5

            return all_tasks

        except Exception as e:
            print(f"  Warning: Task identification failed - {str(e)}")
            return base_operations[:10]  # Fallback to base operations


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description='Metadata Discovery Agent')
    parser.add_argument('metadata_file', help='Path to metadata_output.json')
    parser.add_argument('-o', '--output', help='Output knowledge base file',
                       default='outputs/knowledge_base.json')
    parser.add_argument('-m', '--model', help='Ollama model name',
                       default='gpt-oss:20b')
    parser.add_argument('-f', '--max-fields', type=int, help='Max fields to analyze per dataset',
                       default=10)

    args = parser.parse_args()

    print("=" * 60)
    print("Metadata Discovery Agent (MDA)")
    print("=" * 60)

    mda = MetadataDiscoveryAgent(model_name=args.model, max_fields=args.max_fields)
    knowledge_base = mda.discover(args.metadata_file, args.output)

    print("\n" + "=" * 60)
    print(f"Discovery complete! Analyzed {knowledge_base['total_datasets']} datasets")
    print("=" * 60)


if __name__ == '__main__':
    main()
