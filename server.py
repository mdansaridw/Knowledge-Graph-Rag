import os
import re
import warnings
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List
from neo4j import GraphDatabase
from google import genai
from google.genai import types


warnings.filterwarnings("ignore")
logging.getLogger("google.genai").setLevel(logging.ERROR)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

def normalize_uri(uri: str) -> str:
    """Format and normalize Neo4j URI scheme for reliable connectivity."""
    if not uri:
        return uri
    if uri.startswith("your-"):
        uri = uri.replace("your-", "", 1)
    if uri.startswith("neo4j+s://"):
        return uri.replace("neo4j+s://", "neo4j+ssc://")
    if uri.startswith("bolt+s://"):
        return uri.replace("bolt+s://", "bolt+ssc://")
    return uri

def get_gemini_client():
    """Initialize and return the Gemini API client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured. Please set it in your .env file."
        )
    return genai.Client(api_key=api_key)

def get_db_driver():
    """Establish connection pool to Neo4j."""
    clean_uri = normalize_uri(URI)
    if not clean_uri or not USERNAME or not PASSWORD or clean_uri == "your-neo4j-uri":
        raise HTTPException(
            status_code=500,
            detail="Neo4j connection credentials are not configured. Please set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD in your .env file."
        )
    return GraphDatabase.driver(clean_uri, auth=(USERNAME, PASSWORD))

app = FastAPI(title="Supply Chain GraphRAG Dashboard")

STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# -------------------------------------------------------------
# PYDANTIC SCHEMAS FOR STRUCTURED GEMINI OUTPUTS
# -------------------------------------------------------------
class TraversalStep(BaseModel):
    step_number: int
    source_type: str = Field(description="The starting entity type, e.g., Supplier, PurchaseOrder, Part, Plant, Product")
    target_type: str = Field(description="The destination entity type, e.g., Supplier, PurchaseOrder, Part, Plant, Product")
    relation: str = Field(description="The relationship name, e.g., ISSUED_PO, ORDERS_PART, DELIVERED_TO, USED_IN, MANUFACTURES")
    description: str = Field(description="Short sentence explaining what this hop represents in plain English")

class CypherResponse(BaseModel):
    cypher_query: str = Field(description="The raw, executable Cypher query. Do not wrap in markdown or backticks.")
    traversal_steps: List[TraversalStep] = Field(description="The logical step-by-step traversal path required to find this answer.")
    explanation: str = Field(description="Brief explanation of the search logic.")

class Citation(BaseModel):
    source_po: str = Field(description="The Purchase Order ID, e.g., PO00005. If not applicable, put N/A")
    supplier: str = Field(description="The Supplier name, e.g., Supplier Alpha. If not applicable, put N/A")
    part: str = Field(description="The Part name, e.g., Ethernet Controller. If not applicable, put N/A")
    plant: str = Field(description="The manufacturing plant receiving the part. If not applicable, put N/A")
    product: str = Field(description="The Product name affected. If not applicable, put N/A")
    description: str = Field(description="Brief description of the status or risk for this record")

class CitationList(BaseModel):
    citations: List[Citation] = Field(description="Structured citations showing the specific POs, parts, and plants behind this answer.")

class QueryRequest(BaseModel):
    question: str

# -------------------------------------------------------------
# GRAPH SCHEMA DEFINITION FOR LLM TRANSLATOR
# -------------------------------------------------------------
GRAPH_SCHEMA = """
Database Property Graph Schema:
1. Nodes:
   - :Supplier {id: STRING, name: STRING, location: STRING, risk_rating: STRING ("Low", "Medium", "High")}
   - :Part {id: STRING, name: STRING, category: STRING, unit_price: FLOAT, criticality: STRING ("Low", "Medium", "High")}
   - :Product {id: STRING, name: STRING, customer: STRING}
   - :Plant {id: STRING, name: STRING, location: STRING}
   - :PurchaseOrder {id: STRING, quantity: INTEGER, order_date: STRING (YYYY-MM-DD), expected_delivery_date: STRING (YYYY-MM-DD), actual_delivery_date: STRING (YYYY-MM-DD or null)}

2. Relationships (directed):
   - (s:Supplier)-[:ISSUED_PO]->(po:PurchaseOrder)
   - (po:PurchaseOrder)-[:ORDERS_PART]->(p:Part)
   - (po:PurchaseOrder)-[:DELIVERED_TO]->(pl:Plant)
   - (pl:Plant)-[:MANUFACTURES]->(pr:Product)
   - (p:Part)-[:USED_IN {quantity_required: INTEGER}]->(pr:Product)

Dynamic property logic:
- PurchaseOrder has a logical status:
  * "Pending" if actual_delivery_date is null or empty.
  * "On-Time" if actual_delivery_date <= expected_delivery_date.
  * "Late" if actual_delivery_date > expected_delivery_date.
- PurchaseOrder value is po.quantity * p.unit_price (linked via ORDERS_PART).
"""

def rewrite_query_for_traversal(query: str) -> tuple[str, bool]:
    """Dynamically rewrite Cypher queries to capture traversed path nodes."""
    if "path =" in query.lower():
        return query, False

    match_match = re.search(r'\bMATCH\b', query, re.IGNORECASE)
    if not match_match:
        return query, False

    match_idx = match_match.start()
    
    return_match = re.search(r'\bRETURN\b', query, re.IGNORECASE)
    if not return_match:
        return query, False
        
    new_query = query[:match_idx] + "MATCH path = " + query[match_idx + 5:]
    return_match_new = re.search(r'\bRETURN\b', new_query, re.IGNORECASE)
    if not return_match_new:
        return query, False
    return_idx_new = return_match_new.start()
    
    new_query = new_query[:return_idx_new] + "RETURN nodes(path) AS traversed_nodes, " + new_query[return_idx_new + 6:]
    return new_query, True

def extract_node_ids(results: list) -> list[str]:
    """Extract known entity node IDs from query results for visual highlighting."""
    ids = set()
    pattern = re.compile(r'\b(SUP\d{3}|PART\d{3}|PROD\d{3}|PLANT\d{3}|PO\d{5})\b', re.IGNORECASE)
    
    def search(obj):
        if isinstance(obj, str):
            matches = pattern.findall(obj)
            for m in matches:
                ids.add(m.upper())
        elif isinstance(obj, dict):
            for v in obj.values():
                search(v)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                search(item)
                
    search(results)
    return list(ids)

# -------------------------------------------------------------
# API ENDPOINTS
# -------------------------------------------------------------
@app.get("/api/graph-data")
def get_graph_data():
    """Retrieve full graph nodes and edges for network visualization."""
    driver = get_db_driver()
    nodes = {}
    edges = []
    
    try:
        with driver.session() as session:
            result = session.run("MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m")
            for record in result:
                n = record["n"]
                r = record["r"]
                m = record["m"]
                
                if n is not None:
                    n_id = n.get("id") or n.element_id
                    if n_id not in nodes:
                        nodes[n_id] = {
                            "id": n_id,
                            "label": n.get("name") or n.get("id"),
                            "type": list(n.labels)[0] if n.labels else "Unknown",
                            "properties": dict(n)
                        }
                if m is not None:
                    m_id = m.get("id") or m.element_id
                    if m_id not in nodes:
                        nodes[m_id] = {
                            "id": m_id,
                            "label": m.get("name") or m.get("id"),
                            "type": list(m.labels)[0] if m.labels else "Unknown",
                            "properties": dict(m)
                        }
                if r is not None and n is not None and m is not None:
                    n_id = n.get("id") or n.element_id
                    m_id = m.get("id") or m.element_id
                    edge_entry = {
                        "from": n_id,
                        "to": m_id,
                        "label": r.type
                    }
                    if edge_entry not in edges:
                        edges.append(edge_entry)
        return {"nodes": list(nodes.values()), "edges": edges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        driver.close()

@app.post("/api/query")
def run_query(request: QueryRequest):
    """Execute natural language query through GraphRAG pipeline."""
    question = request.question
    client = get_gemini_client()
    
    # 1. Translate question to Cypher & Traversal Steps
    system_instruction = f"""
    You are an expert Cypher query generator for a Neo4j database containing supply-chain data.
    Your task is to translate natural language questions into precise Cypher queries and logical traversal steps.
    
    {GRAPH_SCHEMA}
    
    CRITICAL RULES:
    1. Reply strictly conforming to the response JSON schema.
    2. Check relationship directions carefully.
    3. To find which products are affected by a supplier/PO delay, you MUST trace through the Part ordered and the BOM: 
       `(po)-[:ORDERS_PART]->(Part)-[:USED_IN]->(Product)`. 
       DO NOT take shortcuts through the Plant: `(po)-[:DELIVERED_TO]->(Plant)-[:MANUFACTURES]->(Product)` is semantically incorrect because it doesn't verify if the product uses the specific part.
    4. For visual path highlighting in our frontend, your Cypher queries MUST return all nodes matched in the pattern (e.g., if you match `(s:Supplier)-[:ISSUED_PO]->(po:PurchaseOrder)-[:ORDERS_PART]->(p:Part)-[:USED_IN]->(pr:Product)`, you MUST write `RETURN s, po, p, pr` rather than just `RETURN pr` or `RETURN pr.id`).
    5. Make string searches case-insensitive if appropriate by using toLower() or regex matches.
    6. For date comparisons, compare them as strings since they are formatted as YYYY-MM-DD.
    """
    
    try:
        translation_response = client.models.generate_content(
            model=MODEL_NAME,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=CypherResponse,
                temperature=0.0
            )
        )
        translation_data = CypherResponse.model_validate_json(translation_response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Cypher Translation failed: {str(e)}")

    # 2. Run generated Cypher query on Neo4j
    cypher_query = translation_data.cypher_query
    raw_db_results = []
    
    rewritten_query, is_rewritten = rewrite_query_for_traversal(cypher_query)
    
    try:
        driver = get_db_driver()
        with driver.session() as session:
            result = session.run(rewritten_query)
            for record in result:
                raw_db_results.append(record.data())
        driver.close()
    except Exception:
        raw_db_results = []
        is_rewritten = False
        try:
            driver = get_db_driver()
            with driver.session() as session:
                result = session.run(cypher_query)
                for record in result:
                    raw_db_results.append(record.data())
            driver.close()
        except Exception as fallback_err:
            raise HTTPException(
                status_code=500, 
                detail=f"Database Cypher execution failed: {str(fallback_err)}\nQuery: {cypher_query}"
            )

    # 3. Extract Node IDs for frontend highlighting
    highlighted_nodes_set = set()
    
    if is_rewritten:
        for record in raw_db_results:
            traversed = record.get("traversed_nodes") or []
            if isinstance(traversed, list):
                for node_dict in traversed:
                    if isinstance(node_dict, dict) and "id" in node_dict:
                        highlighted_nodes_set.add(node_dict["id"])
                        
    db_results = []
    for record in raw_db_results:
        clean_rec = {k: v for k, v in record.items() if k not in ["traversed_nodes", "traversed_edges"]}
        db_results.append(clean_rec)
        
    regex_nodes = extract_node_ids(db_results)
    for node_id in regex_nodes:
        highlighted_nodes_set.add(node_id)
        
    highlighted_nodes = list(highlighted_nodes_set)

    # 4. Synthesize Conversational Answer
    synthesis_prompt = f"""
    You are a Supply Chain Analyst.
    
    The user asked: "{question}"
    We ran this Cypher query on our Neo4j database: {cypher_query}
    The database returned the following results: {db_results}
    
    Write a comprehensive supply chain analysis report answering the user's question:
    1. Direct Answer First: Begin the report with a direct, clear answer containing the key facts immediately.
    2. Format: Write in clean Markdown using headers, bold text, bullet points, and tables where appropriate.
    3. Operational Context: Explain which purchase orders and components are involved.
    4. Business Implications: Discuss assembly bottlenecks, production downtime, delivery risks, and inventory impact.
    5. Actionable Next Steps: Conclude with practical recommendations for procurement and operations.
    """
    
    try:
        synthesis_response = client.models.generate_content(
            model=MODEL_NAME,
            contents=synthesis_prompt,
            config=types.GenerateContentConfig(
                temperature=0.4
            )
        )
        response_text = synthesis_response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversational Answer Synthesis failed: {str(e)}")

    # 5. Extract Structured Citations
    citations_prompt = f"""
    You are a data extraction assistant.
    Review these raw supply chain database query results: {db_results}
    
    Extract the structured citation list mapping each record to its source PO, Supplier, Part, Plant, affected Product, and a brief description of status/risk.
    
    Reply strictly conforming to the CitationList JSON schema.
    """
    
    try:
        citations_response = client.models.generate_content(
            model=MODEL_NAME,
            contents=citations_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CitationList,
                temperature=0.0
            )
        )
        citations_data = CitationList.model_validate_json(citations_response.text)
        citations = citations_data.citations
    except Exception:
        citations = []

    # 6. Return payload
    return {
        "question": question,
        "cypher_query": cypher_query,
        "traversal_steps": translation_data.traversal_steps,
        "raw_results": db_results,
        "highlighted_nodes": highlighted_nodes,
        "response_text": response_text,
        "citations": citations
    }

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serve the index.html dashboard template."""
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend file not found.")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
