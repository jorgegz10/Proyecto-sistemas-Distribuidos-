-- Creación de tablas para el sistema de biblioteca distribuida
-- Este script se ejecuta automáticamente al iniciar el contenedor de PostgreSQL

-- Tabla de libros
CREATE TABLE IF NOT EXISTS libros (
    isbn VARCHAR(20) PRIMARY KEY,
    ejemplares INTEGER NOT NULL DEFAULT 0,
    CHECK (ejemplares >= 0)
);

-- Tabla de préstamos
CREATE TABLE IF NOT EXISTS prestamos (
    isbn VARCHAR(20) NOT NULL,
    usuario VARCHAR(50) NOT NULL,
    fecha_prestamo TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_devolucion TIMESTAMP NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
    renovaciones INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (isbn, usuario),
    FOREIGN KEY (isbn) REFERENCES libros(isbn),
    CHECK (estado IN ('ACTIVO', 'DEVUELTO')),
    CHECK (renovaciones >= 0)
);

-- Insertar libros de prueba
INSERT INTO libros (isbn, ejemplares) VALUES
    ('978-0134685991', 5),  -- Clean Code
    ('978-0135957059', 3),  -- Refactoring
    ('978-0596007126', 7),  -- Head First Design Patterns
    ('978-1491950296', 4)   -- Designing Data-Intensive Applications
ON CONFLICT (isbn) DO UPDATE 
    SET ejemplares = EXCLUDED.ejemplares;

-- Mensaje de confirmación
DO $$
BEGIN
    RAISE NOTICE 'Base de datos inicializada correctamente';
    RAISE NOTICE 'Tablas creadas: libros, prestamos';
    RAISE NOTICE 'Libros de prueba insertados: 4 libros';
END $$;
