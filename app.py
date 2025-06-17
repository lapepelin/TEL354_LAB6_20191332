import yaml
import requests

# --- Clases ---
class Alumno:
    def __init__(self, nombre, mac):
        self.nombre = nombre
        self.mac = mac

class Servicio:
    def __init__(self, nombre, protocolo, puerto):
        self.nombre = nombre
        self.protocolo = protocolo
        self.puerto = puerto

class Servidor:
    def __init__(self, nombre, direccion_ip):
        self.nombre = nombre
        self.direccion_ip = direccion_ip
        self.servicios = []

    def agregar_servicio(self, servicio):
        self.servicios.append(servicio)

class Curso:
    def __init__(self, nombre, estado):
        self.nombre = nombre
        self.estado = estado
        self.alumnos = []
        self.servidores = []

    def agregar_alumno(self, alumno):
        self.alumnos.append(alumno)

    def remover_alumno(self, alumno):
        if alumno in self.alumnos:
            self.alumnos.remove(alumno)

    def agregar_servidor(self, servidor):
        self.servidores.append(servidor)

# --- Funciones REST ---
def get_attachment_points(controller_ip, mac):
    url = f'http://{controller_ip}:8080/wm/device/'
    r = requests.get(url)
    if r.status_code == 200:
        devices = r.json()
        for device in devices:
            # La MAC puede venir como lista, compara en minúsculas
            if mac.lower() in [m.lower() for m in device.get('mac', [])]:
                # Algunos hosts pueden tener múltiples attachment points
                for ap in device.get('attachmentPoint', []):
                    dpid = ap.get('switchDPID')
                    port = ap.get('port')
                    return dpid, port
    return None, None # Si no se encuentra

def get_route(controller_ip, src_dpid, src_port, dst_dpid, dst_port):
    url = f'http://{controller_ip}:8080/wm/topology/route/{src_dpid}/{src_port}/{dst_dpid}/{dst_port}/json'
    r = requests.get(url)
    if r.status_code == 200:
        # La respuesta es una lista de hops (cada hop: switch, puerto)
        route = r.json()
        # lista de (dpid, puerto)
        hops = [(str(hop['switch']), hop['port']) for hop in route]
        return hops
    return []

def importar_yaml(ruta):
    with open('datos.yaml', 'r') as f:
    data = yaml.safe_load(f)

    if 'servidores' in data:
    print("Nombres de los servidores:")
        for servidor in data['servidores']:
            print(servidor['nombre'])
    else:
    print("No se encontró la lista de servidores en el archivo YAML.")

def exportar_yaml(ruta):
    return 0
    
def submenu_cursos():
    while True:
        print("1. Crear curso")
        print("2. Listar cursos")
        print("3. Mostrar detalle de curso")
        print("4. Agregar alumno a curso")
        print("5. Quitar alumno de curso")
        print("6. Volver")
        op = input("> ")
        if op == "1":
            # Lógica para crear curso
            ...
        elif op == "2":
            # Lógica para listar
            ...
        # y así sucesivamente
        elif op == "6":
            break

def submenu_alumnos():

def submenu_servidores():

def submenu_politicas():

def submenu_conexiones():

# --- Menú Principal ---
def menu_principal():
    while True:
        print("1. Importar")
        print("2. Exportar")
        print("3. Cursos")
        print("4. Alumnos")
        print("5. Servidores")
        print("6. Políticas")
        print("7. Conexiones")
        print("8. Salir")
        op = input("> ")
        if op == "1":
            importar_yaml()
            ...
        elif op == "2":
            exportar_yaml()
            ...
        elif op == "3":
            submenu_cursos()
        elif op == "4":
            submenu_alumnos()
        elif op == "5":
            submenu_servidores()
        elif op == "6":
            submenu_politicas()
        elif op == "7":
            submenu_conexiones()
        elif op == "8":
            break
        else:
            print("Opción inválida.")

def main():
    controller_ip = "192.168.200.200"  
    data = {}
    menu_principal()

if __name__ == '__main__':
    main()
