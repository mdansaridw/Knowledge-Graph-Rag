from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

np.random.seed(42)

DATA_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------
# 1. GENERATE SUPPLIERS
# ---------------------------------------------------------
suppliers_data = {
    "supplier_id": [f"SUP{i:03d}" for i in range(1, 11)],
    "name": [
        "Supplier Alpha", "Supplier Beta", "Supplier Gamma", "Supplier Delta",
        "Supplier Epsilon", "Supplier Zeta", "Supplier Eta", "Supplier Theta",
        "Supplier Iota", "Supplier Kappa"
    ],
    "location": ["USA", "USA", "USA", "USA", "South Korea", "Taiwan", "Germany", "Switzerland", "USA", "Switzerland"],
    "risk_rating": ["Low", "Medium", "Low", "Low", "Low", "Medium", "Low", "Medium", "Low", "High"]
}
suppliers_df = pd.DataFrame(suppliers_data)

# ---------------------------------------------------------
# 2. GENERATE PARTS
# ---------------------------------------------------------
parts_data = {
    "part_id": [f"PART{i:03d}" for i in range(1, 16)],
    "name": [
        "STM32 Microcontroller", "ARM Cortex Processor", "10uF Capacitor", 
        "10k Ohm Resistor", "USB-C Connector", "Bluetooth Module", 
        "Wi-Fi Transceiver", "Power Management IC", "Voltage Regulator", 
        "HDMI Port", "8GB DDR4 RAM", "256GB SSD Flash", "LED Driver", 
        "Temperature Sensor", "Ethernet Controller"
    ],
    "category": [
        "Semiconductor", "Semiconductor", "Passive", "Passive", "Connector",
        "RF Module", "RF Module", "Semiconductor", "Semiconductor", "Connector",
        "Memory", "Memory", "Semiconductor", "Sensor", "Semiconductor"
    ],
    "unit_price": [12.50, 45.00, 0.05, 0.02, 1.20, 5.50, 7.20, 3.80, 1.50, 2.10, 35.00, 55.00, 2.20, 1.80, 4.50],
    "criticality": ["High", "High", "Low", "Low", "Medium", "High", "High", "High", "Medium", "Medium", "High", "High", "Low", "Medium", "High"]
}
parts_df = pd.DataFrame(parts_data)

# ---------------------------------------------------------
# 3. GENERATE MANUFACTURING PLANTS
# ---------------------------------------------------------
plants_data = {
    "plant_id": [f"PLANT{i:03d}" for i in range(1, 5)],
    "name": ["Manufacturing Plant A", "Manufacturing Plant B", "Manufacturing Plant C", "Manufacturing Plant D"],
    "location": ["USA", "China", "Mexico", "Germany"]
}
plants_df = pd.DataFrame(plants_data)

# ---------------------------------------------------------
# 4. GENERATE PRODUCTS
# ---------------------------------------------------------
products_data = {
    "product_id": [f"PROD{i:03d}" for i in range(1, 6)],
    "name": ["Smart Gateway", "Medical Monitor", "EV Charging Controller", "Industrial Switch", "Server Board"],
    "customer": ["Customer A", "Customer B", "Customer C", "Customer D", "Customer E"],
    "plant_id": ["PLANT001", "PLANT002", "PLANT003", "PLANT004", "PLANT001"]
}
products_df = pd.DataFrame(products_data)

# ---------------------------------------------------------
# 5. GENERATE BILL OF MATERIALS (BOM)
# ---------------------------------------------------------
bom_records = []
product_parts_map = {
    "PROD001": ["PART001", "PART003", "PART004", "PART005", "PART006", "PART009"],
    "PROD002": ["PART002", "PART003", "PART004", "PART008", "PART014", "PART015"],
    "PROD003": ["PART001", "PART003", "PART008", "PART009", "PART014"],
    "PROD004": ["PART002", "PART003", "PART004", "PART005", "PART007", "PART015"],
    "PROD005": ["PART002", "PART003", "PART004", "PART008", "PART010", "PART011", "PART012", "PART015"]
}

for prod_id, part_list in product_parts_map.items():
    for part_id in part_list:
        qty = 1
        if part_id in ["PART003", "PART004"]:
            qty = int(np.random.randint(5, 20))
        bom_records.append({
            "product_id": prod_id,
            "part_id": part_id,
            "quantity_required": qty
        })
bom_df = pd.DataFrame(bom_records)

# ---------------------------------------------------------
# 6. GENERATE PURCHASE ORDERS (POs)
# ---------------------------------------------------------
po_records = []
start_date = datetime(2026, 1, 1)

supplier_parts = {
    "SUP001": ["PART001", "PART003", "PART004", "PART005", "PART010", "PART014"],
    "SUP002": ["PART003", "PART004", "PART006", "PART007", "PART010", "PART013"],
    "SUP003": ["PART001", "PART008", "PART009", "PART013"],
    "SUP004": ["PART002", "PART015"],
    "SUP005": ["PART011", "PART012"],
    "SUP006": ["PART001", "PART002"],
    "SUP007": ["PART008", "PART009", "PART013"],
    "SUP008": ["PART001", "PART008", "PART014"],
    "SUP009": ["PART002", "PART015"],
    "SUP010": ["PART005", "PART010"]
}

for po_num in range(1, 41):
    po_id = f"PO{po_num:05d}"
    supp_id = np.random.choice(list(supplier_parts.keys()))
    part_id = np.random.choice(supplier_parts[supp_id])
    plant_id = np.random.choice(plants_df["plant_id"].values)
    qty = int(np.random.choice([100, 500, 1000, 5000, 10000]))
    
    days_offset = int(np.random.randint(0, 150))
    ord_date = start_date + timedelta(days=days_offset)
    
    lead_time = int(np.random.randint(14, 30))
    exp_delivery = ord_date + timedelta(days=lead_time)
    
    delivery_roll = float(np.random.rand())
    if delivery_roll < 0.70:
        actual_offset = int(np.random.randint(-5, 1))
        act_delivery = exp_delivery + timedelta(days=actual_offset)
        act_delivery_str = act_delivery.strftime("%Y-%m-%d")
    elif delivery_roll < 0.90:
        actual_offset = int(np.random.randint(1, 15))
        act_delivery = exp_delivery + timedelta(days=actual_offset)
        act_delivery_str = act_delivery.strftime("%Y-%m-%d")
    else:
        act_delivery_str = ""
    
    po_records.append({
        "po_id": po_id,
        "supplier_id": supp_id,
        "part_id": part_id,
        "plant_id": plant_id,
        "quantity": qty,
        "order_date": ord_date.strftime("%Y-%m-%d"),
        "expected_delivery_date": exp_delivery.strftime("%Y-%m-%d"),
        "actual_delivery_date": act_delivery_str
    })

purchase_orders_df = pd.DataFrame(po_records)

# ---------------------------------------------------------
# 7. SAVE DATASETS TO CSV
# ---------------------------------------------------------
suppliers_df.to_csv(DATA_DIR / "suppliers.csv", index=False)
parts_df.to_csv(DATA_DIR / "parts.csv", index=False)
plants_df.to_csv(DATA_DIR / "plants.csv", index=False)
products_df.to_csv(DATA_DIR / "products.csv", index=False)
bom_df.to_csv(DATA_DIR / "bom.csv", index=False)
purchase_orders_df.to_csv(DATA_DIR / "purchase_orders.csv", index=False)

print("Supply chain mock data generated successfully.")
