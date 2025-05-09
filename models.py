from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func
from sqlalchemy.orm import validates
from datetime import datetime

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    ventas = db.relationship('Venta', backref='producto', cascade="all, delete-orphan")
    historial_stock = db.relationship('HistorialStock', backref='producto', cascade="all, delete-orphan")
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    @validates('nombre')
    def validate_nombre(self, key, value):
        if not value or len(value.strip()) == 0:
            raise ValueError("El nombre del producto no puede estar vacío.")
        return value

    @validates('precio')
    def validate_precio(self, key, value):
        if value < 0:
            raise ValueError("El precio no puede ser negativo.")
        return value

    @validates('stock')
    def validate_stock(self, key, value):
        if value < 0:
            raise ValueError("El stock no puede ser negativo.")
        return value


class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    @validates('cantidad')
    def validate_cantidad(self, key, value):
        if value <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        return value


class HistorialStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad_cambiada = db.Column(db.Integer, nullable=False)
    motivo = db.Column(db.String(255), nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    @validates('cantidad_cambiada')
    def validate_cantidad_cambiada(self, key, value):
        if value == 0:
            raise ValueError("El cambio de stock no puede ser 0.")
        return value

    @validates('motivo')
    def validate_motivo(self, key, value):
        if not value or len(value.strip()) == 0:
            raise ValueError("El motivo no puede estar vacío.")
        return value

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    productos = db.relationship('Producto', backref='categoria', lazy=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

class ProductoEliminado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    fecha_eliminacion = db.Column(db.DateTime, default=datetime.utcnow)
