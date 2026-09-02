# Supply Chain Knowledge Graph RAG (GraphRAG)

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.0+-008CC1?style=flat&logo=neo4j&logoColor=white)](https://neo4j.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Flash-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end **Knowledge Graph Retrieval-Augmented Generation (GraphRAG)** system designed for supply-chain risk analysis, multi-hop dependency tracing, and bottleneck discovery. 

Unlike traditional vector-only RAG that struggles with multi-hop relational reasoning across entities, this GraphRAG system translates natural language queries into precise Cypher graph queries, traverses multi-tier supplier-part-product dependencies in **Neo4j**, and synthesizes executive supply-chain intelligence reports using **Google Gemini**.

---

## Key Features

- **Natural Language to Cypher Translation**: Translates complex supply-chain questions into executable Cypher queries with strict schema grounding and zero SQL hallucination.
- **Multi-Hop Dependency & Bottleneck Tracing**: Traces upstream supplier purchase order delays across bills of materials (BOM) to pinpoint affected finished products and manufacturing plants:
  $$\text{Supplier} \xrightarrow{\text{ISSUED\_PO}} \text{PurchaseOrder} \xrightarrow{\text{ORDERS\_PART}} \text{Part} \xrightarrow{\text{USED\_IN}} \text{Product}$$
- **Interactive Graph Visualization**: Full-screen interactive force-directed and hierarchical graph map built with **Vis.js**, featuring dynamic real-time query path highlighting and node property inspection.
- **Traceability & Citations Audit Trail**: Generates structured citation cards mapping each analysis finding to specific Purchase Orders, Suppliers, Component IDs, and Assembly Plants.
- **Executive Analyst Synthesis**: Converts raw graph database records into structured business reports complete with operational impact breakdowns and actionable recommendations.

---

## Graph Schema & Ontology

```mermaid
graph LR
    Supplier["Supplier (ID, Name, Risk)"] -->|ISSUED_PO| PO["PurchaseOrder (ID, Qty, Dates)"]
    PO -->|ORDERS_PART| Part["Part (ID, Name, Price, Criticality)"]
    PO -->|DELIVERED_TO| Plant["Plant (ID, Name, Location)"]
    Plant -->|MANUFACTURES| Product["Product (ID, Name, Customer)"]
    Part -->|USED_IN {qty}| Product

    classDef supplier fill:#3b82f6,stroke:#60a5fa,color:#fff;
    classDef po fill:#eab308,stroke:#facc15,color:#000;
    classDef part fill:#f97316,stroke:#fb923c,color:#fff;
    classDef plant fill:#8b5cf6,stroke:#a78bfa,color:#fff;
    classDef prod fill:#10b981,stroke:#34d399,color:#fff;

    class Supplier supplier;
    class PO po;
    class Part part;
    class Plant plant;
    class Product prod;
```

### Entity Nodes
- **`Supplier`**: ID, Name, Geographic Location, Risk Rating (`Low`, `Medium`, `High`).
- **`Part`**: ID, Name, Category, Unit Price, Criticality (`Low`, `Medium`, `High`).
- **`Plant`**: ID, Facility Name, Location.
- **`Product`**: ID, Product Name, Customer / Client.
- **`PurchaseOrder`**: ID, Quantity, Order Date, Expected Delivery Date, Actual Delivery Date.

---

## Project Structure

```text
.
├── generate_mock_data.py    # Synthetic ERP supply-chain data generator
├── upload_to_neo4j.py       # Data ingestion pipeline for Neo4j Aura / Local
├── rag_pipeline.py          # Standalone CLI GraphRAG translation & synthesis pipeline
├── server.py                # FastAPI backend serving REST API & web dashboard
├── requirements.txt         # Project dependencies
├── .env.example             # Environment variables configuration template
├── .gitignore               # Git exclusion rules
├── static/
│   ├── index.html           # Dashboard UI with split-pane visualizer
│   ├── index.css            # Dark-mode dashboard styling
│   └── app.js               # Vis.js graph visualizer and query pipeline controller
└── *.csv                    # Synthetic supply chain datasets (BOM, POs, Parts, etc.)
```

---

## Getting Started

### 1. Prerequisites
- **Python**: 3.10 or newer
- **Neo4j**: Neo4j AuraDB (Free cloud instance) or local Neo4j Desktop / Docker
- **Google Gemini API Key**: [Get a Gemini API Key](https://aistudio.google.com/)

### 2. Clone and Setup Environment

```bash
git clone https://github.com/<your-username>/supply-chain-graphrag.git
cd supply-chain-graphrag

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Credentials

Copy the `.env.example` template to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your actual database and API credentials:

```env
# Neo4j Database Configuration
NEO4J_URI=neo4j+s://<your-instance-id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password
NEO4J_DATABASE=neo4j

# Google Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.6-flash
```

---

## Data Ingestion & Execution

### 1. Generate Synthetic Datasets (Optional)
The repository includes sample CSVs, but you can regenerate fresh synthetic data anytime:

```bash
python generate_mock_data.py
```

### 2. Ingest Data into Neo4j
Load the entities and relationships into your Neo4j graph:

```bash
python upload_to_neo4j.py
```

### 3. Run via CLI Pipeline
To run natural language supply-chain queries directly in your terminal:

```bash
python rag_pipeline.py
```

### 4. Run the Web Dashboard & Visualizer
Launch the interactive web interface:

```bash
python server.py
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser to interact with the live GraphRAG visualizer.

---

## Example Queries

| Query | What GraphRAG Traverses |
|---|---|
| *"Which products are affected by Supplier Alpha's late deliveries?"* | `(Supplier)-[:ISSUED_PO]->(PO)-[:ORDERS_PART]->(Part)-[:USED_IN]->(Product)` |
| *"Find all pending purchase orders containing High criticality parts and tell me which plants they go to."* | `(PO)-[:ORDERS_PART]->(Part {criticality: 'High'})` and `(PO)-[:DELIVERED_TO]->(Plant)` |
| *"Calculate the total order value of all late purchase orders."* | Matches late POs and sums `po.quantity * part.unit_price` |

---

## Tech Stack

- **Graph Database**: [Neo4j](https://neo4j.com/)
- **LLM Engine**: [Google Gemini 3.6 Flash](https://ai.google.dev/) via `google-genai` SDK
- **Backend API**: [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
- **Data Modeling & Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Data Engineering**: [Pandas](https://pandas.pydata.org/), [NumPy](https://numpy.org/)
- **Frontend Visualization**: [Vis.js Network](https://visjs.org/), Vanilla JS, Modern CSS

---

## License

This project is licensed under the [MIT License](LICENSE).
