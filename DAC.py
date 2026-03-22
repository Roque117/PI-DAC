import re
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import pyodbc
from datetime import datetime, date, time

app = Flask(__name__)
app.secret_key = 'DAC0123456'

def get_db_connection():
    return pyodbc.connect(
        'DRIVER={SQL Server};'
        'SERVER=localhost;'
        'DATABASE=Alcolimetro;'
        'Trusted_Connection=yes;'
    )

def check_and_create_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar y crear tabla Encuesta si no existe
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Encuesta' AND xtype='U')
            CREATE TABLE Encuesta (
                idEncuesta INT IDENTITY(1,1) PRIMARY KEY,
                nombre NVARCHAR(100) NOT NULL,
                email NVARCHAR(100) NOT NULL,
                satisfaccion INT NOT NULL,
                comentario NVARCHAR(MAX),
                fecha DATE NOT NULL
            )
        """)
        conn.commit()
        print("Tabla Encuesta verificada/creada exitosamente")
    except Exception as e:
        print(f"Error al verificar/crear tablas: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/datos', methods=['POST'])
def recibir_datos():
    try:
        sensor_id = request.form.get('sensor_id', '1')
        valor_sensor = request.form.get('valor')
        concentracion = request.form.get('concentracion')

        if not valor_sensor or not concentracion:
            return jsonify({"status": "error", "message": "Datos incompletos"}), 400

        valor_sensor = int(valor_sensor)
        concentracion = float(concentracion)
        fecha_actual = datetime.now()

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT TOP 1 idAutorizado FROM Autorizados")
        id_autorizado = cursor.fetchone()[0]

        id_persona = 10

        cursor.execute("""
            INSERT INTO Registros (Fecha, Hora, idPersona, idAutorizado, Medicion, ValorSensor)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fecha_actual.date(), fecha_actual.time(), id_persona, id_autorizado, concentracion, valor_sensor))

        conn.commit()
        conn.close()

        return jsonify({
            "status": "success", 
            "message": "Datos almacenados",
            "sensor_id": sensor_id,
            "valor_sensor": valor_sensor,
            "concentracion": concentracion
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/buscar')
def buscar():
    query = request.args.get('query', '')
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT E.Matricula AS id, 
               P.Nombre + ' ' + P.APaterno + ' ' + P.AMaterno AS nombre, 
               C.Carrera AS carrera
        FROM Estudiantes E
        JOIN Personas P ON E.idPersona = P.idPersona
        JOIN AsignacionTutores AT ON E.idAsignacion = AT.idAsignacion
        JOIN Grupos G ON AT.idGrupo = G.idGrupo
        JOIN Carreras C ON G.idCarrera = C.idCarrera
        WHERE E.Matricula LIKE ? OR P.Nombre LIKE ? OR P.APaterno LIKE ? OR P.AMaterno LIKE ?
    """, (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))

    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row.id,
            'nombre': row.nombre,
            'carrera': row.carrera
        })

    conn.close()
    return jsonify(results)

@app.route('/datospersonales')
def datospersonales():
    matricula = request.args.get('matricula')
    if not matricula:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT E.Matricula, 
               P.Nombre + ' ' + P.APaterno + ' ' + P.AMaterno AS NombreCompleto,
               P.Edad, 
               'Calle ' + CAST(P.idPersona AS VARCHAR) + ', Col. Centro' AS Domicilio,
               C.Carrera
        FROM Estudiantes E
        JOIN Personas P ON E.idPersona = P.idPersona
        JOIN AsignacionTutores AT ON E.idAsignacion = AT.idAsignacion
        JOIN Grupos G ON AT.idGrupo = G.idGrupo
        JOIN Carreras C ON G.idCarrera = C.idCarrera
        WHERE E.Matricula = ?
    """, (matricula,))

    estudiante = cursor.fetchone()
    conn.close()

    if estudiante:
        estudiante_data = {
            'id': estudiante.Matricula,
            'nombre': estudiante.NombreCompleto,
            'edad': estudiante.Edad,
            'domicilio': estudiante.Domicilio,
            'carrera': estudiante.Carrera
        }
        return render_template('datospersonales.html', estudiante=estudiante_data)
    else:
        return redirect(url_for('index'))

@app.route('/registro')
def registro():
    matricula = request.args.get('matricula')
    if not matricula:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT E.Matricula, 
               P.Nombre + ' ' + P.APaterno + ' ' + P.AMaterno AS NombreCompleto,
               P.Edad, 
               'Calle ' + CAST(P.idPersona AS VARCHAR) + ', Col. Centro' AS Domicilio,
               C.Carrera
        FROM Estudiantes E
        JOIN Personas P ON E.idPersona = P.idPersona
        JOIN AsignacionTutores AT ON E.idAsignacion = AT.idAsignacion
        JOIN Grupos G ON AT.idGrupo = G.idGrupo
        JOIN Carreras C ON G.idCarrera = C.idCarrera
        WHERE E.Matricula = ?
    """, (matricula,))
    estudiante = cursor.fetchone()

    cursor.execute("""
        SELECT R.idRegistro, 
               CONVERT(VARCHAR(10), R.Fecha, 120) AS Fecha,
               CONVERT(VARCHAR(5), R.Hora, 108) AS Hora,
               Per.Nombre + ' ' + Per.APaterno AS Personal,
               R.Medicion AS Nivel,
               R.Comentario AS Comentario,
               CASE 
                   WHEN R.Medicion > 0.8 THEN 'Nivel peligroso'
                   WHEN R.Medicion > 0.5 THEN 'Nivel alto'
                   ELSE 'Normal'
               END AS Estado
        FROM Registros R
        JOIN Autorizados A ON R.idAutorizado = A.idAutorizado
        JOIN Personas Per ON A.idPersona = Per.idPersona
        WHERE R.idPersona = (SELECT idPersona FROM Estudiantes WHERE Matricula = ?)
        ORDER BY R.Fecha DESC, R.Hora DESC
    """, (matricula,))

    registros = []
    for row in cursor.fetchall():
        registros.append({
            'idRegistro': row.idRegistro,
            'fecha': row.Fecha,
            'hora': row.Hora,
            'personal': row.Personal,
            'nivel': row.Nivel,
            'comentario': row.Comentario,
            'estado': row.Estado
        })

    conn.close()

    if estudiante:
        estudiante_data = {
            'id': estudiante.Matricula,
            'nombre': estudiante.NombreCompleto,
            'edad': estudiante.Edad,
            'domicilio': estudiante.Domicilio,
            'carrera': estudiante.Carrera
        }
        return render_template('registro.html', estudiante=estudiante_data, registros=registros)
    else:
        return redirect(url_for('index'))

@app.route('/registroalcohol')
def registro_alcohol():
    matricula = request.args.get('matricula')
    if not matricula:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT E.Matricula, 
               P.Nombre + ' ' + P.APaterno + ' ' + P.AMaterno AS NombreCompleto,
               P.Edad, 
               'Calle ' + CAST(P.idPersona AS VARCHAR) + ', Col. Centro' AS Domicilio,
               C.Carrera
        FROM Estudiantes E
        JOIN Personas P ON E.idPersona = P.idPersona
        JOIN AsignacionTutores AT ON E.idAsignacion = AT.idAsignacion
        JOIN Grupos G ON AT.idGrupo = G.idGrupo
        JOIN Carreras C ON G.idCarrera = C.idCarrera
        WHERE E.Matricula = ?
    """, (matricula,))
    estudiante = cursor.fetchone()

    cursor.execute("""
        SELECT A.idAutorizado AS id, 
               Per.Nombre + ' ' + Per.APaterno AS nombre
        FROM Autorizados A
        JOIN Personas Per ON A.idPersona = Per.idPersona
    """)
    operadores = cursor.fetchall()

    conn.close()

    if estudiante:
        estudiante_data = {
            'id': estudiante.Matricula,
            'nombre': estudiante.NombreCompleto,
            'edad': estudiante.Edad,
            'domicilio': estudiante.Domicilio,
            'carrera': estudiante.Carrera
        }
        niveles = [round(i * 0.05, 2) for i in range(0, 41)]
        operadores_list = [{'id': row.id, 'nombre': row.nombre} for row in operadores]
        return render_template('registroalcohol.html', 
                              estudiante=estudiante_data, 
                              niveles=niveles, 
                              operadores=operadores_list)
    else:
        return redirect(url_for('index'))

@app.route('/registraralcohol', methods=['POST'])
def registrar_alcohol():
    matricula = request.form['matricula']
    fecha = request.form['fecha']
    hora = request.form['hora']
    id_operador = request.form['id_operador']
    nivel = request.form['nivel']
    comentario = request.form['comentario']

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()  # Crear cursor dentro del bloque try

        cursor.execute("SELECT idPersona FROM Estudiantes WHERE Matricula = ?", (matricula,))
        result = cursor.fetchone()
        
        if not result:
            flash('Estudiante no encontrado', 'error')
            return redirect(url_for('registroalcohol', matricula=matricula))
            
        id_persona = result[0]

        cursor.execute("""
            INSERT INTO Registros (Fecha, Hora, idPersona, idAutorizado, Medicion, Comentario)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fecha, hora, id_persona, id_operador, nivel, comentario))

        conn.commit()
        flash('Registro creado exitosamente', 'success')
        return redirect(url_for('registro', matricula=matricula))
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error al crear registro: {str(e)}', 'error')
        return redirect(url_for('registroalcohol', matricula=matricula))
    finally:
        if conn:
            conn.close()  # Cerrar conexión en el bloque finally

@app.route('/acerca')
def acerca():
    return render_template('acerca.html')

@app.route('/encuesta')
def encuesta():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener opciones de satisfacción desde la BD
        cursor.execute("SELECT idSatisfaccion, Descripcion FROM Satisfacciones")
        opciones_satisfaccion = cursor.fetchall()
        
        conn.close()
        
        # Pasar las opciones al template
        return render_template('encuesta.html', opciones_satisfaccion=opciones_satisfaccion)
    except Exception as e:
        print(f"Error al cargar opciones de satisfacción: {str(e)}")
        # En caso de error, usar opciones por defecto
        opciones_por_defecto = [
            (1, '1 - Muy Malo'),
            (2, '2 - Malo'),
            (3, '3 - Regular'),
            (4, '4 - Bueno'),
            (5, '5 - Excelente')
        ]
        return render_template('encuesta.html', opciones_satisfaccion=opciones_por_defecto)
    
@app.route('/confirmacion_encuesta')
def confirmacion_encuesta():
    encuesta_id = request.args.get('encuesta_id')
    
    if not encuesta_id:
        flash('No se especificó una encuesta para mostrar', 'error')
        return redirect(url_for('encuesta'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener detalles de la encuesta
        cursor.execute("""
            SELECT E.idEncuesta, E.nombre, E.email, E.comentario, E.fecha, S.Descripcion 
            FROM Encuesta E
            JOIN Satisfacciones S ON E.idSatisfaccion = S.idSatisfaccion
            WHERE E.idEncuesta = ?
        """, (encuesta_id,))
        
        encuesta = cursor.fetchone()
        conn.close()
        
        if not encuesta:
            flash('No se encontró la encuesta solicitada', 'error')
            return redirect(url_for('encuesta'))
        
        # Preparar datos para la plantilla
        encuesta_data = {
            'id': encuesta.idEncuesta,
            'nombre': encuesta.nombre,
            'email': encuesta.email,
            'comentario': encuesta.comentario,
            'fecha': encuesta.fecha,
            'satisfaccion': encuesta.Descripcion
        }
        
        return render_template('confirmacion_encuesta.html', encuesta=encuesta_data)
        
    except Exception as e:
        flash(f'Error al cargar la encuesta: {str(e)}', 'error')
        return redirect(url_for('encuesta'))

@app.route('/lista_encuestas')
def lista_encuestas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener todas las encuestas
        cursor.execute("""
            SELECT E.idEncuesta, E.nombre, E.email, E.fecha, S.Descripcion 
            FROM Encuesta E
            JOIN Satisfacciones S ON E.idSatisfaccion = S.idSatisfaccion
            ORDER BY E.fecha DESC
        """)
        
        encuestas = []
        for row in cursor.fetchall():
            encuestas.append({
                'id': row.idEncuesta,
                'nombre': row.nombre,
                'email': row.email,
                'fecha': row.fecha,
                'satisfaccion': row.Descripcion
            })
        
        conn.close()
        return render_template('lista_encuestas.html', encuestas=encuestas)
        
    except Exception as e:
        flash(f'Error al cargar las encuestas: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/guardar_encuesta', methods=['POST'])
def guardar_encuesta():
    conn = None
    try:
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip()
        id_satisfaccion = request.form.get('satisfaccion')
        comentario = request.form.get('comentario', '').strip()
        fecha = request.form.get('fecha', '')
        
        # Validación básica
        if not nombre or not email or not id_satisfaccion or not fecha:
            flash('Por favor, completa todos los campos obligatorios', 'error')
            return redirect(url_for('encuesta'))
        
        # Validar formato de email
        if '@' not in email or '.' not in email:
            flash('Correo electrónico inválido', 'error')
            return redirect(url_for('encuesta'))

        # Convertir satisfacción a entero
        try:
            id_satisfaccion = int(id_satisfaccion)
            if not (1 <= id_satisfaccion <= 5):
                raise ValueError()
        except (ValueError, TypeError):
            flash('Valor de satisfacción inválido', 'error')
            return redirect(url_for('encuesta'))

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar encuesta
        cursor.execute("""
            INSERT INTO Encuesta (nombre, email, idSatisfaccion, comentario, fecha)
            OUTPUT INSERTED.idEncuesta
            VALUES (?, ?, ?, ?, ?)
        """, (nombre, email, id_satisfaccion, comentario, fecha))
        
        # Obtener ID de la encuesta recién creada
        encuesta_id = cursor.fetchone()[0]
        conn.commit()
        
        # Redirigir a la página de confirmación con el ID
        return redirect(url_for('confirmacion_encuesta', encuesta_id=encuesta_id))
    
    except Exception as e:
        flash(f'Error al guardar la encuesta: {str(e)}', 'error')
        return redirect(url_for('encuesta'))
    
    finally:
        if conn:
            conn.close()

@app.route('/detalle_encuesta')
def detalle_encuesta():
    encuesta_id = request.args.get('encuesta_id')
    
    if not encuesta_id:
        flash('No se especificó una encuesta para mostrar', 'error')
        return redirect(url_for('lista_encuestas'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener detalles de la encuesta
        cursor.execute("""
            SELECT E.idEncuesta, E.nombre, E.email, E.comentario, E.fecha, S.Descripcion 
            FROM Encuesta E
            JOIN Satisfacciones S ON E.idSatisfaccion = S.idSatisfaccion
            WHERE E.idEncuesta = ?
        """, (encuesta_id,))
        
        encuesta = cursor.fetchone()
        conn.close()
        
        if not encuesta:
            flash('No se encontró la encuesta solicitada', 'error')
            return redirect(url_for('lista_encuestas'))
        
        # Preparar datos para la plantilla
        encuesta_data = {
            'id': encuesta.idEncuesta,
            'nombre': encuesta.nombre,
            'email': encuesta.email,
            'comentario': encuesta.comentario,
            'fecha': encuesta.fecha,
            'satisfaccion': encuesta.Descripcion
        }
        
        return render_template('detalle_encuesta.html', encuesta=encuesta_data)
        
    except Exception as e:
        flash(f'Error al cargar la encuesta: {str(e)}', 'error')
        return redirect(url_for('lista_encuestas'))
            
@app.route('/perfil')
def perfil():
    matricula = request.args.get('matricula')
    estudiante = None
    if matricula:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT E.Matricula, 
                       P.Nombre + ' ' + P.APaterno + ' ' + P.AMaterno AS NombreCompleto,
                       P.Edad, 
                       'Calle ' + CAST(P.idPersona AS VARCHAR) + ', Col. Centro' AS Domicilio,
                       C.Carrera,
                       P.email
                FROM Estudiantes E
                JOIN Personas P ON E.idPersona = P.idPersona
                JOIN AsignacionTutores AT ON E.idAsignacion = AT.idAsignacion
                JOIN Grupos G ON AT.idGrupo = G.idGrupo
                JOIN Carreras C ON G.idCarrera = C.idCarrera
                WHERE E.Matricula = ?
            """, (matricula,))
            estudiante = cursor.fetchone()
        except pyodbc.Error as e:
            print(f"Error de base de datos: {e}")
        finally:
            if conn:
                conn.close()
    return render_template('perfil.html', estudiante=estudiante)

@app.route('/logout')
def logout():
    return redirect(url_for('index'))

# Rutas para editar y eliminar registros
@app.route('/eliminar_registro/<int:id_registro>', methods=['POST'])
def eliminar_registro(id_registro):
    matricula = request.args.get('matricula')
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Registros WHERE idRegistro = ?", (id_registro,))
        conn.commit()
        flash('Registro eliminado exitosamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar registro: {str(e)}', 'error')
    finally:
        if conn:
            conn.close()
    return redirect(url_for('registro', matricula=matricula))

@app.route('/editar_registro/<int:id_registro>')
def editar_registro(id_registro):
    matricula = request.args.get('matricula')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT R.idRegistro, R.Fecha, R.Hora, R.Medicion, R.idAutorizado, R.Comentario
        FROM Registros R
        WHERE R.idRegistro = ?
    """, (id_registro,))
    registro = cursor.fetchone()
    
    cursor.execute("""
        SELECT A.idAutorizado AS id, 
               Per.Nombre + ' ' + Per.APaterno AS nombre
        FROM Autorizados A
        JOIN Personas Per ON A.idPersona = Per.idPersona
    """)
    operadores = cursor.fetchall()
    conn.close()

    if registro:
        fecha_str = registro.Fecha
        if isinstance(fecha_str, str) and ' ' in fecha_str:
            fecha_str = fecha_str.split()[0]
        
        hora_str = registro.Hora
        if isinstance(hora_str, str) and ' ' in hora_str:
            hora_str = hora_str.split()[1][:5]
        
        registro_data = {
            'idRegistro': registro.idRegistro,
            'Fecha': registro.Fecha,
            'Hora': registro.Hora,
            'Medicion': registro.Medicion,
            'idAutorizado': registro.idAutorizado,
            'Comentario': registro.Comentario
        }
        
        return render_template('editar_registro.html', 
                              registro=registro_data,
                              fecha=fecha_str,
                              hora=hora_str,
                              operadores=operadores,
                              matricula=matricula)
    return redirect(url_for('registro', matricula=matricula))

@app.route('/actualizar_registro/<int:id_registro>', methods=['POST'])
def actualizar_registro(id_registro):
    matricula = request.form['matricula']
    fecha = request.form['fecha']
    hora = request.form['hora']
    id_operador = request.form['id_operador']
    nivel = request.form['nivel']
    comentario = request.form['comentario']
    
    conn = None
    try:
        # Validar datos antes de guardar
        if not fecha or not hora or not id_operador or not nivel:
            flash('Todos los campos obligatorios deben completarse', 'error')
            return redirect(url_for('editar_registro', id_registro=id_registro, matricula=matricula))
        
        # Convertir nivel a float con validación
        try:
            nivel = float(nivel)
            if nivel < 0 or nivel > 2:
                flash('El nivel de alcohol debe estar entre 0 y 2 g/L', 'error')
                return redirect(url_for('editar_registro', id_registro=id_registro, matricula=matricula))
        except ValueError:
            flash('El nivel de alcohol debe ser un número válido', 'error')
            return redirect(url_for('editar_registro', id_registro=id_registro, matricula=matricula))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Actualizar registro
        cursor.execute("""
            UPDATE Registros 
            SET Fecha = ?, 
                Hora = ?, 
                idAutorizado = ?, 
                Medicion = ?, 
                Comentario = ?
            WHERE idRegistro = ?
        """, (fecha, hora, id_operador, nivel, comentario, id_registro))
        
        conn.commit()
        flash('Registro actualizado exitosamente', 'success')
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error al actualizar registro: {str(e)}', 'error')
    finally:
        if conn:
            conn.close()
    return redirect(url_for('registro', matricula=matricula))

if __name__ == '__main__':
    check_and_create_tables()  # Verificar/crear tablas al iniciar
    app.run(host='0.0.0.0', port=5000, debug=True)