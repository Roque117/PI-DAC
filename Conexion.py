import pyodbc

class ConexionDB:
    def __init__(self):
        try:
            self.connection = pyodbc.connect(
                'DRIVER={SQL Server};'
                'SERVER=LAPTOP-AB79J7C2;'
                'DATABASE=Alcolimetro;'
                'Trusted_Connection=yes;'
            )
            self.cursor = self.connection.cursor()
            self.errMss = ''
        except Exception as ex:
            self.errMss = str(ex)
            self.connection = None
            self.cursor = None
    
    def execute_query(self, query, params=None):
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
                
            if query.strip().upper().startswith('SELECT'):
                return self.cursor.fetchall()
            else:
                self.connection.commit()
                return True
        except Exception as ex:
            print(f'Error al ejecutar la consulta: {ex}')
            return None

