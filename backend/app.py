import os, sqlite3, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'returns.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-before-deployment')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
CORS(app, supports_credentials=True, origins=os.environ.get('FRONTEND_ORIGIN', 'http://localhost:5173').split(','))

ROLES = ['Customer Support Agent', 'Warehouse Inspector', 'Finance Officer', 'Returns Manager']
STATUSES = ['Requested', 'Inspection Pending', 'Approved', 'Rejected', 'Replacement Processing', 'Replacement Shipped', 'Refund Pending', 'Refund Completed', 'Closed']

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con

def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, order_ref TEXT UNIQUE NOT NULL, customer_name TEXT NOT NULL, email TEXT NOT NULL, product TEXT NOT NULL, amount REAL NOT NULL, order_date TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS returns(id INTEGER PRIMARY KEY AUTOINCREMENT, case_ref TEXT UNIQUE NOT NULL, order_id INTEGER NOT NULL REFERENCES orders(id), reason TEXT NOT NULL, details TEXT, requested_amount REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Requested', inspection_result TEXT, inspection_notes TEXT, decision_note TEXT, resolution TEXT, refund_amount REAL, refund_reference TEXT, refund_date TEXT, replacement_tracking TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, created_by INTEGER REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT, return_id INTEGER NOT NULL REFERENCES returns(id), user_name TEXT NOT NULL, action TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL);
    ''')
    if con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        users = [
          ('Alex Morgan','support@demo.com','Support@123','Customer Support Agent'),
          ('Jordan Lee','warehouse@demo.com','Warehouse@123','Warehouse Inspector'),
          ('Taylor Smith','finance@demo.com','Finance@123','Finance Officer'),
          ('Morgan Reed','manager@demo.com','Manager@123','Returns Manager')]
        con.executemany('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)', [(n,e,generate_password_hash(p),r) for n,e,p,r in users])
    if con.execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 0:
        today = datetime.now().date()
        samples = [
          ('ORD-2026-1001','Olivia Carter','olivia@example.com','Wireless Headphones',3499,today-timedelta(days=12)),
          ('ORD-2026-1002','Noah Wilson','noah@example.com','Smart Watch',5999,today-timedelta(days=8)),
          ('ORD-2026-1003','Ava Johnson','ava@example.com','Bluetooth Speaker',2499,today-timedelta(days=21)),
          ('ORD-2026-1004','Liam Brown','liam@example.com','Mechanical Keyboard',4299,today-timedelta(days=5)),
          ('ORD-2026-1005','Sophia Davis','sophia@example.com','USB-C Hub',1899,today-timedelta(days=16)),
          ('ORD-2026-1006','Ethan Miller','ethan@example.com','Fitness Band',2199,today-timedelta(days=30))]
        con.executemany('INSERT INTO orders(order_ref,customer_name,email,product,amount,order_date) VALUES(?,?,?,?,?,?)', [(a,b,c,d,e,f.isoformat()) for a,b,c,d,e,f in samples])
    con.commit(); con.close()

def current_user():
    if not session.get('user_id'): return None
    con=db(); u=con.execute('SELECT id,name,email,role FROM users WHERE id=?',(session['user_id'],)).fetchone(); con.close()
    return dict(u) if u else None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user(): return jsonify(error='Please sign in to continue.'),401
        return fn(*args, **kwargs)
    return wrapper

def roles(*allowed):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u=current_user()
            if not u: return jsonify(error='Please sign in to continue.'),401
            if u['role'] not in allowed: return jsonify(error='Your role does not have permission for this action.'),403
            return fn(*args, **kwargs)
        return wrapper
    return deco

def log(con, rid, user, action, note=''):
    con.execute('INSERT INTO activity(return_id,user_name,action,note,created_at) VALUES(?,?,?,?,?)',(rid,user['name'],action,note,datetime.now().isoformat(timespec='seconds')))

def rowdict(r): return dict(r) if r else None

@app.get('/api/health')
def health(): return jsonify(status='ok', application='Order Returns & Refund Case Manager')

@app.post('/api/login')
def login():
    data=request.get_json(silent=True) or {}; email=(data.get('email') or '').strip().lower(); password=data.get('password') or ''
    con=db(); u=con.execute('SELECT * FROM users WHERE lower(email)=?',(email,)).fetchone(); con.close()
    if not u or not check_password_hash(u['password'],password): return jsonify(error='Incorrect email or password.'),401
    session.clear(); session['user_id']=u['id']
    return jsonify(user={'id':u['id'],'name':u['name'],'email':u['email'],'role':u['role']})

@app.post('/api/logout')
@login_required
def logout(): session.clear(); return jsonify(message='Signed out.')

@app.get('/api/me')
@login_required
def me(): return jsonify(user=current_user())

@app.get('/api/orders/<order_ref>')
@login_required
def get_order(order_ref):
    con=db(); r=con.execute('SELECT * FROM orders WHERE upper(order_ref)=upper(?)',(order_ref.strip(),)).fetchone(); con.close()
    if not r: return jsonify(error='No order was found for that reference.'),404
    return jsonify(order=rowdict(r))

@app.get('/api/orders')
@login_required
def orders():
    con=db(); rows=con.execute('SELECT * FROM orders ORDER BY id DESC').fetchall(); con.close(); return jsonify(orders=[rowdict(r) for r in rows])

@app.post('/api/returns')
@roles('Customer Support Agent','Returns Manager')
def create_return():
    u=current_user(); d=request.get_json(silent=True) or {}; ref=(d.get('order_ref') or '').strip(); reason=(d.get('reason') or '').strip(); details=(d.get('details') or '').strip()
    if not ref or not reason: return jsonify(error='Order reference and return reason are required.'),400
    con=db(); order=con.execute('SELECT * FROM orders WHERE upper(order_ref)=upper(?)',(ref,)).fetchone()
    if not order: con.close(); return jsonify(error='Order reference is invalid. Please verify the order first.'),400
    existing=con.execute("SELECT id FROM returns WHERE order_id=? AND status NOT IN ('Rejected','Closed')",(order['id'],)).fetchone()
    if existing: con.close(); return jsonify(error='An active return case already exists for this order.'),409
    now=datetime.now().isoformat(timespec='seconds'); case='RET-'+datetime.now().strftime('%y%m%d')+'-'+secrets.token_hex(2).upper()
    cur=con.execute('INSERT INTO returns(case_ref,order_id,reason,details,requested_amount,status,created_at,updated_at,created_by) VALUES(?,?,?,?,?,?,?,?,?)',(case,order['id'],reason,details,order['amount'],'Inspection Pending',now,now,u['id']))
    rid=cur.lastrowid; log(con,rid,u,'Return request created',f'{case} created for {order["order_ref"]}')
    con.commit(); item=con.execute('SELECT r.*,o.order_ref,o.customer_name,o.email,o.product,o.amount AS order_amount FROM returns r JOIN orders o ON o.id=r.order_id WHERE r.id=?',(rid,)).fetchone(); con.close()
    return jsonify(return_case=rowdict(item)),201

@app.get('/api/returns')
@login_required
def list_returns():
    q=(request.args.get('q') or '').strip(); status=(request.args.get('status') or '').strip(); con=db()
    sql='SELECT r.*,o.order_ref,o.customer_name,o.email,o.product,o.amount AS order_amount FROM returns r JOIN orders o ON o.id=r.order_id WHERE 1=1'; args=[]
    if q: sql+=' AND (r.case_ref LIKE ? OR o.order_ref LIKE ? OR o.customer_name LIKE ? OR o.product LIKE ?)'; args += [f'%{q}%']*4
    if status: sql+=' AND r.status=?'; args.append(status)
    sql+=' ORDER BY r.created_at DESC'; rows=con.execute(sql,args).fetchall(); con.close(); return jsonify(returns=[rowdict(r) for r in rows])

@app.get('/api/returns/<int:rid>')
@login_required
def get_return(rid):
    con=db(); item=con.execute('SELECT r.*,o.order_ref,o.customer_name,o.email,o.product,o.amount AS order_amount FROM returns r JOIN orders o ON o.id=r.order_id WHERE r.id=?',(rid,)).fetchone()
    if not item: con.close(); return jsonify(error='Return case not found.'),404
    history=con.execute('SELECT * FROM activity WHERE return_id=? ORDER BY id DESC',(rid,)).fetchall(); con.close()
    return jsonify(return_case=rowdict(item),history=[rowdict(x) for x in history])

@app.post('/api/returns/<int:rid>/inspect')
@roles('Warehouse Inspector','Returns Manager')
def inspect(rid):
    d=request.get_json(silent=True) or {}; result=d.get('result'); notes=(d.get('notes') or '').strip()
    if result not in ['Pass','Fail','Needs Review']: return jsonify(error='Choose a valid inspection result.'),400
    con=db(); r=con.execute('SELECT * FROM returns WHERE id=?',(rid,)).fetchone()
    if not r: con.close(); return jsonify(error='Return case not found.'),404
    if r['status'] not in ['Inspection Pending','Requested']: con.close(); return jsonify(error='This case is not awaiting inspection.'),409
    status='Inspection Pending' if result=='Needs Review' else 'Requested'
    con.execute('UPDATE returns SET inspection_result=?,inspection_notes=?,status=?,updated_at=? WHERE id=?',(result,notes,status,datetime.now().isoformat(timespec='seconds'),rid))
    log(con,rid,current_user(),'Inspection recorded',f'{result}: {notes}')
    con.commit(); con.close(); return jsonify(message='Inspection saved.',inspection_result=result)

@app.post('/api/returns/<int:rid>/decision')
@roles('Returns Manager')
def decision(rid):
    d=request.get_json(silent=True) or {}; decision=d.get('decision'); resolution=d.get('resolution'); note=(d.get('note') or '').strip()
    if decision not in ['Approved','Rejected']: return jsonify(error='Decision must be Approved or Rejected.'),400
    if decision=='Approved' and resolution not in ['Refund','Replacement']: return jsonify(error='Choose Refund or Replacement as the resolution.'),400
    con=db(); r=con.execute('SELECT * FROM returns WHERE id=?',(rid,)).fetchone()
    if not r: con.close(); return jsonify(error='Return case not found.'),404
    if r['inspection_result'] not in ['Pass','Needs Review'] and decision=='Approved': con.close(); return jsonify(error='A passing inspection must be recorded before approval.'),409
    status=('Refund Pending' if resolution=='Refund' else 'Replacement Processing') if decision=='Approved' else 'Rejected'
    con.execute('UPDATE returns SET status=?,decision_note=?,resolution=?,updated_at=? WHERE id=?',(status,note,resolution if decision=='Approved' else None,datetime.now().isoformat(timespec='seconds'),rid))
    log(con,rid,current_user(),f'Return {decision.lower()}',note or (resolution or ''))
    con.commit(); con.close(); return jsonify(message='Decision saved.',status=status)

@app.post('/api/returns/<int:rid>/refund')
@roles('Finance Officer','Returns Manager')
def refund(rid):
    d=request.get_json(silent=True) or {}; amount=d.get('amount'); reference=(d.get('reference') or '').strip()
    try: amount=float(amount)
    except (TypeError,ValueError): return jsonify(error='Enter a valid refund amount.'),400
    con=db(); r=con.execute('SELECT * FROM returns WHERE id=?',(rid,)).fetchone()
    if not r: con.close(); return jsonify(error='Return case not found.'),404
    if r['status']!='Refund Pending': con.close(); return jsonify(error='This case is not awaiting a refund.'),409
    if amount<=0 or amount>r['requested_amount']: con.close(); return jsonify(error='Refund must be greater than zero and cannot exceed the order amount.'),400
    if not reference: con.close(); return jsonify(error='Enter the manual refund reference number.'),400
    now=datetime.now().isoformat(timespec='seconds'); con.execute("UPDATE returns SET refund_amount=?,refund_reference=?,refund_date=?,status='Refund Completed',updated_at=? WHERE id=?",(amount,reference,now,now,rid))
    log(con,rid,current_user(),'Manual refund recorded',f'₹{amount:.2f} | Reference: {reference}')
    con.commit(); con.close(); return jsonify(message='Manual refund recorded. No payment was initiated.',status='Refund Completed')

@app.post('/api/returns/<int:rid>/replacement')
@roles('Warehouse Inspector','Returns Manager')
def replacement(rid):
    d=request.get_json(silent=True) or {}; tracking=(d.get('tracking') or '').strip()
    con=db(); r=con.execute('SELECT * FROM returns WHERE id=?',(rid,)).fetchone()
    if not r: con.close(); return jsonify(error='Return case not found.'),404
    if r['status']!='Replacement Processing': con.close(); return jsonify(error='This case is not awaiting replacement processing.'),409
    if not tracking: con.close(); return jsonify(error='Enter a replacement tracking number.'),400
    con.execute("UPDATE returns SET replacement_tracking=?,status='Replacement Shipped',updated_at=? WHERE id=?",(tracking,datetime.now().isoformat(timespec='seconds'),rid))
    log(con,rid,current_user(),'Replacement shipped',f'Tracking: {tracking}')
    con.commit(); con.close(); return jsonify(message='Replacement shipment recorded.',status='Replacement Shipped')

@app.post('/api/returns/<int:rid>/close')
@roles('Returns Manager')
def close_case(rid):
    con=db(); r=con.execute('SELECT * FROM returns WHERE id=?',(rid,)).fetchone()
    if not r: con.close(); return jsonify(error='Return case not found.'),404
    if r['status'] not in ['Rejected','Refund Completed','Replacement Shipped']: con.close(); return jsonify(error='Only rejected, refunded or shipped cases can be closed.'),409
    con.execute("UPDATE returns SET status='Closed',updated_at=? WHERE id=?",(datetime.now().isoformat(timespec='seconds'),rid)); log(con,rid,current_user(),'Case closed')
    con.commit(); con.close(); return jsonify(message='Case closed.',status='Closed')

@app.get('/api/analytics')
@login_required
def analytics():
    con=db(); total=con.execute('SELECT COUNT(*) n FROM returns').fetchone()['n']; pending=con.execute("SELECT COUNT(*) n FROM returns WHERE status IN ('Requested','Inspection Pending')").fetchone()['n']; approved=con.execute("SELECT COUNT(*) n FROM returns WHERE status IN ('Approved','Refund Pending','Refund Completed','Replacement Processing','Replacement Shipped','Closed')").fetchone()['n']; refunds=con.execute("SELECT COUNT(*) n FROM returns WHERE status='Refund Completed'").fetchone()['n']; refund_total=con.execute("SELECT COALESCE(SUM(refund_amount),0) n FROM returns WHERE status='Refund Completed'").fetchone()['n']
    reasons=con.execute('SELECT reason,COUNT(*) count FROM returns GROUP BY reason ORDER BY count DESC').fetchall(); statuses=con.execute('SELECT status,COUNT(*) count FROM returns GROUP BY status ORDER BY count DESC').fetchall(); recent=con.execute("SELECT substr(created_at,1,7) month,COUNT(*) count FROM returns WHERE created_at>=date('now','-5 months') GROUP BY month ORDER BY month").fetchall(); con.close()
    return jsonify(metrics={'total':total,'pending':pending,'approved':approved,'refunds':refunds,'refund_total':refund_total},reasons=[rowdict(x) for x in reasons],statuses=[rowdict(x) for x in statuses],monthly=[rowdict(x) for x in recent])

@app.get('/api/users')
@roles('Returns Manager')
def users():
    con=db(); rows=con.execute('SELECT id,name,email,role FROM users ORDER BY name').fetchall(); con.close(); return jsonify(users=[rowdict(x) for x in rows])

if __name__ == '__main__':
    init_db(); app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=os.environ.get('FLASK_DEBUG')=='1')
