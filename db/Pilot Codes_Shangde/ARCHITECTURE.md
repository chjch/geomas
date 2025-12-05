# Two-Agent Architecture Design

## System Overview

```
Directory with Data
    ↓
[Metadata Discovery Agent (MDA)]
    ↓
Data Knowledge Base (JSON)
    ↓                    
    ↓              [Planning Ontology (RDF)]
    ↓                    ↓
    └──────→ [Query Processing Agent (QP)] ←─── Human Query
                    ↓
            Structured Analysis Spec (JSON)
                    ↓
            Text2SQL Module (out of scope)
```

---

## Component 1: Metadata Discovery Agent (MDA)

### Purpose
Autonomously explore directory, understand all data comprehensively, and build knowledge base.

### Workflow

1. **Scan & Classify**
   - Use existing `metadata_scanner.py` to find all files
   - LLM classifies each as:
     * **Primary**: Raw/original data (e.g., census data, survey data)
     * **Secondary**: Derived/processed (e.g., dissolved parcels, aggregated statistics)
   - Detection logic: check filenames, metadata, creation dates, dependencies

2. **Context Understanding** (per dataset)
   - **Spatial**: Bounds, CRS, geometry type, coverage area
   - **Temporal**: Date fields, time range, currency
   - **Semantic**: What real-world phenomenon it represents (via LLM analyzing field names, samples, file names)

3. **Field-Level Analysis**
   - Sample 5-10 records quickly
   - LLM interprets: "SLUC1 = land use code", "ACRES = parcel area"
   - Detect data types, value ranges, categorical vs continuous

4. **Task/Capability Identification**
   - Based on context + fields, identify what analyses are possible
   - Example: "Polygon layer with land use codes → suitable for zoning analysis, spatial joins with demographic data, change detection"

5. **Output: Data Knowledge Base**

```json
{
  "datasets": [
    {
      "file_name": "parcels.shp",
      "classification": "primary",
      "spatial_context": {
        "extent": "Broward County, FL",
        "crs": "NAD83 Florida East",
        "geometry": "Polygon"
      },
      "temporal_context": {
        "reference_year": 2024,
        "currency": "current"
      },
      "semantic_context": {
        "represents": "Land parcels with zoning information",
        "domain": "land use planning"
      },
      "fields": [
        {"name": "SLUC1", "meaning": "Land use code", "type": "categorical"},
        {"name": "ACRES", "meaning": "Parcel area in acres", "type": "numeric"}
      ],
      "capable_tasks": [
        "Zoning distribution analysis",
        "Density calculation",
        "Spatial join with demographics"
      ]
    }
  ]
}
```

### Implementation
- **Files**: `mda_agent.py`, enhance `metadata_scanner.py`
- **LLM Integration**: Anthropic Claude API (for semantic reasoning)
- **Dependencies**: Existing scanner + LLM API

---

## Component 2: Planning Ontology (RDF)

### Purpose
Formal knowledge graph defining urban planning domain: concepts, entities, relationships.

### Structure

```turtle
# Planning Concepts
:LandUse rdf:type :PlanningConcept .
:Density rdf:type :PlanningConcept .
:Accessibility rdf:type :PlanningConcept .

# Urban Entities
:Parcel rdf:type :UrbanEntity .
:CensusTract rdf:type :UrbanEntity .
:TAZ rdf:type :UrbanEntity .

# Relationships
:Parcel :hasAttribute :LandUse .
:Density :measuredOn :Parcel .
:CensusTract :contains :Parcel .
:Accessibility :relatedTo :TransitStop .

# Analysis Methods
:ZonalStatistics :appliesTo :CensusTract .
:SpatialJoin :requires [:Parcel, :CensusTract] .
```

### Implementation
- **File**: `planning_ontology.rdf` or `.ttl`
- **Library**: `rdflib` (Python)
- **Initial Scope**: 20-30 core concepts/entities for MVP

---

## Component 3: Query Processing Agent (QP)

### Purpose
Parse human query, activate relevant knowledge, generate structured analysis specification.

### Workflow

**Step 1: Query Parsing**
```
Input: "I want to analyze residential density near transit stops in high-income areas"
Output: Extracted concepts/entities
  - Concepts: [Density, Accessibility]
  - Entities: [Parcel/TAZ, TransitStop]
  - Filters: [Residential, High-income]
```

**Step 2: Ontology Activation**
- Query RDF for relevant subgraph
- Find: Density → requires Parcel + area calculation
- Find: Near transit → requires spatial buffer, TransitStop layer
- Find: High-income → requires demographic data (CensusTract level)

**Step 3: Data Knowledge Activation**
- Search MDA knowledge base for matching datasets
- Match: "parcels.shp has land use, geometry"
- Match: "mobility_hubs.shp has transit locations"
- Match: Need demographic layer → check if exists

**Step 4: Analysis Process Specification**

```json
{
  "query": "Analyze residential density near transit...",
  "analysis_steps": [
    {
      "step": 1,
      "operation": "Filter parcels by land use = Residential",
      "data_source": "parcels.shp",
      "method": "attribute_query"
    },
    {
      "step": 2,
      "operation": "Buffer transit stops by 800m",
      "data_source": "mobility_hubs.shp",
      "method": "spatial_buffer"
    },
    {
      "step": 3,
      "operation": "Spatial join parcels with buffer",
      "method": "spatial_intersect"
    }
  ],
  "required_data": [
    {"dataset": "parcels.shp", "status": "available"},
    {"dataset": "mobility_hubs.shp", "status": "available"},
    {"dataset": "census_demographics", "status": "MISSING"}
  ],
  "sufficiency_check": {
    "can_complete": false,
    "missing_data": ["Census demographic data with income"],
    "alternative": "Use proxy: property values from parcels"
  }
}
```

**Step 5: Output Generation**
- Structured JSON for text2sql or workflow engine
- Include SQL hints, GIS operation sequences, data gaps

### Implementation
- **File**: `qp_agent.py`
- **LLM Role**: Parse query, reason about analysis logic
- **RDF Querying**: SPARQL queries via `rdflib`
- **Knowledge Base**: Load MDA's JSON output

---

## File Structure

```
Data Discovery/
├── metadata_scanner.py          # Enhanced with LLM integration
├── mda_agent.py                 # NEW: MDA orchestrator
├── qp_agent.py                  # NEW: QP orchestrator
├── planning_ontology.ttl        # NEW: RDF ontology
├── requirements.txt             # Add: anthropic, rdflib
├── outputs/
│   ├── metadata_output.json     # Raw metadata
│   ├── knowledge_base.json      # MDA output
│   └── analysis_spec.json       # QP output
└── example_usage.py             # Demo workflow
```

---

## MVP Scope

### MDA
- Primary/secondary classification
- Semantic understanding of 5-10 sample datasets
- Generate knowledge base JSON

### QP
- Simple ontology (10 concepts, 5 entities)
- Handle 3-5 query types
- Output structured analysis spec

### Out of Scope (Phase 2)
- FGDC XML parsing
- Auto-generating missing data
- Text2SQL implementation

---

## Supervisor Requirements Mapping

### Addressed in Architecture

✅ **Leverage agentic AI for data understanding**
- MDA: Autonomous exploration and interpretation
- QP: Intelligent query processing

✅ **Understand complete metadata**
- MDA processes all available metadata comprehensively

✅ **Semantic layer (beyond FGDC)**
- LLM adds semantic interpretation to technical metadata
- Planning ontology provides domain knowledge

✅ **Find relevant data**
- QP matches query concepts to available datasets

✅ **Identify suitable processing methods**
- MDA identifies capable tasks per dataset
- QP specifies analysis steps and methods

✅ **Understand spatial/temporal/semantic contexts**
- All three contexts explicitly captured in knowledge base

✅ **Downstream usefulness (text2sql)**
- QP outputs structured analysis spec as input

### Deferred to Phase 2

⏸️ **Understand semi-complete metadata**
- Inference engine for missing fields

⏸️ **Understand data without metadata**
- On-the-fly metadata generation

⏸️ **Evidence collection**
- Literature review on GIS data redundancy
- Experiments showing reduced duplication
