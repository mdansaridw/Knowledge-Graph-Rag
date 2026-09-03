import os
import warnings
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase
from google import genai
from google.genai import types


warnings.filterwarnings("ignore")
logging.getLogger("google.genai").setLevel(logging.ERROR)

load_dotenv()

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

def get_db_driver():
    """Return a connected Neo4j driver instance."""
    clean_uri = normalize_uri(URI)
    return GraphDatabase.driver(clean_uri, auth=(USERNAME, PASSWORD))

def get_gemini_client():
    """Initialize and return the Gemini API client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set. Please configure it in your environment or .env file.")
    return genai.Client(api_key=api_key)

GRAPH_SCHEMA = """
Database Property Graph Schema:
1. Nodes:
   - :Supplier {id: STRING, name: STRING, location: STRING, risk_rating: STRING ("Low", "Medium", "High")}
   - :Part {id: STRING, name: STRING, category: STRING, unit_price: FLOAT, criticality: STRING ("Low", "Medium", "High")}
   - :Product {id: STRING, name: STRING, customer: STRING}
   - :Plant {id: STRING, name: STRING, location: STRING}
   - :PurchaseOrder {id: STRING, quantity: INTEGER, order_date: STRING (YYYY-MM-DD), expected_delivery_date: STRING (YYYY-MM-DD), actual_delivery_date: STRING (YYYY-MM-DD or empty)}

2. Relationships (directed):
   - (s:Supplier)-[:ISSUED_PO]->(po:PurchaseOrder)
   - (po:PurchaseOrder)-[:ORDERS_PART]->(p:Part)
   - (po:PurchaseOrder)-[:DELIVERED_TO]->(pl:Plant)
   - (pl:Plant)-[:MANUFACTURES]->(pr:Product)
   - (p:Part)-[:USED_IN {quantity_required: INTEGER}]->(pr:Product)

Dynamic properties computed on nodes/edges:
- PurchaseOrder has a computed property 'status' which is:
  * "Pending" if actual_delivery_date is empty/null.
  * "On-Time" if actual_delivery_date <= expected_delivery_date.
  * "Late" if actual_delivery_date > expected_delivery_date.
- PurchaseOrder value can be calculated dynamically inside a query as: po.quantity * part.unit_price (linked via ORDERS_PART)
"""

def generate_cypher(question: str) -> str:
    """Translate a natural language question into a Cypher query using Gemini."""
    client = get_gemini_client()
    system_instruction = f"""
    You are an expert Cypher query generator for a Neo4j graph database.
    Your task is to translate natural language questions about the supply chain into precise Cypher queries.
    
    {GRAPH_SCHEMA}
    
    CRITICAL RULES:
    1. Reply ONLY with the raw Cypher query. Do not wrap it in backticks (e.g., do NOT use ```cypher or ```) and do not write explanations.
    2. Strictly do not add SQL syntax like OVER.
    3. Verify relationship directions. For example, Supplier points TO PurchaseOrder: (s:Supplier)-[:ISSUED_PO]->(po:PurchaseOrder).
    4. Make string searches case-insensitive if appropriate by using toLower() or regex matches.
    5. For date comparisons, compare them as strings since they are formatted as YYYY-MM-DD.
    6. Always return meaningful nodes or properties (e.g., return s.name, po.id, p.name rather than just return s).
    """

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0
        )
    )
    
    query = response.text.strip()
    if query.startswith("```"):
        query = query.split("\n", 1)[1]
        if query.endswith("```"):
            query = query.rsplit("\n", 1)[0]
    query = query.replace("`", "").strip()
    return query

def run_cypher_query(cypher_query: str) -> list[dict]:
    """Execute the Cypher query on Neo4j and return records as dictionaries."""
    driver = get_db_driver()
    results = []
    
    with driver.session() as session:
        result = session.run(cypher_query)
        for record in result:
            results.append(record.data())
            
    driver.close()
    return results

def synthesize_answer(question: str, cypher_query: str, query_results: list[dict]) -> str:
    """Synthesize database query results into a professional supply chain analyst answer."""
    client = get_gemini_client()
    prompt = f"""
    You are a Supply Chain Analyst.
    
    The user asked the following question:
    "{question}"
    
    To find the answer, we ran this Cypher query on the graph database:
    {cypher_query}
    
    The database returned the following results:
    {query_results}
    
    Write a clear, professional, and conversational response to the user:
    1. Directly answer the question based on the database results.
    2. Cite specific Purchase Orders, Suppliers, Parts, or Plants.
    3. Explain the business context or implications (e.g., if a part is late, explain that it affects manufacturing).
    4. If the results are empty, state that no records match the criteria, and explain why.
    """
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4
        )
    )
    
    return response.text.strip()

def run_rag_pipeline(question: str):
    """Execute the end-to-end GraphRAG pipeline for a given query."""
    print(f"\n[1/4] User Question: '{question}'")
    
    cypher_query = generate_cypher(question)
    print(f"[2/4] Generated Cypher Query:\n{cypher_query}")
    
    try:
        raw_results = run_cypher_query(cypher_query)
        print(f"[3/4] Database Results: {raw_results}")
        
        final_answer = synthesize_answer(question, cypher_query, raw_results)
        print(f"\n[4/4] Analyst Response:\n{final_answer}\n")
        return final_answer
    except Exception as e:
        print(f"\n[ERROR] Failed to execute query: {e}")
        return None

if __name__ == "__main__":
    print("=== Supply Chain GraphRAG System ===")
    print("Type your question below (or 'exit' to quit).\n")
    
    while True:
        user_q = input("Ask a question: ").strip()
        if user_q.lower() in ["exit", "quit"]:
            break
        if not user_q:
            continue
        run_rag_pipeline(user_q)
        print("-" * 60)
