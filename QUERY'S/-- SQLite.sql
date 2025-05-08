-- SQLite

select* FROM sqlite_master 
WHERE type='table';

SELECT * from historial_stock

select * from usuario

DELETE FROM usuario
where username = 'jcandia'

select * from producto

select * from categoria

select * from venta

SELECT venta.id AS venta_id,
       producto.nombre AS producto_nombre,
       venta.cantidad AS cantidad_vendida,
       venta.fecha AS fecha_venta
FROM venta
JOIN producto ON venta.producto_id = producto.id;

--REVISAR PRODUCTO BAJO STOCK--

SELECT id, nombre, precio, stock 
FROM producto
WHERE stock < 5;

UPDATE producto
SET stock = 3
WHERE id = 1; -- Cambia el ID al producto que deseas actualizar

ROLLBACK;


DELETE FROM producto