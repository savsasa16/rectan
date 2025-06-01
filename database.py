import sqlite3
from datetime import datetime
import pytz

def get_bkk_time():
    bkk_tz = pytz.timezone('Asia/Bangkok')
    return datetime.now(bkk_tz)

def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row # This allows accessing columns by name (e.g., row['column_name'])
    return conn

def init_db(conn):
    cursor = conn.cursor()

    # Create promotions table first
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,       -- ชื่อโปรโมชัน เช่น 'ซื้อ 3 แถม 1', 'ลด 25% ยางบางรุ่น'
            type TEXT NOT NULL,             -- ประเภทโปรโมชัน: 'buy_x_get_y', 'percentage_discount', 'fixed_price_per_n'
            value1 REAL NOT NULL,           -- ค่าแรก: X (สำหรับ buy_x_get_y), เปอร์เซ็นต์ (สำหรับ percentage_discount), ราคาคงที่ (สำหรับ fixed_price_per_n)
            value2 REAL NULL,               -- ค่าสอง: Y (สำหรับ buy_x_get_y), (null สำหรับอื่น)
            is_active BOOLEAN DEFAULT 1,    -- 1 = ใช้งาน, 0 = ไม่ใช้งาน
            created_at TEXT NOT NULL
        );
    """)

    # Modified tires table to link to promotions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            size TEXT NOT NULL,
            quantity INTEGER DEFAULT 0,
            cost_sc REAL NULL, 
            cost_dunlop REAL NULL,
            cost_online REAL NULL,
            wholesale_price1 REAL NULL,
            wholesale_price2 REAL NULL,
            price_per_item REAL NOT NULL,   -- Changed from retail_price
            promotion_id INTEGER NULL,      -- Link to promotions table
            year_of_manufacture INTEGER NULL,
            UNIQUE(brand, model, size),
            FOREIGN KEY (promotion_id) REFERENCES promotions(id) ON DELETE SET NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wheels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            diameter REAL NOT NULL,
            pcd TEXT NOT NULL,
            width REAL NOT NULL,
            et INTEGER NULL,
            color TEXT NULL,
            quantity INTEGER DEFAULT 0,
            cost REAL NULL, 
            cost_online REAL NULL,
            wholesale_price1 REAL NULL,
            wholesale_price2 REAL NULL,
            retail_price REAL NOT NULL, -- Keep retail_price for wheels
            image_filename TEXT NULL,
            UNIQUE(brand, model, diameter, pcd, width, et, color)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tire_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tire_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL, -- 'IN' or 'OUT'
            quantity_change INTEGER NOT NULL,
            remaining_quantity INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (tire_id) REFERENCES tires(id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wheel_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wheel_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL, -- 'IN' or 'OUT'
            quantity_change INTEGER NOT NULL,
            remaining_quantity INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (wheel_id) REFERENCES wheels(id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wheel_fitments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wheel_id INTEGER NOT NULL,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            year_start INTEGER NOT NULL,
            year_end INTEGER NULL,
            UNIQUE(wheel_id, brand, model, year_start, year_end),
            FOREIGN KEY (wheel_id) REFERENCES wheels(id) ON DELETE CASCADE
        );
    """)
    conn.commit()

# --- Promotion Functions ---
def add_promotion(conn, name, promo_type, value1, value2, is_active):
    created_at = get_bkk_time().isoformat()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO promotions (name, type, value1, value2, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, promo_type, value1, value2, is_active, created_at))
    conn.commit()
    return cursor.lastrowid

def get_promotion(conn, promo_id):
    cursor = conn.execute("SELECT * FROM promotions WHERE id = ?", (promo_id,))
    return cursor.fetchone()

def get_all_promotions(conn, include_inactive=False):
    sql_query = "SELECT * FROM promotions"
    params = []
    if not include_inactive:
        sql_query += " WHERE is_active = 1"
    sql_query += " ORDER BY name"
    cursor = conn.execute(sql_query, params)
    return cursor.fetchall()

def update_promotion(conn, promo_id, name, promo_type, value1, value2, is_active):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE promotions SET
            name = ?,
            type = ?,
            value1 = ?,
            value2 = ?,
            is_active = ?
        WHERE id = ?
    """, (name, promo_type, value1, value2, is_active, promo_id))
    conn.commit()

def delete_promotion(conn, promo_id):
    conn.execute("UPDATE tires SET promotion_id = NULL WHERE promotion_id = ?", (promo_id,))
    conn.execute("DELETE FROM promotions WHERE id = ?", (promo_id,))
    conn.commit()

# --- Tire Functions (Modified) ---
def add_tire(conn, brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tires (brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture))
    conn.commit()
    return cursor.lastrowid

def get_tire(conn, tire_id):
    cursor = conn.execute("""
        SELECT t.*, 
               p.name AS promo_name, 
               p.type AS promo_type, 
               p.value1 AS promo_value1, 
               p.value2 AS promo_value2,
               p.is_active AS promo_is_active
        FROM tires t
        LEFT JOIN promotions p ON t.promotion_id = p.id
        WHERE t.id = ?
    """, (tire_id,))
    tire = cursor.fetchone()
    
    if tire:
        tire_dict = dict(tire) 
        tire_dict['display_promo_price_per_item'] = None # Default to None
        tire_dict['display_price_for_4'] = tire_dict['price_per_item'] * 4 # Default for 4 items
        tire_dict['display_promo_description'] = None # Default description

        if tire_dict['promotion_id'] is not None and tire_dict['promo_is_active'] == 1:
            promo_calc_result = calculate_tire_promo_prices(
                tire_dict['price_per_item'],
                tire_dict['promo_type'],
                tire_dict['promo_value1'],
                tire_dict['promo_value2']
            )
            tire_dict['display_promo_price_per_item'] = promo_calc_result['price_per_item_promo']
            tire_dict['display_price_for_4'] = promo_calc_result['price_for_4_promo']
            tire_dict['display_promo_description'] = promo_calc_result['promo_description_text']
        
        return tire_dict 
    return tire

def update_tire(conn, tire_id, brand, model, size, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tires SET
            brand = ?,
            model = ?,
            size = ?,
            cost_sc = ?,
            cost_dunlop = ?,
            cost_online = ?,
            wholesale_price1 = ?,
            wholesale_price2 = ?,
            price_per_item = ?,
            promotion_id = ?,
            year_of_manufacture = ?
        WHERE id = ?
    """, (brand, model, size, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture, tire_id))
    conn.commit()

# Function for Import from Excel (updated for promotion_id and price_per_item)
def add_tire_import(conn, brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture): 
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tires (brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture))
    conn.commit()
    return cursor.lastrowid

def update_tire_import(conn, tire_id, brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture): 
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tires SET
            brand = ?,
            model = ?,
            size = ?,
            quantity = ?, 
            cost_sc = ?,
            cost_dunlop = ?,
            cost_online = ?,
            wholesale_price1 = ?,
            wholesale_price2 = ?,
            price_per_item = ?,
            promotion_id = ?,
            year_of_manufacture = ?
        WHERE id = ?
    """, (brand, model, size, quantity, cost_sc, cost_dunlop, cost_online, wholesale_price1, wholesale_price2, price_per_item, promotion_id, year_of_manufacture, tire_id))
    conn.commit()

# NEW: Unified function to calculate prices for display based on promo type
def calculate_tire_promo_prices(price_per_item, promo_type, promo_value1, promo_value2):
    price_per_item_promo = price_per_item
    price_for_4_promo = price_per_item * 4
    promo_description_text = None

    if price_per_item is None or promo_type is None:
        return {
            'price_per_item_promo': None, 
            'price_for_4_promo': price_per_item * 4 if price_per_item is not None else None,
            'promo_description_text': None
        }

    if promo_type == 'buy_x_get_y' and promo_value1 is not None and promo_value2 is not None:
        if (promo_value1 > 0 and promo_value2 >= 0):
            # Price for (X + Y) items = price_per_item * X
            # Price per item (promo) = (price_per_item * X) / (X + Y)
            # Price for 4 items (promo) = price_per_item_promo * 4
            if (promo_value1 + promo_value2) > 0: # Avoid division by zero
                price_per_item_promo = (price_per_item * promo_value1) / (promo_value1 + promo_value2)
                price_for_4_promo = price_per_item_promo * 4
                promo_description_text = f"ซื้อ {int(promo_value1)} แถม {int(promo_value2)} ฟรี"
            else: # If X+Y is 0, promo is invalid
                price_per_item_promo = None
                price_for_4_promo = None
                promo_description_text = "โปรไม่ถูกต้อง (X+Y=0)"
        else: # Invalid X or Y
            price_per_item_promo = None
            price_for_4_promo = None
            promo_description_text = "โปรไม่ถูกต้อง (X,Y<=0)"
    
    elif promo_type == 'percentage_discount' and promo_value1 is not None:
        if (promo_value1 >= 0 and promo_value1 <= 100):
            price_per_item_promo = price_per_item * (1 - (promo_value1 / 100))
            price_for_4_promo = price_per_item_promo * 4
            promo_description_text = f"ลด {promo_value1}%"
        else: # Invalid percentage
            price_per_item_promo = None
            price_for_4_promo = None
            promo_description_text = "โปรไม่ถูกต้อง (%ไม่ถูกต้อง)"
    
    elif promo_type == 'fixed_price_per_n' and promo_value1 is not None and promo_value2 is not None:
        # promo_value1 is fixed price for promo_value2 items
        # Example: 3 items for $2900 (Value1=2900, Value2=3)
        if promo_value2 > 0:
            price_per_item_promo = promo_value1 / promo_value2
            price_for_4_promo = price_per_item_promo * 4
            promo_description_text = f"ราคา {promo_value1:.2f} บาท สำหรับ {int(promo_value2)} เส้น"
        else: # Invalid N
            price_per_item_promo = None
            price_for_4_promo = None
            promo_description_text = "โปรไม่ถูกต้อง (N<=0)"
            
    # Fallback to normal price if promo type is not recognized or values are invalid
    if price_per_item_promo is None:
        price_per_item_promo = price_per_item
        price_for_4_promo = price_per_item * 4
        promo_description_text = None

    return {
        'price_per_item_promo': price_per_item_promo, 
        'price_for_4_promo': price_for_4_promo,
        'promo_description_text': promo_description_text
    }


def get_all_tires(conn, query=None, brand_filter='all'):
    sql_query = """
        SELECT t.*, 
               p.name AS promo_name, 
               p.type AS promo_type, 
               p.value1 AS promo_value1, 
               p.value2 AS promo_value2,
               p.is_active AS promo_is_active
        FROM tires t
        LEFT JOIN promotions p ON t.promotion_id = p.id
    """
    params = []
    conditions = []

    if query:
        search_term = f"%{query}%"
        conditions.append("(t.brand LIKE ? OR t.model LIKE ? OR t.size LIKE ?)")
        params.extend([search_term, search_term, search_term])
    
    if brand_filter != 'all':
        conditions.append("t.brand = ?")
        params.append(brand_filter)
    
    if conditions:
        sql_query += " WHERE " + " AND ".join(conditions)
    
    sql_query += " ORDER BY t.brand, t.model, t.size"
    
    cursor = conn.execute(sql_query, params)
    tires = cursor.fetchall()

    processed_tires = []
    for tire in tires:
        tire_dict = dict(tire) 
        
        # Calculate display prices for each tire
        promo_calc_result = {
            'price_per_item_promo': None, 
            'price_for_4_promo': tire_dict['price_per_item'] * 4 if tire_dict['price_per_item'] is not None else None,
            'promo_description_text': None
        }

        if tire_dict['promotion_id'] is not None and tire_dict['promo_is_active'] == 1:
            promo_calc_result = calculate_tire_promo_prices(
                tire_dict['price_per_item'], 
                tire_dict['promo_type'], 
                tire_dict['promo_value1'], 
                tire_dict['promo_value2']
            )
        
        tire_dict['display_promo_price_per_item'] = promo_calc_result['price_per_item_promo']
        tire_dict['display_price_for_4'] = promo_calc_result['price_for_4_promo']
        tire_dict['display_promo_description_text'] = promo_calc_result['promo_description_text']
        
        processed_tires.append(tire_dict)
    
    return processed_tires

def update_tire_quantity(conn, tire_id, new_quantity):
    conn.execute("UPDATE tires SET quantity = ? WHERE id = ?", (new_quantity, tire_id))
    conn.commit()

def add_tire_movement(conn, tire_id, move_type, quantity_change, remaining_quantity, notes):
    timestamp = get_bkk_time().isoformat()
    conn.execute("""
        INSERT INTO tire_movements (tire_id, timestamp, type, quantity_change, remaining_quantity, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (tire_id, timestamp, move_type, quantity_change, remaining_quantity, notes))
    conn.commit()

def delete_tire(conn, tire_id):
    conn.execute("DELETE FROM tires WHERE id = ?", (tire_id,))
    conn.commit()

def get_all_tire_brands(conn):
    cursor = conn.execute("SELECT DISTINCT brand FROM tires ORDER BY brand")
    return [row['brand'] for row in cursor.fetchall()]

# --- Wheel Functions ---
def get_all_wheels(conn, query=None, brand_filter='all'):
    sql_query = "SELECT * FROM wheels"
    params = []
    conditions = []

    if query:
        search_term = f"%{query}%"
        conditions.append("(brand LIKE ? OR model LIKE ? OR pcd LIKE ? OR color LIKE ?)")
        params.extend([search_term, search_term, search_term, search_term])
    
    if brand_filter != 'all':
        conditions.append("brand = ?")
        params.append(brand_filter)
    
    if conditions:
        sql_query += " WHERE " + " AND ".join(conditions)
    
    sql_query += " ORDER BY brand, model, diameter"
    
    cursor = conn.execute(sql_query, params)
    return cursor.fetchall()

def get_wheel(conn, wheel_id):
    cursor = conn.execute("SELECT * FROM wheels WHERE id = ?", (wheel_id,))
    return cursor.fetchone()

def add_wheel(conn, brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO wheels (brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename))
    conn.commit()
    return cursor.lastrowid

def update_wheel(conn, wheel_id, brand, model, diameter, pcd, width, et, color, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE wheels SET
            brand = ?,
            model = ?,
            diameter = ?,
            pcd = ?,
            width = ?,
            et = ?,
            color = ?,
            cost = ?,
            cost_online = ?,
            wholesale_price1 = ?,
            wholesale_price2 = ?,
            retail_price = ?,
            image_filename = ?
        WHERE id = ?
    """, (brand, model, diameter, pcd, width, et, color, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename, wheel_id))
    conn.commit()

def add_wheel_import(conn, brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO wheels (brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename))
    conn.commit()
    return cursor.lastrowid

def update_wheel_import(conn, wheel_id, brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE wheels SET
            brand = ?,
            model = ?,
            diameter = ?,
            pcd = ?,
            width = ?,
            et = ?,
            color = ?,
            quantity = ?,
            cost = ?,
            cost_online = ?,
            wholesale_price1 = ?,
            wholesale_price2 = ?,
            retail_price = ?,
            image_filename = ?
        WHERE id = ?
    """, (brand, model, diameter, pcd, width, et, color, quantity, cost, cost_online, wholesale_price1, wholesale_price2, retail_price, image_filename, wheel_id))
    conn.commit()

def delete_wheel(conn, wheel_id):
    conn.execute("DELETE FROM wheels WHERE id = ?", (wheel_id,))
    conn.commit()

def get_all_wheel_brands(conn):
    cursor = conn.execute("SELECT DISTINCT brand FROM wheels ORDER BY brand")
    return [row['brand'] for row in cursor.fetchall()]

def add_wheel_fitment(conn, wheel_id, brand, model, year_start, year_end):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO wheel_fitments (wheel_id, brand, model, year_start, year_end)
        VALUES (?, ?, ?, ?, ?)
    """, (wheel_id, brand, model, year_start, year_end))
    conn.commit()

def get_wheel_fitments(conn, wheel_id):
    cursor = conn.execute("SELECT * FROM wheel_fitments WHERE wheel_id = ? ORDER BY brand, model, year_start", (wheel_id,))
    return cursor.fetchall()

def delete_wheel_fitment(conn, fitment_id):
    conn.execute("DELETE FROM wheel_fitments WHERE id = ?", (fitment_id,))
    conn.commit()