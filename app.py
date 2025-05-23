from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from xhtml2pdf import pisa
from io import BytesIO
import os
from werkzeug.utils import secure_filename
import pandas as pd
from models import db, Usuario, Producto, Venta, Categoria, HistorialStock, ProductoEliminado
from datetime import datetime
from sqlalchemy import text, create_engine

# Configuración inicial
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///veterinaria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'clave_secreta'

# Configuración para subir archivos
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Inicialización de extensiones
db.init_app(app)  # Vincula SQLAlchemy con la aplicación Flask
migrate = Migrate(app, db)

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirige a la página de login si no está autenticado
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))



# Rutas de la aplicación
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))  # Redirige al dashboard si está autenticado
    return redirect(url_for('login'))  # Redirige al login si no está autenticado

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"Bienvenido, {user.username}!", "success")
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
    search = request.args.get('search', '').strip()  # Obtén el término de búsqueda
    if search:
        # Filtrar ventas por el nombre del producto asociado
        ventas = Venta.query.join(Producto).filter(Producto.nombre.ilike(f'%{search}%')).all()
    else:
        # Mostrar todas las ventas si no hay búsqueda
        ventas = Venta.query.all()

    productos = Producto.query.all()  # Mantén los productos para otras funcionalidades
    return render_template('dashboard.html', ventas=ventas, productos=productos, active_page='dashboard')

@app.route('/agregar_producto', methods=['GET', 'POST'])
@login_required
def agregar_producto():
    if request.method == 'POST':
        nombre = request.form['nombre']
        precio = round(float(request.form['precio']))  # Redondear el precio
        stock = int(request.form['stock'])
        categoria_id = request.form.get('categoria_id')

        if not nombre.strip():
            flash("El nombre del producto no puede estar vacío.", "danger")
            return redirect(request.url)

        nuevo_producto = Producto(
            nombre=nombre,
            precio=precio,  # Precio redondeado
            stock=stock,
            categoria_id=categoria_id
        )
        db.session.add(nuevo_producto)
        db.session.commit()
        flash(f"Producto '{nombre}' agregado correctamente.", "success")
        return redirect(url_for('dashboard'))

    categorias = Categoria.query.all()
    return render_template('agregar_producto.html', categorias=categorias, active_page='agregar_producto')

@app.route('/eliminar_producto/<int:producto_id>', methods=['POST'])
@login_required
def eliminar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)

    # Registrar el producto eliminado
    producto_eliminado = ProductoEliminado(
        nombre=producto.nombre,
        precio=producto.precio,
        stock=producto.stock
    )
    db.session.add(producto_eliminado)

    # Eliminar el producto de la base de datos
    db.session.delete(producto)
    db.session.commit()

    flash(f"Producto '{producto.nombre}' eliminado correctamente.", "success")
    return redirect(url_for('reporte_stock'))

@app.route('/ajustar_stock/<int:producto_id>', methods=['POST'])
@login_required
def ajustar_stock(producto_id):
    try:
        producto = Producto.query.get_or_404(producto_id)
        cantidad_a_reducir = int(request.form['cantidad'])

        if cantidad_a_reducir > producto.stock:
            flash(f"No puedes reducir más del stock disponible ({producto.stock}).", "danger")
        else:
            producto.stock -= cantidad_a_reducir
            db.session.add(HistorialStock(
                producto_id=producto.id,
                cantidad_cambiada=-cantidad_a_reducir,
                motivo="Ajuste manual"
            ))
            db.session.commit()
            flash(f"Se redujo el stock de '{producto.nombre}' en {cantidad_a_reducir} unidades.", "success")
    except Exception as e:
        db.session.rollback()  # Revertir cambios si ocurre un error
        flash(f"Error al ajustar el stock: {e}", "danger")
    finally:
        db.session.remove()  # Usa remove() en lugar de close() para evitar problemas de conexión

    return redirect(url_for('reporte_stock'))

@app.route('/reporte_bajo_stock')
@login_required
def reporte_bajo_stock():
    umbral_stock = 5
    productos_bajo_stock = Producto.query.filter(Producto.stock < umbral_stock).all()
    return render_template('reporte_bajo_stock.html', productos=productos_bajo_stock, umbral_stock=umbral_stock)

@app.route('/historial_stock/<int:producto_id>')
@login_required
def historial_stock(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    historial = HistorialStock.query.filter_by(producto_id=producto_id).all()
    return render_template('historial_stock.html', producto=producto, historial=historial)

@app.route('/cargar_productos', methods=['GET', 'POST'])
@login_required
def cargar_productos():
    if request.method == 'POST':
        if 'archivo' not in request.files:
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(request.url)

        archivo = request.files['archivo']
        if archivo.filename == '':
            flash("El archivo no tiene un nombre válido.", "danger")
            return redirect(request.url)

        if not archivo.filename.endswith('.xlsx'):
            flash("El archivo debe ser un archivo Excel con extensión .xlsx.", "danger")
            return redirect(request.url)

        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)

        try:
            # Leer el archivo Excel
            df = pd.read_excel(filepath)

            # Validar que las columnas requeridas estén presentes
            columnas_requeridas = {'nombre', 'precio', 'stock'}
            if not columnas_requeridas.issubset(df.columns):
                flash(f"El archivo Excel debe contener las columnas: {', '.join(columnas_requeridas)}.", "danger")
                return redirect(request.url)

            # Insertar productos en la base de datos
            for _, row in df.iterrows():
                producto = Producto(
                    nombre=row['nombre'],
                    precio=round(row['precio']),  # Redondear el precio
                    stock=row['stock']
                )
                db.session.add(producto)

            db.session.commit()
            flash("Productos cargados exitosamente desde el archivo Excel.", "success")
        except Exception as e:
            flash(f"Error al procesar el archivo: {e}", "danger")
        finally:
            # Eliminar el archivo subido después de procesarlo
            if os.path.exists(filepath):
                os.remove(filepath)

        return redirect(url_for('dashboard'))

    return render_template('cargar_productos.html')

@app.route('/emitir_boleta/<int:venta_id>')
@login_required
def emitir_boleta(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    producto = Producto.query.get_or_404(venta.producto_id)

    rendered = render_template('boleta.html', venta=venta, producto=producto)
    output_folder = os.path.join(os.getcwd(), 'generated_boletas')
    os.makedirs(output_folder, exist_ok=True)
    pdf_path = os.path.join(output_folder, f'boleta_{venta.id}.pdf')

    with open(pdf_path, 'wb') as pdf_file:
        pisa.CreatePDF(BytesIO(rendered.encode("UTF-8")), dest=pdf_file)

    return send_file(pdf_path, as_attachment=True, download_name=f'boleta_{venta.id}.pdf')

@app.route('/generar_pdf/<int:venta_id>')
@login_required
def generar_pdf(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    producto = Producto.query.get_or_404(venta.producto_id)

    rendered = render_template('boleta.html', venta=venta, producto=producto)
    output_folder = os.path.join(os.getcwd(), 'generated_boletas')
    os.makedirs(output_folder, exist_ok=True)
    pdf_path = os.path.join(output_folder, f'boleta_{venta.id}.pdf')

    with open(pdf_path, 'wb') as pdf_file:
        pisa.CreatePDF(BytesIO(rendered.encode("UTF-8")), dest=pdf_file)

    return send_file(pdf_path, as_attachment=True, download_name=f'boleta_{venta.id}.pdf')

@app.route('/ventas')
@login_required
def ventas():
    search = request.args.get('search', '').strip()  # Obtén el término de búsqueda
    if search:
        # Filtrar productos disponibles por nombre que contengan el término de búsqueda
        productos = Producto.query.filter(Producto.stock > 0, Producto.nombre.ilike(f'%{search}%')).all()
    else:
        # Mostrar solo los productos disponibles si no hay búsqueda
        productos = Producto.query.filter(Producto.stock > 0).all()

    ventas = Venta.query.all()
    return render_template('ventas.html', ventas=ventas, productos=productos, active_page='ventas')


@app.route('/vender/<int:producto_id>', methods=['POST'])
@login_required
def vender(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    cantidad = int(request.form['cantidad'])

    if cantidad > producto.stock:
        flash(f"No hay suficiente stock para vender {cantidad} unidades de '{producto.nombre}'.", "danger")
    else:
        producto.stock -= cantidad
        venta = Venta(producto_id=producto.id, cantidad=cantidad)
        db.session.add(venta)
        db.session.commit()
        flash(f"Se vendieron {cantidad} unidades de '{producto.nombre}'.", "success")

    return redirect(url_for('dashboard'))

@app.route('/reporte_ventas')
@login_required
def reporte_ventas():
    ventas = Venta.query.all()
    total_ventas = sum(venta.cantidad * venta.producto.precio for venta in ventas if venta.producto)
    return render_template('reporte_ventas.html', ventas=ventas, total_ventas=total_ventas)

@app.route('/reporte_stock')
@login_required
def reporte_stock():
    productos = Producto.query.all()
    # Convertir precios a enteros
    for producto in productos:
        producto.precio = int(producto.precio)
    return render_template('reporte_stock.html', productos=productos)

@app.route('/generar_pdf_reporte_ventas')
@login_required
def generar_pdf_reporte_ventas():
    ventas = Venta.query.all()
    total_ventas = sum(venta.cantidad * venta.producto.precio for venta in ventas if venta.producto)
    rendered = render_template('reporte_ventas_pdf.html', ventas=ventas, total_ventas=total_ventas)
    pdf = BytesIO()
    pisa.CreatePDF(BytesIO(rendered.encode("UTF-8")), dest=pdf)
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name='reporte_ventas.pdf')

@app.route('/generar_pdf_reporte_stock')
@login_required
def generar_pdf_reporte_stock():
    productos = Producto.query.all()
    now = datetime.now()
    rendered = render_template('reporte_stock_pdf.html', productos=productos, now=now)
    pdf = BytesIO()
    pisa.CreatePDF(BytesIO(rendered.encode("UTF-8")), dest=pdf)
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name='reporte_stock.pdf')

@app.route('/agregar_categoria', methods=['GET', 'POST'])
@login_required
def agregar_categoria():
    if request.method == 'POST':
        nombre = request.form['nombre']
        if not nombre.strip():
            flash("El nombre de la categoría no puede estar vacío.", "danger")
            return redirect(request.url)

        # Verifica si la categoría ya existe
        if Categoria.query.filter_by(nombre=nombre).first():
            flash("La categoría ya existe.", "warning")
            return redirect(request.url)

        nueva_categoria = Categoria(nombre=nombre)
        db.session.add(nueva_categoria)
        db.session.commit()
        flash(f"Categoría '{nombre}' agregada correctamente.", "success")
        return redirect(url_for('dashboard'))

    return render_template('agregar_categoria.html')

@app.route('/productos_eliminados')
@login_required
def productos_eliminados():
    productos = ProductoEliminado.query.all()
    return render_template('productos_eliminados.html', productos=productos)

@app.route('/generar_pdf_productos_eliminados')
@login_required
def generar_pdf_productos_eliminados():
    productos_eliminados = ProductoEliminado.query.all()
    now = datetime.now()
    rendered = render_template('productos_eliminados_pdf.html', productos=productos_eliminados, now=now)
    pdf = BytesIO()
    pisa.CreatePDF(BytesIO(rendered.encode("UTF-8")), dest=pdf)
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name='productos_eliminados.pdf')

if __name__ == '__main__':
    with app.app_context():
        # Configurar SQLite para acceso concurrente
        with db.engine.connect() as connection:
            connection.execute(text("PRAGMA journal_mode=WAL"))

        # Código para inicializar datos
        if not Usuario.query.filter_by(username="admin").first():
            usuario = Usuario(username="admin")
            usuario.set_password("admin123")
            db.session.add(usuario)
            db.session.commit()

    app.run(debug=True)