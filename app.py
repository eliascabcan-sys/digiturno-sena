from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_file
import pymysql
from io import BytesIO
from reportlab.pdfgen import canvas
from flask_bcrypt import Bcrypt
from openpyxl import Workbook
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'  # ⚠️ Mejor mover a variable de entorno

# SQL CONFIG ---------------------------------------------------------
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'flask_login')

def get_db_connection():
    return pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB'],
        cursorclass=pymysql.cursors.DictCursor
    )

bcrypt = Bcrypt(app)

# UTIL ---------------------------------------------------------
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# RUTAS ---------------------------------------------------------

@app.route('/')
def home():
    # si está logueado lo manda a su panel
    if 'usuario' in session:
        if session.get('is_admin') == 1:
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('usuario'))
    
    # si NO está logueado, muestra index.html en lugar de login
    return render_template('index.html')

#Sugerencias

@app.route('/contacto', methods=['POST'])
def contacto():
    nombre = request.form['name']
    correo = request.form['personal']
    mensaje = request.form['message']

    # Guardar en la base de datos
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO sugerencias (nombre, correo, mensaje) VALUES (%s, %s, %s)",
                (nombre, correo, mensaje))
    conn.commit()
    cur.close()
    conn.close()

    # Mostrar mensaje flash
    flash("¡Mensaje enviado con éxito!", "success")
    return redirect(url_for('home'))

# LOGIN ---------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contrasena = request.form['contrasena']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE correo = %s", (correo,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['contrasena'], contrasena):
            session['usuario'] = user['usuario']   # ⚠️ Asegúrate que la tabla tenga esta columna
            session['id'] = user['id']
            session['is_admin'] = user['is_admin']

            if user['is_admin'] == 1:
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('usuario'))
        else:
            flash('Correo o contraseña incorrectos', 'danger')
            return redirect(url_for('login'))

    response = make_response(render_template('login.html'))
    return add_no_cache_headers(response)

# REGISTRO ---------------------------------------------------------
@app.route('/regis', methods=['GET', 'POST'])
def regis():
    if request.method == 'POST':
        usuario = request.form['usuario']
        correo = request.form['correo']
        telefono = request.form['telefono']
        contrasena = request.form['contrasena']
        hashed_password = bcrypt.generate_password_hash(contrasena).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE correo = %s", (correo,))
        existing_user = cur.fetchone()
        if existing_user:
            flash('El correo ya existe. Intenta con otro.', 'danger')
            cur.close()
            conn.close()
            return redirect(url_for('regis'))

        cur.execute(
            "INSERT INTO users (usuario, correo, telefono, contrasena, is_admin) VALUES (%s, %s, %s, %s, 0)",
            (usuario, correo, telefono, hashed_password)
        )
        conn.commit()
        cur.close()
        conn.close()

        flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))

    response = make_response(render_template('regis.html'))
    return add_no_cache_headers(response)

# PANEL USUARIO ---------------------------------------------------------
# PANEL USUARIO (con filtro por fechas)
@app.route('/usuario', methods=['GET'])
def usuario():
    if 'usuario' not in session or session.get('is_admin') == 1:
        return redirect(url_for('login'))

    fecha_inicio = request.args.get('fecha_inicio') or None
    fecha_fin = request.args.get('fecha_fin') or None

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        query = "SELECT id, tipo_turno, fecha, hora_inicio, hora_fin, estado FROM turnos WHERE user_id = %s"
        params = [session['id']]

        if fecha_inicio:
            query += " AND fecha >= %s"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND fecha <= %s"
            params.append(fecha_fin)

        query += " ORDER BY fecha DESC, hora_inicio ASC"

        cur.execute(query, tuple(params))
        turnos = cur.fetchall() or []
    except Exception as e:
        import traceback; traceback.print_exc()
        flash(f"Error al obtener tus turnos: {e}", "danger")
        turnos = []
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

    return render_template('usuario.html', turnos=turnos, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)


# CONFIGURACIÓN USUARIO -----------------------------------------
@app.route('/configuracion', methods=['GET', 'POST'])
def configuracion():
    if 'usuario' not in session or session.get('is_admin') == 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nueva_contrasena = request.form['nueva_contrasena']
        confirmar_contrasena = request.form['confirmar_contrasena']

        if nueva_contrasena != confirmar_contrasena:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('configuracion'))

        hashed_pw = bcrypt.generate_password_hash(nueva_contrasena).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET contrasena = %s WHERE id = %s", (hashed_pw, session['id']))
        conn.commit()
        cur.close()
        conn.close()

        flash('Contraseña actualizada correctamente', 'success')
        return redirect(url_for('configuracion'))

    return render_template('configuracion.html')

# RUTA: formulario para que el usuario notifique un problema---------------------------------------------------
@app.route('/usuario/notificar', methods=['GET', 'POST'])
def usuario_notificar():
    if 'usuario' not in session or session.get('is_admin') == 1:
        return redirect(url_for('login'))

    if request.method == 'POST':
        asunto = request.form.get('asunto', '').strip()
        mensaje = request.form['mensaje']
        user_id = session['id']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO notificaciones (user_id, asunto, mensaje, fecha, leido)
            VALUES (%s, %s, %s, NOW(), 0)
        """, (user_id, asunto, mensaje))
        conn.commit()
        cur.close()
        conn.close()

        flash('Tu notificación fue enviada correctamente.', 'success')
        return redirect(url_for('usuario'))

    return render_template('usuario_notificar.html')








#admin---------------------------------------------------------------------------------------------------
@app.route('/admin')
def admin():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.tipo_turno, t.fecha, t.hora_inicio, t.hora_fin, t.estado, u.usuario 
        FROM turnos t 
        JOIN users u ON t.user_id = u.id
    """)
    turnos = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('admin.html', turnos=turnos)
#admin_usuarios---------------------------------------------------
@app.route('/admin/usuarios')
def admin_usuarios():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, usuario, correo, telefono, is_admin FROM users")
    usuarios = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('admin_usuarios.html', usuarios=usuarios)


# ELIMINAR USUARIO -----------------------------------------
@app.route('/admin/usuarios/eliminar/<int:user_id>')
def eliminar_usuario(user_id):
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Evitar eliminar a un administrador
        cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            flash("Usuario no encontrado.", "warning")
        elif user['is_admin'] == 1:
            flash("No puedes eliminar a un administrador.", "danger")
        else:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            flash("Usuario eliminado correctamente.", "success")

    except Exception as e:
        import traceback; traceback.print_exc()
        flash(f"Error al eliminar usuario: {e}", "danger")
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

    return redirect(url_for('admin_usuarios'))


#admin reportes ------------------------------------------------------------------------------
@app.route('/reportes')
def reportes():
    # seguridad: sólo admin
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    # obtener filtros desde la query string
    user_id = request.args.get('user_id') or None
    fecha_inicio = request.args.get('fecha_inicio') or None
    fecha_fin = request.args.get('fecha_fin') or None

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Helper: convierte filas (tuplas) a dicts si es necesario
        def rows_to_dicts(cursor, rows):
            if not rows:
                return []
            # si ya son dicts (p.ej. DictCursor) devolver tal cual
            if isinstance(rows[0], dict):
                return rows
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

        # 1) lista de usuarios para el select
        cur.execute("SELECT id, usuario FROM users")
        usuarios_rows = cur.fetchall()
        usuarios = rows_to_dicts(cur, usuarios_rows)

        # 2) consulta principal de turnos con filtros
        query = """
            SELECT t.id, t.tipo_turno, t.fecha, t.hora_inicio, t.hora_fin, t.estado, u.usuario
            FROM turnos t
            JOIN users u ON t.user_id = u.id
            WHERE 1=1
        """
        params = []
        if user_id:
            query += " AND u.id = %s"
            params.append(user_id)
        if fecha_inicio:
            query += " AND t.fecha >= %s"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND t.fecha <= %s"
            params.append(fecha_fin)
        query += " ORDER BY t.fecha ASC"

        cur.execute(query, tuple(params))
        turnos_rows = cur.fetchall()
        turnos = rows_to_dicts(cur, turnos_rows)

        # 3) estadísticas para el gráfico (mismo filtro)
        stats_q = """
            SELECT t.tipo_turno, COUNT(*) as total
            FROM turnos t
            JOIN users u ON t.user_id = u.id
            WHERE 1=1
        """
        stats_params = []
        if user_id:
            stats_q += " AND u.id = %s"
            stats_params.append(user_id)
        if fecha_inicio:
            stats_q += " AND t.fecha >= %s"
            stats_params.append(fecha_inicio)
        if fecha_fin:
            stats_q += " AND t.fecha <= %s"
            stats_params.append(fecha_fin)
        stats_q += " GROUP BY t.tipo_turno"

        cur.execute(stats_q, tuple(stats_params))
        estad_rows = cur.fetchall()
        estad_rows = rows_to_dicts(cur, estad_rows)

        # 4) preparar resumen con claves fijas y mapear Matutino -> Diurno para mostrar
        resumen = {"Matutino": 0, "Nocturno": 0}
        for r in estad_rows:
            tipo = r.get('tipo_turno') if isinstance(r, dict) else r[0]
            total = int(r.get('total') if isinstance(r, dict) else r[1] or 0)
            if tipo:
                resumen[tipo] = total

        # preparar labels y datos para la gráfica (mostrar "Diurno" en vez de "Matutino")
        chart_labels = []
        chart_data = []
        for k, v in resumen.items():
            display_label = "Diurno" if k == "Matutino" else k
            chart_labels.append(display_label)
            chart_data.append(v)

        # 5) normalizar turnos para que en la tabla también muestre "Diurno" en vez de "Matutino"
        turnos_norm = []
        for t in turnos:
            # t puede ser dict o tupla convertida; rows_to_dicts ya devolvió dicts
            row = dict(t)
            if row.get('tipo_turno') == 'Matutino':
                row['tipo_turno'] = 'Diurno'
            turnos_norm.append(row)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error al generar reportes: {e}", "danger")
        # cerrar recursos si están abiertos
        try:
            cur.close()
            conn.close()
        except:
            pass
        return redirect(url_for('admin'))
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

    selected_user = int(user_id) if user_id else None

    return render_template(
        'reportes.html',
        usuarios=usuarios,
        turnos=turnos_norm,
        selected_user=selected_user,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

#Reportes/Excel-----------------------------------------------------
@app.route('/reportes/excel')
def reportes_excel():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    user_id = request.args.get('user_id')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')

    conn = get_db_connection()
    cur = conn.cursor()

    query = """
        SELECT t.id, t.tipo_turno, t.fecha, t.hora_inicio, t.hora_fin, t.estado, u.usuario
        FROM turnos t
        JOIN users u ON t.user_id = u.id
        WHERE 1=1
    """
    params = []
    if user_id:
        query += " AND u.id = %s"
        params.append(user_id)
    if fecha_inicio:
        query += " AND t.fecha >= %s"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND t.fecha <= %s"
        params.append(fecha_fin)

    cur.execute(query, tuple(params))
    turnos = cur.fetchall()
    cur.close()
    conn.close()

    # Generar Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Turnos"
    ws.append(["ID", "Tipo", "Fecha", "Inicio", "Fin", "Estado", "Usuario"])

    for t in turnos:
        ws.append([t['id'], t['tipo_turno'], str(t['fecha']), t['hora_inicio'], t['hora_fin'], t['estado'], t['usuario']])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name="reporte_turnos.xlsx", as_attachment=True)


@app.route('/reportes/pdf')
def reportes_pdf():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    user_id = request.args.get('user_id')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')

    conn = get_db_connection()
    cur = conn.cursor()

    query = """
        SELECT t.id, t.tipo_turno, t.fecha, t.hora_inicio, t.hora_fin, t.estado, u.usuario
        FROM turnos t
        JOIN users u ON t.user_id = u.id
        WHERE 1=1
    """
    params = []
    if user_id:
        query += " AND u.id = %s"
        params.append(user_id)
    if fecha_inicio:
        query += " AND t.fecha >= %s"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND t.fecha <= %s"
        params.append(fecha_fin)

    cur.execute(query, tuple(params))
    turnos = cur.fetchall()
    cur.close()
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=(595, 842))
    y = 800

    p.setFont("Helvetica-Bold", 16)
    p.drawString(150, y, "Reporte de Turnos - Digiturnos")
    y -= 40

    for t in turnos:
        if y < 100:
            p.showPage()
            y = 800
            p.setFont("Helvetica-Bold", 16)
            p.drawString(150, y, "Reporte de Turnos - Digiturnos")
            y -= 40

        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"ID: {t['id']} | {t['tipo_turno']} | {t['fecha']} | {t['hora_inicio']} - {t['hora_fin']} | {t['estado']} | {t['usuario']}")
        y -= 20

    p.save()
    buffer.seek(0)

    return send_file(buffer, download_name="reporte_turnos.pdf", as_attachment=True)

# EDITAR ESTADO DE UN TURNO -----------------------------------------
@app.route('/turnos/editar/<int:id>', methods=['GET', 'POST'])
def editar_turno(id):
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        fecha = request.form['fecha']
        tipo_turno = request.form['tipo_turno']
        estado = request.form['estado']
        user_id = request.form['user_id']

        # Ajustar las horas según tipo de turno
        if tipo_turno == "Diurno":
            hora_inicio = "06:00:00"
            hora_fin = "18:00:00"
        else:
            hora_inicio = "18:00:00"
            hora_fin = "06:00:00"

        cur.execute("""
            UPDATE turnos 
            SET tipo_turno=%s, fecha=%s, hora_inicio=%s, hora_fin=%s, estado=%s, user_id=%s 
            WHERE id=%s
        """, (tipo_turno, fecha, hora_inicio, hora_fin, estado, user_id, id))

        conn.commit()
        cur.close()
        conn.close()
        flash("Turno actualizado correctamente", "success")
        return redirect(url_for('reportes'))

    # Si es GET → obtener turno y lista de usuarios
    cur.execute("""
        SELECT t.id, t.tipo_turno, t.fecha, t.estado, t.user_id, u.usuario
        FROM turnos t
        JOIN users u ON t.user_id = u.id
        WHERE t.id = %s
    """, (id,))
    turno = cur.fetchone()

    cur.execute("SELECT id, usuario FROM users WHERE is_admin = 0")
    usuarios = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('turno-editar.html', turno=turno, usuarios=usuarios)

# CREAR NUEVO TURNO -----------------------------------------
@app.route('/turno/nuevo', methods=['GET', 'POST'])
def nuevo_turno():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        fecha = request.form['fecha']
        tipo_turno = request.form['tipo_turno'].strip()  # 👈 quita espacios extra
        estado = request.form['estado']
        user_id = request.form['user_id']

        # Definir horas según el tipo de turno
        if tipo_turno == "Diurno":
            hora_inicio = "06:00:00"
            hora_fin = "18:00:00"
        else:
            hora_inicio = "18:00:00"
            hora_fin = "06:00:00"

        cur.execute("""
    INSERT INTO turnos (tipo_turno, fecha, hora_inicio, hora_fin, estado, user_id)
    VALUES (%s, %s, %s, %s, %s, %s)
""", (tipo_turno, fecha, hora_inicio, hora_fin, estado, user_id))


        conn.commit()
        cur.close()
        conn.close()
        flash("Turno asignado correctamente", "success")
        return redirect(url_for('admin'))

    # Si es GET, mostrar formulario con usuarios
    cur.execute("SELECT id, usuario FROM users WHERE is_admin = 0")
    usuarios = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('turno-nuevo.html', usuarios=usuarios)
# --------------------------------------------------------
# 📩 ADMIN - VER NOTIFICACIONES
# --------------------------------------------------------
@app.route('/admin/notificaciones')
def admin_notificaciones():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT n.id, u.usuario, n.mensaje, n.fecha, n.leido
            FROM notificaciones n
            JOIN users u ON n.user_id = u.id
            ORDER BY n.fecha DESC
        """)
        notis = cur.fetchall()
    except Exception as e:
        import traceback; traceback.print_exc()
        flash(f"Error al obtener notificaciones: {e}", "danger")
        notis = []
    finally:
        cur.close()
        conn.close()

    return render_template('admin_notificaciones.html', notis=notis)


# ✅ Marcar una notificación como leída
@app.route('/notificacion/leida/<int:noti_id>')
def notificacion_leida(noti_id):
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notificaciones SET leido = 1 WHERE id = %s", (noti_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Notificación marcada como leída", "success")
    return redirect(url_for('admin_notificaciones'))


# 🗑️ Eliminar notificación
@app.route('/notificacion/eliminar/<int:noti_id>')
def eliminar_notificacion(noti_id):
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notificaciones WHERE id = %s", (noti_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Notificación eliminada correctamente", "success")
    return redirect(url_for('admin_notificaciones'))


# ADMIN - SUGERENCIAS (ver, marcar como leída, eliminar) ------------------------------
@app.route('/admin/sugerencias')
def admin_sugerencias():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre, correo, mensaje, fecha, leido 
        FROM sugerencias 
        ORDER BY fecha DESC
    """)
    sugerencias = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('admin_sugerencias.html', sugerencias=sugerencias)


# MARCAR SUGERENCIA COMO LEÍDA -------------------------------------------------------
@app.route('/admin/sugerencias/leida/<int:sug_id>')
def sugerencia_leida(sug_id):
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sugerencias SET leido = 1 WHERE id = %s", (sug_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Sugerencia marcada como leída.", "success")
    return redirect(url_for('admin_sugerencias'))


# ELIMINAR SUGERENCIA ---------------------------------------------------------------
@app.route('/admin/sugerencias/eliminar/<int:sug_id>')
def sugerencia_eliminar(sug_id):
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sugerencias WHERE id = %s", (sug_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Sugerencia eliminada.", "danger")
    return redirect(url_for('admin_sugerencias'))



# ELIMINAR UN TURNO -----------------------------------------
@app.route('/turnos/eliminar/<int:id>')
def eliminar_turno(id):
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM turnos WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Turno eliminado correctamente", "danger")
    return redirect(url_for('admin'))

# EXPORTAR TURNOS A EXCEL ----------------------------------------------
@app.route('/report/turnos/excel')
def report_turnos_excel():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.numero, t.fecha, t.estado, u.usuario 
        FROM turnos t 
        JOIN users u ON t.user_id = u.id
    """)
    turnos = cur.fetchall()
    cur.close()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Turnos"
    ws.append(["ID", "Número", "Fecha", "Estado", "Usuario"])

    for turno in turnos:
        ws.append([turno['id'], turno['numero'], str(turno['fecha']), turno['estado'], turno['usuario']])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output, download_name="reporte_turnos.xlsx", as_attachment=True)

# EXPORTAR TURNOS A PDF ----------------------------------------------
@app.route('/report/turnos/pdf')
def report_turnos_pdf():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.numero, t.fecha, t.estado, u.usuario 
        FROM turnos t 
        JOIN users u ON t.user_id = u.id
    """)
    turnos = cur.fetchall()
    cur.close()
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=(595, 842))  # A4
    y = 800

    p.setFont("Helvetica-Bold", 16)
    p.drawString(180, y, "Reporte de Turnos - Digiturnos")
    y -= 40

    for turno in turnos:
        if y < 100:  # Nueva página si se llena
            p.showPage()
            y = 800
            p.setFont("Helvetica-Bold", 16)
            p.drawString(180, y, "Reporte de Turnos - Digiturnos")
            y -= 40

        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"ID: {turno['id']} | Número: {turno['numero']} | Fecha: {turno['fecha']} | Estado: {turno['estado']} | Usuario: {turno['usuario']}")
        y -= 20

    p.save()
    buffer.seek(0)

    return send_file(buffer, download_name="reporte_turnos.pdf", as_attachment=True)

# CONFIGURACIÓN DEL ADMIN -----------------------------------------
@app.route('/configuracion_admin', methods=['GET', 'POST'])
def configuracion_admin():
    if 'usuario' not in session or session.get('is_admin') == 0:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nueva_contrasena = request.form['nueva_contrasena']
        confirmar_contrasena = request.form['confirmar_contrasena']

        if nueva_contrasena != confirmar_contrasena:
            flash('Las contraseñas no coinciden.', 'danger')
            return redirect(url_for('configuracion_admin'))

        hashed_pw = bcrypt.generate_password_hash(nueva_contrasena).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET contrasena = %s WHERE id = %s", (hashed_pw, session['id']))
        conn.commit()
        cur.close()
        conn.close()

        flash('Contraseña actualizada correctamente.', 'success')
        return redirect(url_for('configuracion_admin'))

    return render_template('configuracion_admin.html')


# LOGOUT ---------------------------------------------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# MAIN ---------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)









