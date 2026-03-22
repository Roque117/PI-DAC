import pyodbc

def test_aws_connection(endpoint, username, password):
    """
    Prueba la conexión al servidor SQL Server en AWS RDS usando la base de datos 'master'
    
    Parámetros:
    endpoint : Dirección del servidor RDS (ej: 'mi-instancia.xxxxxx.us-east-1.rds.amazonaws.com,1433')
    username : Usuario administrador
    password : Contraseña del usuario
    """
    # Construir cadena de conexión
    connection_string = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={endpoint};"
        f"DATABASE=master;"  # Usamos la base de datos maestra
        f"UID={username};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"  # Importante para pruebas iniciales
    )

    try:
        # Establecer conexión
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        # 1. Verificar versión de SQL Server
        cursor.execute("SELECT @@VERSION AS version")
        version = cursor.fetchone()[0]
        
        # 2. Listar bases de datos existentes
        cursor.execute("SELECT name FROM sys.databases")
        databases = [db[0] for db in cursor.fetchall()]
        
        # 3. Verificar el estado del servidor
        cursor.execute("SELECT @@SERVERNAME AS server, DB_NAME() AS current_db")
        server_info = cursor.fetchone()
        
        # Mostrar resultados
        print("\n✅ ¡Conexión exitosa a AWS RDS!")
        print(f"• Servidor: {server_info.server}")
        print(f"• Versión SQL Server: {version}")
        print(f"• Base de datos actual: {server_info.current_db}")
        print("\n📊 Bases de datos disponibles:")
        for i, db in enumerate(databases, 1):
            print(f"  {i}. {db}")
        
        # Crear una nueva base de datos si no existe (opcional)
        new_db_name = "MiNuevaBaseDeDatos"
        if new_db_name not in databases:
            cursor.execute(f"CREATE DATABASE {new_db_name}")
            conn.commit()
            print(f"\n🆕 Base de datos '{new_db_name}' creada exitosamente!")
        
        conn.close()
        return True
        
    except pyodbc.Error as ex:
        print("\n❌ Error de conexión:")
        print(f"Código: {ex.args[0]}")
        print(f"Mensaje: {ex.args[1]}")
        
        # Diagnóstico de errores comunes
        if "08001" in str(ex):
            print("\n🔍 Posibles soluciones:")
            print("1. Verifica que el endpoint es correcto")
            print("2. Asegúrate que el Security Group permite tu IP en el puerto 1433")
            print("3. Comprueba que la instancia RDS está en estado 'Available'")
            
        elif "28000" in str(ex):
            print("\n🔍 Posibles soluciones:")
            print("1. Revisa el usuario y contraseña")
            print("2. Verifica que el usuario tiene privilegios en la instancia")
            
        return False

# Configuración para AWS RDS (REEMPLAZA CON TUS DATOS)
test_aws_connection(
    endpoint="dac.cutoyos8emc9.us-east-1.rds.amazonaws.com,1433",  # Ej: "mi-db.abc123.us-east-1.rds.amazonaws.com,1433"
    username="admin",                              # Usuario maestro que creaste
    password="admin123"                # Contraseña del usuario
)