# Digiturno: sistema de turnos para vigilancia escolar

Aplicación web para organizar los turnos de los vigilantes de un colegio, que antes no contaban con un orden de atención.
Proyecto grupal del SENA, Técnico en Análisis y Desarrollo de Software.

## Tecnologías

Python, Flask, MySQL (PyMySQL), Bootstrap, HTML, CSS y JavaScript.

## Funciones

- Registro e inicio de sesión, con contraseñas encriptadas con bcrypt
- Roles de administrador y usuario
- Creación, edición y eliminación de turnos (diurno y nocturno)
- Notificaciones de los usuarios hacia el administrador
- Formulario de sugerencias
- Reportes de turnos exportables a PDF y Excel

## Cómo ejecutarlo

1. Instala [Python](https://www.python.org/downloads/) y [XAMPP](https://www.apachefriends.org/). Inicia **MySQL** desde XAMPP.
2. Abre `http://localhost/phpmyadmin` e importa el archivo `flask_login.sql` (crea la base de datos `flask_login` con sus tablas).
3. En la carpeta del proyecto, ejecuta en PowerShell:

   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python app.py
   ```

4. Abre `http://127.0.0.1:5000` en el navegador.

La conexión usa por defecto `localhost`, usuario `root` y sin contraseña (configuración normal de XAMPP). Se puede cambiar con las variables de entorno `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD` y `MYSQL_DB`.

## Usuarios de prueba

| Rol | Correo | Contraseña |
|-----|--------|------------|
| Administrador | admin@demo.com | Demo1234 |
| Usuario | vigilante1@demo.com | Demo1234 |
| Usuario | vigilante2@demo.com | Demo1234 |

Son cuentas de demostración con datos ficticios.

## Crear un usuario administrador

Todos los usuarios que se registran desde `/regis` quedan como usuarios normales (`is_admin = 0`). Para convertir uno en administrador:

1. Regístrate desde la página.
2. En phpMyAdmin, abre la base `flask_login`, tabla `users`, y pon el valor `1` en la columna `is_admin` de ese usuario. También puedes ejecutar:

   ```sql
   UPDATE users SET is_admin = 1 WHERE correo = 'tu_correo@ejemplo.com';
   ```

3. Cierra sesión (`/logout`) y vuelve a iniciar sesión para que el cambio tenga efecto.

`is_admin = 1` es administrador y `is_admin = 0` es usuario normal.