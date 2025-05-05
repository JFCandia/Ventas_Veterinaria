from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate

# Configuración inicial
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///veterinaria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave_secreta'

# Inicialización de extensiones
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Modelos de base de datos
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)

class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relación con el modelo Producto
    producto = db.relationship('Producto', backref='ventas')

# Rutas de la aplicación
@app.route('/')
def index():
    productos = Producto.query.all()
    return render_template('index.html', productos=productos)

@app.route('/vender/<int:producto_id>', methods=['POST'])
@login_required
def vender(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    cantidad = int(request.form['cantidad'])

    if producto.stock >= cantidad:
        # Registrar la venta
        venta = Venta(producto_id=producto.id, cantidad=cantidad)
        producto.stock -= cantidad  # Actualizar el stock
        db.session.add(venta)
        db.session.commit()
        flash(f"Venta registrada: {cantidad} unidades de {producto.nombre}.", "success")
    else:
        flash(f"No hay suficiente stock para vender {cantidad} unidades de {producto.nombre}.", "danger")
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"Bienvenido, {user.username}!", "success")

            # Redirigir al usuario a la página que intentaba acceder o al dashboard
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Consulta las ventas y pasa los datos a la plantilla
    ventas = Venta.query.all()
    productos = Producto.query.all()
    return render_template('dashboard.html', ventas=ventas, productos=productos)

@app.route('/agregar_producto', methods=['GET', 'POST'])
@login_required
def agregar_producto():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['nombre']
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])

        # Crear un nuevo producto
        producto = Producto(nombre=nombre, precio=precio, stock=stock)
        db.session.add(producto)
        db.session.commit()

        # Mostrar mensaje de éxito
        flash(f"Producto '{nombre}' agregado correctamente.", "success")
        return redirect(url_for('dashboard'))

    # Mostrar el formulario
    return render_template('agregar_producto.html')

@app.route('/ventas')
def ventas():
    ventas = Venta.query.all()
    return render_template('ventas.html', ventas=ventas)

@app.route('/api/productos')
def api_productos():
    productos = Producto.query.all()
    productos_json = [
        {"id": p.id, "nombre": p.nombre, "precio": p.precio, "stock": p.stock}
        for p in productos
    ]
    return jsonify(productos_json)

@app.route('/guardar_productos')
def guardar_productos():
    productos = Producto.query.all()
    session['productos'] = [
        {"id": p.id, "nombre": p.nombre, "precio": p.precio, "stock": p.stock}
        for p in productos
    ]
    return redirect(url_for('mostrar_productos'))

@app.route('/mostrar_productos')
def mostrar_productos():
    productos = session.get('productos', [])
    return render_template('productos.html', productos=productos)

@app.route('/reportes')
@login_required
def reportes():
    # Consulta las ventas y agrupa por producto
    ventas = db.session.query(
        Producto.nombre,
        db.func.sum(Venta.cantidad).label('total')
    ).join(Venta, Producto.id == Venta.producto_id).group_by(Producto.nombre).all()

    # Extrae los nombres de los productos y las cantidades vendidas
    labels = [venta[0] for venta in ventas]  # Nombres de los productos
    data = [venta[1] for venta in ventas]    # Cantidades vendidas

    return render_template('reportes.html', labels=labels, data=data)

@app.context_processor
def inject_productos():
    productos = Producto.query.all()  # Consulta todos los productos
    return dict(productos=productos)

if __name__ == '__main__':
    with app.app_context():
        # Agregar un usuario inicial si no existe
        if not Usuario.query.filter_by(username="admin").first():
            usuario = Usuario(username="admin")
            usuario.set_password("admin123")
            db.session.add(usuario)

        # Agregar productos iniciales si no existen
        if not Producto.query.first():
            productos_iniciales = [
                Producto(nombre="Alimento para perros", precio=50.0, stock=20),
                Producto(nombre="Alimento para gatos", precio=45.0, stock=15),
                Producto(nombre="Juguete para perros", precio=25.0, stock=10),
                Producto(nombre="Juguete para gatos", precio=20.0, stock=12),
                Producto(nombre="Collar antipulgas", precio=35.0, stock=8),
                Producto(nombre="Arena para gatos", precio=30.0, stock=25),
                Producto(nombre="Shampoo para mascotas", precio=15.0, stock=18),
                Producto(nombre="Cama para perros", precio=100.0, stock=5),
                Producto(nombre="Cama para gatos", precio=90.0, stock=6),
                Producto(nombre="Transportadora para mascotas", precio=120.0, stock=4),
            ]
            db.session.add_all(productos_iniciales)

        # Guardar los cambios
        db.session.commit()

        # Imprimir usuarios y productos
        print(Usuario.query.all())  # Debería devolver una lista de usuarios
        print(Producto.query.all())  # Debería devolver una lista de productos

    # Iniciar la aplicación Flask
    app.run(debug=True)