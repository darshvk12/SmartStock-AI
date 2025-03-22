from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import os
from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a random secret key in production

# Database setup
def get_db_connection():
    conn = sqlite3.connect('grocery_store.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    ''')
    
    # Create inventory table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        vendor TEXT NOT NULL
    )
    ''')
    
    # Create vendors table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT NOT NULL,
        address TEXT NOT NULL,
        categories TEXT NOT NULL
    )
    ''')
    
    # Create sales table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        date TEXT NOT NULL,
        items TEXT NOT NULL,
        total REAL NOT NULL,
        customer_name TEXT,
        customer_phone TEXT,
        payment_status TEXT NOT NULL,
        cashier TEXT NOT NULL
    )
    ''')
    
    # Insert default admin and cashier users if they don't exist
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      ('admin', generate_password_hash('admin123'), 'admin'))
    
    cursor.execute("SELECT * FROM users WHERE username = 'cashier'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      ('cashier', generate_password_hash('cashier123'), 'cashier'))
    
    # Insert sample inventory data if table is empty
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        sample_inventory = [
            ('Rice', 'Grains', 25.99, 150, 'Global Foods'),
            ('Milk', 'Dairy', 3.99, 80, 'Farm Fresh'),
            ('Bread', 'Bakery', 2.49, 45, 'City Bakery'),
            ('Apples', 'Fruits', 1.99, 200, 'Organic Farms'),
            ('Chicken', 'Meat', 7.99, 30, 'Premium Meats')
        ]
        cursor.executemany("INSERT INTO inventory (name, category, price, stock, vendor) VALUES (?, ?, ?, ?, ?)",
                          sample_inventory)
    
    # Insert sample vendor data if table is empty
    cursor.execute("SELECT COUNT(*) FROM vendors")
    if cursor.fetchone()[0] == 0:
        sample_vendors = [
            ('Global Foods', 'John Smith', '555-123-4567', 'john@globalfoods.com', 
             '123 Main St, Anytown, USA', 'Grains,Canned Goods,Spices'),
            ('Farm Fresh', 'Mary Johnson', '555-987-6543', 'mary@farmfresh.com', 
             '456 Rural Rd, Countryside, USA', 'Dairy,Produce,Eggs'),
            ('City Bakery', 'Robert Davis', '555-456-7890', 'robert@citybakery.com', 
             '789 Urban Ave, Metropolis, USA', 'Bakery,Desserts'),
            ('Organic Farms', 'Sarah Wilson', '555-789-0123', 'sarah@organicfarms.com', 
             '101 Green Ln, Ecoville, USA', 'Fruits,Vegetables,Organic'),
            ('Premium Meats', 'Michael Brown', '555-234-5678', 'michael@premiummeats.com', 
             '202 Butcher St, Meatville, USA', 'Meat,Poultry,Seafood')
        ]
        cursor.executemany('''
        INSERT INTO vendors (name, contact, phone, email, address, categories) 
        VALUES (?, ?, ?, ?, ?, ?)''', sample_vendors)
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Routes
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        
        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('cashier_dashboard'))
    else:
        flash('Invalid username or password')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Admin routes
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    return render_template('admin/dashboard.html')

@app.route('/admin/inventory')
def admin_inventory():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    inventory = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    
    return render_template('admin/inventory.html', inventory=inventory)

@app.route('/admin/inventory/add', methods=['POST'])
def add_inventory():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO inventory (name, category, price, stock, vendor)
    VALUES (?, ?, ?, ?, ?)
    ''', (data['name'], data['category'], data['price'], data['stock'], data['vendor']))
    
    item_id = cursor.lastrowid
    conn.commit()
    
    item = conn.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    
    return jsonify({
        'success': True,
        'item': {
            'id': item['id'],
            'name': item['name'],
            'category': item['category'],
            'price': item['price'],
            'stock': item['stock'],
            'vendor': item['vendor']
        }
    })

@app.route('/admin/inventory/update/<int:item_id>', methods=['POST'])
def update_inventory(item_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    
    conn = get_db_connection()
    conn.execute('''
    UPDATE inventory
    SET stock = stock + ?
    WHERE id = ?
    ''', (data['quantity'], item_id))
    conn.commit()
    
    item = conn.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    
    return jsonify({
        'success': True,
        'item': {
            'id': item['id'],
            'name': item['name'],
            'category': item['category'],
            'price': item['price'],
            'stock': item['stock'],
            'vendor': item['vendor']
        }
    })

@app.route('/admin/inventory/delete/<int:item_id>', methods=['POST'])
def delete_inventory(item_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    conn.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/vendors')
def admin_vendors():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    vendors = conn.execute('SELECT * FROM vendors').fetchall()
    conn.close()
    
    return render_template('admin/vendors.html', vendors=vendors)

@app.route('/admin/vendors/add', methods=['POST'])
def add_vendor():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO vendors (name, contact, phone, email, address, categories)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['name'], data['contact'], data['phone'], data['email'], data['address'], data['categories']))
    
    vendor_id = cursor.lastrowid
    conn.commit()
    
    vendor = conn.execute('SELECT * FROM vendors WHERE id = ?', (vendor_id,)).fetchone()
    conn.close()
    
    return jsonify({
        'success': True,
        'vendor': {
            'id': vendor['id'],
            'name': vendor['name'],
            'contact': vendor['contact'],
            'phone': vendor['phone'],
            'email': vendor['email'],
            'address': vendor['address'],
            'categories': vendor['categories']
        }
    })

@app.route('/admin/vendors/delete/<int:vendor_id>', methods=['POST'])
def delete_vendor(vendor_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    conn.execute('DELETE FROM vendors WHERE id = ?', (vendor_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/sales')
def admin_sales():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    sales = conn.execute('SELECT * FROM sales ORDER BY date DESC').fetchall()
    
    # Process sales data for charts
    monthly_sales = {}
    category_sales = {}
    total_sales = 0
    pending_count = 0
    
    for sale in sales:
        # Parse date
        date = datetime.strptime(sale['date'], '%Y-%m-%d %H:%M:%S')
        month = date.strftime('%b')
        
        # Add to monthly sales
        if month in monthly_sales:
            monthly_sales[month] += sale['total']
        else:
            monthly_sales[month] = sale['total']
        
        # Add to total sales
        total_sales += sale['total']
        
        # Count pending payments
        if sale['payment_status'] == 'pending':
            pending_count += 1
        
        # Add to category sales
        try:
            items = json.loads(sale['items'])
            for item in items:
                category = item.get('category', 'Other')
                if category in category_sales:
                    category_sales[category] += item.get('subtotal', 0)
                else:
                    category_sales[category] = item.get('subtotal', 0)
        except (json.JSONDecodeError, TypeError):
            # Handle case where items is not valid JSON
            pass
    
    conn.close()
    
    # Calculate average sale
    average_sale = 0
    if len(sales) > 0:
        average_sale = round(total_sales / len(sales), 2)
    
    # Format total sales
    total_sales = round(total_sales, 2)
    
    # Prepare data for charts
    monthly_data = {
        'labels': list(monthly_sales.keys()),
        'values': list(monthly_sales.values())
    }
    
    category_data = {
        'labels': list(category_sales.keys()),
        'values': list(category_sales.values())
    }
    
    return render_template('admin/sales.html', 
                          sales=sales, 
                          total_sales=total_sales,
                          average_sale=average_sale,
                          pending_count=pending_count,
                          monthly_data=monthly_data,
                          category_data=category_data)

# Cashier routes
@app.route('/cashier/dashboard')
def cashier_dashboard():
    if 'user_id' not in session or session['role'] != 'cashier':
        return redirect(url_for('index'))
    return render_template('cashier/dashboard.html')

@app.route('/cashier/pos')
def cashier_pos():
    if 'user_id' not in session or session['role'] != 'cashier':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    inventory = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    
    return render_template('cashier/pos.html', inventory=inventory)

@app.route('/cashier/inventory/get')
def get_inventory():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    inventory = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    
    inventory_list = []
    for item in inventory:
        inventory_list.append({
            'id': item['id'],
            'name': item['name'],
            'category': item['category'],
            'price': item['price'],
            'stock': item['stock'],
            'vendor': item['vendor']
        })
    
    return jsonify({'success': True, 'inventory': inventory_list})

@app.route('/cashier/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session or session['role'] != 'cashier':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    cart_items = data['items']
    customer = data['customer']
    total = data['total']
    
    # Generate invoice number
    now = datetime.now()
    date_str = now.strftime('%Y%m%d')
    random_num = os.urandom(2).hex()
    invoice_number = f"INV-{date_str}-{random_num}"
    
    # Update inventory
    conn = get_db_connection()
    
    # Check if we have enough stock
    for item in cart_items:
        current_stock = conn.execute('SELECT stock FROM inventory WHERE id = ?', 
                                    (item['id'],)).fetchone()['stock']
        if current_stock < item['quantity']:
            conn.close()
            return jsonify({
                'success': False,
                'message': f"Not enough stock for {item['name']}. Only {current_stock} available."
            }), 400
    
    # Update stock levels
    for item in cart_items:
        conn.execute('UPDATE inventory SET stock = stock - ? WHERE id = ?', 
                    (item['quantity'], item['id']))
        
        # Check if stock is low and needs reordering
        new_stock = conn.execute('SELECT stock, vendor FROM inventory WHERE id = ?', 
                                (item['id'],)).fetchone()
        if new_stock['stock'] <= 5:
            # In a real app, this would trigger an order to the vendor
            print(f"Low stock alert: {item['name']} is low on stock. Vendor: {new_stock['vendor']}")
    
    # Save sale
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO sales (invoice_number, date, items, total, customer_name, customer_phone, payment_status, cashier)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        invoice_number,
        now.strftime('%Y-%m-%d %H:%M:%S'),
        json.dumps(cart_items),
        total,
        customer['name'],
        customer['phone'],
        customer['paymentStatus'],
        session['username']
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'invoice_number': invoice_number
    })

@app.route('/cashier/customers')
def cashier_customers():
    if 'user_id' not in session or session['role'] != 'cashier':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    pending_accounts = conn.execute('''
    SELECT * FROM sales 
    WHERE payment_status = 'pending' 
    ORDER BY date DESC
    ''').fetchall()
    conn.close()
    
    return render_template('cashier/customers.html', accounts=pending_accounts)

@app.route('/cashier/customers/mark-paid/<invoice_number>', methods=['POST'])
def mark_paid(invoice_number):
    if 'user_id' not in session or session['role'] != 'cashier':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    conn.execute('''
    UPDATE sales
    SET payment_status = 'paid'
    WHERE invoice_number = ?
    ''', (invoice_number,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
