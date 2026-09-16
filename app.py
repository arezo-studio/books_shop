
# ============================================================
# کتاب‌فروشی آنلاین - فایل اصلی برنامه
# ============================================================

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests

# ============================================================
# تنظیمات اولیه
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookstore.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================================
# تنظیمات زرین‌پال (سندباکس)
# ============================================================
ZARINPAL_MERCHANT = '40dd3bce-be92-4ca0-9a26-cfe7ac6f4c7d'
ZARINPAL_REQUEST_URL = 'https://sandbox.zarinpal.com/pg/v4/payment/request.json'
ZARINPAL_VERIFY_URL = 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json'
ZARINPAL_STARTPAY_URL = 'https://sandbox.zarinpal.com/pg/StartPay/'
CALLBACK_URL = 'http://127.0.0.1:5002/verify-payment'

# ============================================================
# مدل‌های دیتابیس
# ============================================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    books = db.relationship('Book', backref='category', lazy=True)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(200))
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    status = db.Column(db.String(20), default='pending')
    total_price = db.Column(db.Float, default=0.0)
    payment_ref = db.Column(db.String(100), default='')
    items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float)
    book = db.relationship('Book')

# ============================================================
# ساخت دیتابیس و داده‌های اولیه
# ============================================================
with app.app_context():
    db.create_all()
    if Category.query.count() == 0:
        cats = [
            Category(name='رمان'),
            Category(name='تاریخی'),
            Category(name='کودک'),
            Category(name='علمی'),
            Category(name='شعر'),
            Category(name='مذهبی')
        ]
        db.session.add_all(cats)
        db.session.commit()

        books = [
            Book(title='صد سال تنهایی', author='گابریل گارسیا مارکز', price=120000, stock=10, category=cats[0]),
            Book(title='جنگ و صلح', author='لئو تولستوی', price=180000, stock=3, category=cats[0]),
            Book(title='تاریخ ایران باستان', author='حسن پیرنیا', price=90000, stock=5, category=cats[1]),
            Book(title='شازده کوچولو', author='آنتوان دو سنت اگزوپری', price=75000, stock=12, category=cats[2]),
            Book(title='مثنوی معنوی', author='مولانا', price=150000, stock=7, category=cats[4]),
            Book(title='هری پاتر و سنگ جادو', author='جی.کی. رولینگ', price=200000, stock=2, category=cats[2]),
            Book(title='انسان خردمند', author='یووال نوح هراری', price=160000, stock=4, category=cats[3]),
            Book(title='دیوان حافظ', author='حافظ', price=95000, stock=20, category=cats[4]),
            Book(title='نهج البلاغه', author='امام علی (ع)', price=130000, stock=0, category=cats[5]),
            Book(title='مغازه خودکشی', author='ژان تولی', price=85000, stock=6, category=cats[0])
        ]
        db.session.add_all(books)
        db.session.commit()

# ============================================================
# مسیرهای عمومی سایت
# ============================================================
@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/shop')
def shop():
    categories = Category.query.all()
    books = Book.query.limit(8).all()
    return render_template('index.html', categories=categories, books=books)


@app.route('/category/<cat_name>')
def category(cat_name):
    category = Category.query.filter_by(name=cat_name).first_or_404()
    books = Book.query.filter_by(category_id=category.id).all()
    return render_template('category.html', category=category, books=books)

# ============================================================
# سبد خرید
# ============================================================
@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    cart_items = []
    total = 0
    for book_id, qty in cart.items():
        book = Book.query.get(int(book_id))
        if book:
            subtotal = book.price * qty
            total += subtotal
            cart_items.append({'book': book, 'quantity': qty, 'subtotal': subtotal})
    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/add-to-cart/<int:book_id>', methods=['POST'])
def add_to_cart(book_id):
    cart = session.get('cart', {})
    cart[str(book_id)] = cart.get(str(book_id), 0) + 1
    session['cart'] = cart
    return redirect(request.referrer or url_for('shop'))


@app.route('/update-cart/<int:book_id>', methods=['POST'])
def update_cart(book_id):
    new_qty = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    if new_qty <= 0:
        cart.pop(str(book_id), None)
    else:
        cart[str(book_id)] = new_qty
    session['cart'] = cart
    return redirect(url_for('cart'))


@app.route('/remove-from-cart/<int:book_id>', methods=['POST'])
def remove_from_cart(book_id):
    cart = session.get('cart', {})
    cart.pop(str(book_id), None)
    session['cart'] = cart
    return redirect(url_for('cart'))

# ============================================================
# ثبت سفارش و اتصال به زرین‌پال
# ============================================================
@app.route('/place-order', methods=['POST'])
@login_required
def place_order():
    cart = session.get('cart', {})
    if not cart:
        flash('سبد خرید شما خالی است.')
        return redirect(url_for('cart'))

    total = 0
    for book_id, qty in cart.items():
        book = Book.query.get(int(book_id))
        if book:
            total += book.price * qty

    if total <= 0:
        flash('مبلغ سبد خرید نامعتبر است.')
        return redirect(url_for('cart'))

    order = Order(user_id=current_user.id, status='pending', total_price=total)
    db.session.add(order)
    db.session.flush()

    for book_id, qty in cart.items():
        book = Book.query.get(int(book_id))
        if book:
            item = OrderItem(order_id=order.id, book_id=book.id, quantity=qty, price=book.price)
            db.session.add(item)
    db.session.commit()

    session['pending_order_id'] = order.id

    request_data = {
        'merchant_id': ZARINPAL_MERCHANT,
        'amount': int(total),
        'callback_url': CALLBACK_URL,
        'description': f'سفارش شماره {order.id}'
    }

    try:
        response = requests.post(ZARINPAL_REQUEST_URL, json=request_data, timeout=10)
        result = response.json()
    except Exception:
        flash('خطا در اتصال به درگاه پرداخت.')
        db.session.delete(order)
        db.session.commit()
        return redirect(url_for('cart'))

    if result.get('data') and result['data'].get('authority'):
        authority = result['data']['authority']
        return redirect(f'{ZARINPAL_STARTPAY_URL}{authority}')
    else:
        flash('خطا در ایجاد تراکنش.')
        db.session.delete(order)
        db.session.commit()
        return redirect(url_for('cart'))


@app.route('/verify-payment', methods=['GET'])
@login_required
def verify_payment():
    authority = request.args.get('Authority')
    status = request.args.get('Status')

    order_id = session.get('pending_order_id')
    if not order_id:
        flash('سفارشی برای پرداخت یافت نشد.')
        return redirect(url_for('shop'))

    order = Order.query.get(order_id)
    if not order:
        flash('سفارش نامعتبر است.')
        return redirect(url_for('shop'))

    if status == 'OK':
        verify_data = {
            'merchant_id': ZARINPAL_MERCHANT,
            'amount': int(order.total_price),
            'authority': authority
        }
        try:
            response = requests.post(ZARINPAL_VERIFY_URL, json=verify_data, timeout=10)
            result = response.json()
        except Exception:
            flash('خطا در بررسی پرداخت.')
            return redirect(url_for('orders'))

        if result.get('data') and result['data'].get('code') == 100:
            order.status = 'paid'
            order.payment_ref = str(result['data'].get('ref_id', ''))
            db.session.commit()

            for item in order.items:
                item.book.stock = max(0, item.book.stock - item.quantity)
            db.session.commit()

            session.pop('cart', None)
            session.pop('pending_order_id', None)

            flash('پرداخت با موفقیت انجام شد. سفارش شما ثبت شد.')
            return redirect(url_for('orders'))
        else:
            flash('پرداخت ناموفق بود.')
            db.session.delete(order)
            db.session.commit()
            session.pop('pending_order_id', None)
            return redirect(url_for('cart'))
    else:
        flash('پرداخت لغو شد.')
        db.session.delete(order)
        db.session.commit()
        session.pop('pending_order_id', None)
        return redirect(url_for('cart'))

# ============================================================
# سفارش‌های من
# ============================================================
@app.route('/orders')
@login_required
def orders():
    user_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=user_orders)

# ============================================================
# احراز هویت
# ============================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not username or not email or not password:
            flash('لطفاً همه فیلدها را پر کنید.')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً استفاده شده.')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('این ایمیل قبلاً ثبت شده.')
            return redirect(url_for('register'))
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('ثبت‌نام با موفقیت انجام شد. حالا وارد شوید.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('ورود موفق.')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('shop'))
        else:
            flash('نام کاربری یا رمز عبور اشتباه است.')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('خروج انجام شد.')
    return redirect(url_for('shop'))

# ============================================================
# پنل مدیریت - داشبورد
# ============================================================
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('شما اجازه‌ی دسترسی به این صفحه را ندارید.')
        return redirect(url_for('shop'))

    total_books = Book.query.count()
    total_orders = Order.query.count()
    total_users = User.query.count()
    paid_orders = Order.query.filter_by(status='paid').count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
                           total_books=total_books,
                           total_orders=total_orders,
                           total_users=total_users,
                           paid_orders=paid_orders,
                           recent_orders=recent_orders)

# ============================================================
# پنل مدیریت - کتاب‌ها
# ============================================================
@app.route('/admin/books')
@login_required
def admin_books():
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))
    books = Book.query.order_by(Book.id.desc()).all()
    return render_template('admin/books.html', books=books)


@app.route('/admin/books/add', methods=['GET', 'POST'])
@login_required
def admin_add_book():
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))

    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        image = request.form.get('image', '')
        description = request.form.get('description', '')
        category_id = request.form.get('category_id')

        if not title or not author or price <= 0:
            flash('لطفاً همه‌ی فیلدهای ضروری را پر کنید.')
            return redirect(url_for('admin_add_book'))

        book = Book(title=title, author=author, price=price, stock=stock,
                    image=image, description=description,
                    category_id=category_id if category_id else None)
        db.session.add(book)
        db.session.commit()
        flash('کتاب با موفقیت اضافه شد.')
        return redirect(url_for('admin_books'))

    categories = Category.query.all()
    return render_template('admin/book_form.html', categories=categories, book=None)


@app.route('/admin/books/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_book(book_id):
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))

    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        book.title = request.form.get('title')
        book.author = request.form.get('author')
        book.price = float(request.form.get('price', 0))
        book.stock = int(request.form.get('stock', 0))
        book.image = request.form.get('image', '')
        book.description = request.form.get('description', '')
        category_id = request.form.get('category_id')
        book.category_id = category_id if category_id else None
        db.session.commit()
        flash('کتاب با موفقیت ویرایش شد.')
        return redirect(url_for('admin_books'))

    categories = Category.query.all()
    return render_template('admin/book_form.html', categories=categories, book=book)


@app.route('/admin/books/delete/<int:book_id>', methods=['POST'])
@login_required
def admin_delete_book(book_id):
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))
    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    flash('کتاب حذف شد.')
    return redirect(url_for('admin_books'))

# ============================================================
# پنل مدیریت - دسته‌بندی‌ها
# ============================================================
@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))

    if request.method == 'POST':
        name = request.form.get('name')
        if name and not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))
            db.session.commit()
            flash('دسته‌بندی اضافه شد.')
        else:
            flash('این دسته‌بندی وجود دارد یا نامعتبر است.')
        return redirect(url_for('admin_categories'))

    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST'])
@login_required
def admin_delete_category(cat_id):
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))
    category = Category.query.get_or_404(cat_id)
    if category.books:
        flash('این دسته‌بندی دارای کتاب است و قابل حذف نیست.')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('دسته‌بندی حذف شد.')
    return redirect(url_for('admin_categories'))

# ============================================================
# پنل مدیریت - سفارش‌ها
# ============================================================
@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))
    orders_list = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders_list)

# ============================================================
# پنل مدیریت - کاربران
# ============================================================
@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('دسترسی ندارید.')
        return redirect(url_for('shop'))
    users = User.query.order_by(User.id.desc()).all()
    return render_template('admin/users.html', users=users)
# ============================================================
# جستجو
# ============================================================
@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if query:
        books = Book.query.filter(
            (Book.title.ilike(f'%{query}%')) |
            (Book.author.ilike(f'%{query}%'))
        ).all()
    else:
        books = []
    return render_template('search.html', query=query, books=books)

# ============================================================
# اجرای برنامه
# ============================================================
if __name__ == '__main__':
    app.run()
