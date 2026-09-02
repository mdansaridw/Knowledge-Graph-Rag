import os
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase
import pandas as pd

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

DATA_DIR = Path(__file__).resolve().parent

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

def get_driver():
    """Create and return a Neo4j database driver instance."""
    clean_uri = normalize_uri(URI)
    if not clean_uri or not USERNAME or not PASSWORD or clean_uri == "your-neo4j-uri":
        raise ValueError(
            "Neo4j connection credentials are not configured or contain placeholder values. "
            "Please update NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD in your .env file."
        )
    return GraphDatabase.driver(clean_uri, auth=(USERNAME, PASSWORD))

def get_cleaned_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to records with NaN/null values replaced with Python None."""
    records = df.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None
    return records

def upload_nodes_and_relationships():
    """Ingest CSV datasets into Neo4j nodes and directed relationships."""
    try:
        driver = get_driver()
        driver.verify_connectivity()
    except Exception as e:
        print(f"\n[ERROR] Unable to connect to Neo4j: {e}")
        print("\nPlease check the following:")
        print("  1. Your .env file exists and contains valid NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD values.")
        print("  2. If using Neo4j Aura, ensure your database instance is active (not paused/deleted).")
        print("  3. The URI format is correct (e.g., neo4j+s://<instance-id>.databases.neo4j.io or bolt://localhost:7687).")
        return

    with driver.session() as session:
        print("Connected to Neo4j. Clearing existing data...")
        session.run("MATCH (n) DETACH DELETE n")

        # 1. Ingest Suppliers
        print("Uploading Suppliers...")
        suppliers_df = pd.read_csv(DATA_DIR / "suppliers.csv")
        suppliers_records = get_cleaned_records(suppliers_df)
        suppliers_query = """
        UNWIND $rows AS row
        MERGE (s:Supplier {id: row.supplier_id})
        SET s.name = row.name, 
            s.location = row.location, 
            s.risk_rating = row.risk_rating
        """
        session.run(suppliers_query, rows=suppliers_records)

        # 2. Ingest Parts
        print("Uploading Parts...")
        parts_df = pd.read_csv(DATA_DIR / "parts.csv")
        parts_records = get_cleaned_records(parts_df)
        parts_query = """
        UNWIND $rows AS row
        MERGE (p:Part {id: row.part_id})
        SET p.name = row.name, 
            p.category = row.category, 
            p.unit_price = toFloat(row.unit_price), 
            p.criticality = row.criticality
        """
        session.run(parts_query, rows=parts_records)

        # 3. Ingest Manufacturing Plants
        print("Uploading Plants...")
        plants_df = pd.read_csv(DATA_DIR / "plants.csv")
        plants_records = get_cleaned_records(plants_df)
        plants_query = """
        UNWIND $rows AS row
        MERGE (pl:Plant {id: row.plant_id})
        SET pl.name = row.name, 
            pl.location = row.location
        """
        session.run(plants_query, rows=plants_records)

        # 4. Ingest Products and MANUFACTURES Relationships
        print("Uploading Products and MANUFACTURES relationships...")
        products_df = pd.read_csv(DATA_DIR / "products.csv")
        products_records = get_cleaned_records(products_df)
        products_query = """
        UNWIND $rows AS row
        MERGE (pr:Product {id: row.product_id})
        SET pr.name = row.name, 
            pr.customer = row.customer
        WITH pr, row
        MATCH (pl:Plant {id: row.plant_id})
        MERGE (pl)-[:MANUFACTURES]->(pr)
        """
        session.run(products_query, rows=products_records)

        # 5. Ingest Bill of Materials (BOM) Relationships
        print("Uploading Bill of Materials relationships...")
        bom_df = pd.read_csv(DATA_DIR / "bom.csv")
        bom_records = get_cleaned_records(bom_df)
        bom_query = """
        UNWIND $rows AS row
        MATCH (p:Part {id: row.part_id})
        MATCH (pr:Product {id: row.product_id})
        MERGE (p)-[r:USED_IN]->(pr)
        SET r.quantity_required = toInteger(row.quantity_required)
        """
        session.run(bom_query, rows=bom_records)

        # 6. Ingest Purchase Orders and Multi-Node Relationships
        print("Uploading Purchase Orders and linking relationships...")
        purchase_orders_df = pd.read_csv(DATA_DIR / "purchase_orders.csv")
        po_records = get_cleaned_records(purchase_orders_df)
        po_query = """
        UNWIND $rows AS row
        MERGE (po:PurchaseOrder {id: row.po_id})
        SET po.quantity = toInteger(row.quantity),
            po.order_date = row.order_date,
            po.expected_delivery_date = row.expected_delivery_date,
            po.actual_delivery_date = row.actual_delivery_date
        
        WITH po, row
        MATCH (s:Supplier {id: row.supplier_id})
        MERGE (s)-[:ISSUED_PO]->(po)
        
        WITH po, row
        MATCH (p:Part {id: row.part_id})
        MERGE (po)-[:ORDERS_PART]->(p)
        
        WITH po, row
        MATCH (pl:Plant {id: row.plant_id})
        MERGE (po)-[:DELIVERED_TO]->(pl)
        """
        session.run(po_query, rows=po_records)
        
    print("\nData ingestion complete.")
    driver.close()

if __name__ == "__main__":
    upload_nodes_and_relationships()
