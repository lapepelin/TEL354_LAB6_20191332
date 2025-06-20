import yaml # Importa la librería para manejar archivos YAML (leer y escribir)
import requests # Importa la librería para hacer peticiones HTTP (API REST)
import sys  # Para manejar argumentos de línea de comandos

# --- Clases ---
class Alumno:
    def __init__(self, nombre, mac, codigo=None):  # Constructor, ahora admite un código opcional
        self.nombre = nombre         # Asigna el nombre al atributo de instancia
        self.mac = mac               # Asigna la MAC al atributo de instancia
        self.codigo = codigo         # Código identificador del alumno
        self.autorizado = autorizado # Indica si el alumno está autorizado

    def esta_autorizado(self):
        """Devuelve True si el alumno está autorizado."""
        return self.autorizado

class Servicio:
    def __init__(self, nombre, protocolo, puerto):
        self.nombre = nombre
        self.protocolo = protocolo
        self.puerto = puerto

class Servidor:
    def __init__(self, nombre, direccion_ip):
        self.nombre = nombre
        self.direccion_ip = direccion_ip
        self.servicios = []        # Lista de servicios que ofrece el servidor

    def agregar_servicio(self, servicio):    # Método para agregar un servicio al servidor
        self.servicios.append(servicio)

class Curso:
    def __init__(self, nombre, estado):
        self.nombre = nombre
        self.estado = estado
        self.alumnos = []    # Lista de alumnos inscritos
        self.servidores = []    # Lista de servidores asociados al curso

    def agregar_alumno(self, alumno):    # Método para agregar un alumno al curso
        self.alumnos.append(alumno)

    def remover_alumno(self, alumno):    # Método para remover un alumno del curso
        if alumno in self.alumnos:
            self.alumnos.remove(alumno)

    def agregar_servidor(self, servidor):    # Método para agregar un servidor al curso
        self.servidores.append(servidor)

class Conexion:
    def __init__(self, handler, alumno, servidor, servicio, ruta=None):
        self.handler = handler
        self.alumno = alumno
        self.servidor = servidor
        self.servicio = servicio
        self.ruta = ruta or []

# Lista global de cursos
cursos = []
conexiones = []
controller_ip = "192.168.200.200"  # Dirección IP del controlador Floodlight

# --- Funciones REST ---
def get_attachment_points(controller_ip, mac):
    # Obtiene el punto de attachment (switch y puerto) para un host por su MAC
    url = f'http://{controller_ip}:8080/wm/device/'    # Construye la URL de la API
    r = requests.get(url)    # Hace el request GET a la API
    if r.status_code == 200:    # Si la respuesta es exitosa
        devices = r.json()    # Convierte la respuesta en JSON (lista de devices)
        for device in devices:    # Recorre los dispositivos detectados
            # La MAC puede venir como lista, compara en minúsculas
            if mac.lower() in [m.lower() for m in device.get('mac', [])]:
                # Algunos hosts pueden tener múltiples attachment points
                for ap in device.get('attachmentPoint', []):
                    dpid = ap.get('switchDPID')    # ID del switch al que está conectado el host
                    port = ap.get('port')    # Puerto del switch al que está conectado
                    return dpid, port    # Retorna el DPID y el puerto
    return None, None # Si no se encuentra, devuelve None

def get_route(controller_ip, src_dpid, src_port, dst_dpid, dst_port):
    # Obtiene la ruta (lista de switches y puertos) entre dos puntos de la red
    url = f'http://{controller_ip}:8080/wm/topology/route/{src_dpid}/{src_port}/{dst_dpid}/{dst_port}/json'
    r = requests.get(url)    # Hace el request GET a la API
    if r.status_code == 200:
        # La respuesta es una lista de hops (cada hop: switch, puerto)
        route = r.json()   
        # lista de (dpid, puerto)
        hops = [(str(hop['switch']), hop['port']) for hop in route]    # Arma una lista de tuplas (dpid, puerto)
        return hops    # Retorna la lista de saltos
    return []    # Si falla, retorna lista vacía

def build_route(controller_ip, ruta, mac_src, ip_src, mac_dst, ip_dst, proto_l4, puerto_l4):
    """
    Crea los flows necesarios a lo largo de la ruta para permitir tráfico entre src y dst.
    """
    for idx, (dpid, in_port) in enumerate(ruta):
        # Ejemplo genérico

        flow = {
            "switch": dpid,
            "name": f"fwd_{mac_src}_{mac_dst}_{puerto_l4}_{idx}",
            "priority": "40000",
            "eth_type": "0x0800", # IPv4
            "ipv4_src": ip_src,
            "ipv4_dst": ip_dst,
            "ip_proto": proto_l4,  # 6 para TCP, 17 para UDP
            "tp_dst": puerto_l4,   # puerto destino
            "in_port": in_port,
            "active": "true",
            "actions": "output=ALL"
        }
        url = f"http://{controller_ip}:8080/wm/staticflowpusher/json"
        resp = requests.post(url, json=flow)
        if resp.status_code == 200:
            print(f"Flow instalado en {dpid}:{in_port}")
        else:
            print(f"Error instalando flow en {dpid}:{in_port}")
            
def calcular_ruta(alumno, servidor):
    """Obtiene la ruta actual entre un alumno y un servidor."""
    dpid_src, port_src = get_attachment_points(controller_ip, alumno.mac)
    dpid_dst, port_dst = get_attachment_points(controller_ip, servidor.mac)

    if not dpid_src or not dpid_dst:
        return []

    return get_route(controller_ip, dpid_src, port_src, dpid_dst, port_dst)

def importar_yaml(ruta):
    global cursos
    with open(ruta, 'r') as f:
        data = yaml.safe_load(f)

    alumnos_dict = {}
    if 'alumnos' in data:
        for a in data['alumnos']:
            alumnos_dict[a['codigo']] = Alumno(a['nombre'], a['mac'], a['codigo'])

    servidores_dict = {}
    if 'servidores' in data:
        for s in data['servidores']:
            srv = Servidor(s['nombre'], s['direccion_ip'])
            srv.mac = s.get('mac', None)
            for svc in s.get('servicios', []):
                srv.agregar_servicio(Servicio(svc['nombre'], svc['protocolo'], svc['puerto']))
            servidores_dict[s['nombre']] = srv

    cursos.clear()
    if 'cursos' in data:
        for c in data['cursos']:
            curso = Curso(c['nombre'], c['estado'])
            # Asocia alumnos
            for cod in c.get('alumnos', []):
                if cod in alumnos_dict:
                    curso.agregar_alumno(alumnos_dict[cod])
            # Asocia servidores y filtra servicios permitidos
            for srv_obj in c.get('servidores', []):
                srv = servidores_dict.get(srv_obj['nombre'])
                if srv:
                    # Si tienes "servicios_permitidos", crea una nueva lista solo con esos servicios
                    if 'servicios_permitidos' in srv_obj:
                        nuevos_servicios = [s for s in srv.servicios if s.nombre in srv_obj['servicios_permitidos']]
                        srv.servicios = nuevos_servicios
                    curso.agregar_servidor(srv)
            cursos.append(curso)
    print("Datos importados correctamente.")
    
def submenu_cursos():

    # ...dentro de tu opción "1. Crear" en submenu_conexiones:
    curso_nom = input("Curso: ")
    curso = next((c for c in cursos if c.nombre == curso_nom), None)
    if not curso:
        print("Curso no encontrado.")
        continue
    if curso.estado != "DICTANDO":
        print("El curso no está activo.")
        continue
    # Selección del alumno
    # ...
    alumno = curso.alumnos[int(idx) - 1]
    # Asegúrate que alumno esté en curso.alumnos (ya lo seleccionas de ahí, así que bien)
    
    # Selección del servidor
    # ...
    servidor = curso.servidores[int(idx) - 1]
    # Verifica que el servidor está en curso.servidores (también ok porque seleccionas de ahí)
    
    # Selección del servicio
    # ...
    servicio = servidor.servicios[int(idx) - 1]
    # Ahora verifica si el servicio está en la lista de servicios permitidos del curso (si tu estructura los maneja así)
    # Si tienes una lista tipo curso.servicios_permitidos o algo similar, comprueba aquí
    
    # Aquí podrías tener una función extra de autorización, pero en tu flujo, si seleccionas todo desde los objetos de curso,
    # ya se cumple la mayor parte. Pero, SIEMPRE antes de crear la conexión, chequea TODO:
    
    if alumno not in curso.alumnos:
        print("El alumno no está matriculado en este curso.")
        continue
    if servidor not in curso.servidores:
        print("Servidor no permitido en este curso.")
        continue
    if servicio not in servidor.servicios:
        print("Servicio no permitido en este servidor.")
        continue
    
    # Solo aquí creas la conexión
    handler = f"con{len(conexiones)+1}"
    conexiones.append(Conexion(handler, alumno, servidor, servicio, ruta))
    print(f"Conexión creada con handler {handler}")
    
    # Submenú para manejar las operaciones sobre cursos (Listar, Detalle, Actualizar)
    while True:
        print("1. Listar")
        print("2. Mostrar detalle")
        print("3. Actualizar")
        print("4. Volver")
        op = input("> ")
        if op == "1":
            if not cursos:    # Si la lista de cursos está vacía
                print("No hay cursos registrados.")
            else:
                for idx, c in enumerate(cursos, 1):    # Imprime la lista de cursos con índice
                    print(f"{idx}. {c.nombre} - {c.estado}")
        elif op == "2":
            nombre = input("Nombre del curso: ")    # Pide el nombre del curso a mostrar
            curso = next((c for c in cursos if c.nombre == nombre), None)    # Busca el curso por nombre
            if curso:
                print(f"Nombre: {curso.nombre}")
                print(f"Estado: {curso.estado}")
                if curso.alumnos:
                    print("Alumnos:")
                    for a in curso.alumnos:
                        print(f"- {a.nombre} ({a.mac})")
                else:
                    print("Sin alumnos")
            else:
                print("Curso no encontrado.")
        elif op == "3":
            nombre = input("Nombre del curso: ")    # Pide el nombre del curso a actualizar
            curso = next((c for c in cursos if c.nombre == nombre), None)
            if not curso:
                print("Curso no encontrado.")
                continue
            print("1. Agregar alumno")
            print("2. Eliminar alumno")
            subop = input("> ")
            if subop == "1":
                nom = input("Nombre del alumno: ")     # Pide datos para crear el alumno
                mac = input("MAC del alumno: ")
                codigo = input("Código del alumno (opcional): ")
                # Agrega el alumno con código si se proporciona
                if codigo == "":
                    codigo = None
                curso.agregar_alumno(Alumno(nom, mac, codigo))
            elif subop == "2":
                if not curso.alumnos:
                    print("No hay alumnos para eliminar.")
                else:
                    for i, a in enumerate(curso.alumnos, 1):    #Lista los alumnos para elegir
                        print(f"{i}. {a.nombre}")
                    idx = input("Seleccione alumno: ")    # Pide el índice del alumno a borrar
                    if idx.isdigit() and 1 <= int(idx) <= len(curso.alumnos):
                        curso.remover_alumno(curso.alumnos[int(idx) - 1])    # Remueve al alumno
                    else:
                        print("Índice inválido.")
            else:
                print("Opción inválida.")
        elif op == "4":
            break    # Sale del submenú de cursos
        else:
            print("Opción inválida.")

def submenu_alumnos():
    # Permite listar alumnos existentes y ver sus detalles
    while True:
        print("1. Listar")
        print("2. Mostrar detalle")
        print("3. Volver")
        op = input("> ")
        if op == "1":
            filtro = input("Filtrar por curso (dejar en blanco para todos): ")
            encontrados = False
            for curso in cursos:
                if filtro and curso.nombre != filtro:
                    continue
                for a in curso.alumnos:
                    codigo = getattr(a, "codigo", None)
                    cod_str = codigo if codigo is not None else "N/A"
                    print(f"{cod_str} - {a.nombre} ({a.mac})")
                    encontrados = True
            if not encontrados:
                print("No hay alumnos registrados.")
        elif op == "2":
            nombre = input("Nombre del alumno: ")
            alumno = None
            for curso in cursos:
                for a in curso.alumnos:
                    if a.nombre == nombre:
                        alumno = a
                        break
                if alumno:
                    break
            if alumno:
                codigo = getattr(alumno, "codigo", None)
                cod_str = codigo if codigo is not None else "N/A"
                print(f"Código: {cod_str}")
                print(f"Nombre: {alumno.nombre}")
                print(f"MAC: {alumno.mac}")
            else:
                print("Alumno no encontrado.")
        elif op == "3":
            break
        else:
            print("Opción inválida.")

def submenu_servidores():
    # Permite listar los servidores y ver detalles de cada uno
    while True:
        print("1. Listar")
        print("2. Mostrar detalle")
        print("3. Volver")
        op = input("> ")
        if op == "1":
            filtro = input("Filtrar por curso (dejar en blanco para todos): ")
            encontrados = False
            for curso in cursos:
                if filtro and curso.nombre != filtro:
                    continue
                for s in curso.servidores:
                    print(f"{s.nombre} - {s.direccion_ip}")
                    encontrados = True
            if not encontrados:
                print("No hay servidores registrados.")
        elif op == "2":
            nombre = input("Nombre del servidor: ")
            servidor = None
            for curso in cursos:
                for s in curso.servidores:
                    if s.nombre == nombre:
                        servidor = s
                        break
                if servidor:
                    break
            if servidor:
                if servidor.servicios:
                    print("Servicios:")
                    for svc in servidor.servicios:
                        print(f"- {svc.nombre} {svc.protocolo}/{svc.puerto}")
                else:
                    print("El servidor no tiene servicios registrados.")
            else:
                print("Servidor no encontrado.")
        elif op == "3":
            break
        else:
            print("Opción inválida.")

def submenu_conexiones():
    while True:
        print("1. Crear")
        print("2. Listar")
        print("3. Mostrar detalle")
        print("4. Recalcular")
        print("5. Actualizar")
        print("6. Borrar")
        print("7. Volver")
        op = input("> ")
        if op == "1":
            curso_nom = input("Curso: ")
            curso = next((c for c in cursos if c.nombre == curso_nom), None)
            if not curso:
                print("Curso no encontrado.")
                continue
            if not curso.alumnos:
                print("El curso no tiene alumnos.")
                continue
            for i, a in enumerate(curso.alumnos, 1):
                print(f"{i}. {a.nombre}")
            idx = input("Seleccione alumno: ")
            if not idx.isdigit() or not (1 <= int(idx) <= len(curso.alumnos)):
                print("Índice inválido.")
                continue
            alumno = curso.alumnos[int(idx) - 1]
            if not alumno.esta_autorizado():
                print("El alumno no está autorizado para crear conexiones.")
                continue
            if not curso.servidores:
                print("El curso no tiene servidores.")
                continue
            for i, s in enumerate(curso.servidores, 1):
                print(f"{i}. {s.nombre}")
            idx = input("Seleccione servidor: ")
            if not idx.isdigit() or not (1 <= int(idx) <= len(curso.servidores)):
                print("Índice inválido.")
                continue
            servidor = curso.servidores[int(idx) - 1]
            if not servidor.servicios:
                print("El servidor no tiene servicios.")
                continue
            for i, svc in enumerate(servidor.servicios, 1):
                print(f"{i}. {svc.nombre}")
            idx = input("Seleccione servicio: ")
            if not idx.isdigit() or not (1 <= int(idx) <= len(servidor.servicios)):
                print("Índice inválido.")
                continue
                
            servicio = servidor.servicios[int(idx) - 1]
            
            # OBTÉN EL PUNTO DE ATTACHMENT DEL ALUMNO Y DEL SERVIDOR
            dpid_src, port_src = get_attachment_points(controller_ip, alumno.mac)
            dpid_dst, port_dst = get_attachment_points(controller_ip, servidor.mac) # Ojo: servidor.mac debe existir

            if not dpid_src or not dpid_dst:
                print("No se pudo encontrar el punto de attachment para el host o servidor.")
                continue

            # CALCULA LA RUTA ENTRE AMBOS
            ruta = get_route(controller_ip, dpid_src, port_src, dpid_dst, port_dst)

            if not ruta:
                print("No se encontró una ruta válida entre el alumno y el servidor.")
                continue

            # INSTALA LOS FLOWS EN LA RED (AMBOS SENTIDOS)
            proto_l4 = 6 if servicio.protocolo.upper() == "TCP" else 17
            build_route(controller_ip, ruta, alumno.mac, "IP_DEL_ALUMNO", servidor.mac, servidor.direccion_ip, proto_l4, servicio.puerto)

            # CREA LA CONEXIÓN EN EL SISTEMA
            handler = f"con{len(conexiones)+1}"
            conexiones.append(Conexion(handler, alumno, servidor, servicio, ruta))
            print(f"Conexión creada con handler {handler}")
        elif op == "2":
            if not conexiones:
                print("No hay conexiones registradas.")
            else:
                for c in conexiones:
                    print(f"{c.handler}: {c.alumno.nombre} -> {c.servicio.nombre} ({c.servidor.nombre})")
        elif op == "3":
            h = input("Handler: ")
            con = next((c for c in conexiones if c.handler == h), None)
            if con:
                if con.ruta:
                    print("Ruta:")
                    for dpid, port in con.ruta:
                        print(f"- {dpid}:{port}")
                else:
                    print("Sin ruta")
            else:
                print("Conexión no encontrada.")
        elif op == "4":
            h = input("Handler: ")
            con = next((c for c in conexiones if c.handler == h), None)
            if con:
                nueva = calcular_ruta(con.alumno, con.servidor)
                if nueva:
                    for dpid, port in nueva:
                        print(f"- {dpid}:{port}")
                else:
                    print("No se pudo calcular la ruta.")
            else:
                print("Conexión no encontrada.")
        elif op == "5":
            h = input("Handler: ")
            con = next((c for c in conexiones if c.handler == h), None)
            if con:
                nueva = calcular_ruta(con.alumno, con.servidor)
                if nueva:
                    con.ruta = nueva
                    print("Ruta actualizada.")
                else:
                    print("No se pudo calcular la ruta.")
            else:
                print("Conexión no encontrada.")
        elif op == "6":
            h = input("Handler: ")
            for i, c in enumerate(conexiones):
                if c.handler == h:
                    if not c.alumno.esta_autorizado():
                        print("El alumno no está autorizado para eliminar esta conexion.")
                        break
                    del conexiones[i]
                    print("Conexión eliminada.")
                    break
            else:
                print("Conexión no encontrada.")
        elif op == "7":
            break
        else:
            print("Opción inválida.")

# --- Menú Principal ---
def menu():
    while True:
        print("1. Importar")
        print("2. Exportar")    # <- SOLO OPCIÓN, no implementada
        print("3. Cursos")
        print("4. Alumnos")
        print("5. Servidores")
        print("6. Políticas")    # <- SOLO OPCIÓN, no implementada
        print("7. Conexiones")
        print("8. Salir")
        op = input("> ")
        if op == "1":
            ruta = input("Archivo YAML a importar: ")
            importar_yaml(ruta)
        elif op == "2":
            print("Función de exportar no implementada todavía.")
        elif op == "3":
            submenu_cursos()
        elif op == "4":
            submenu_alumnos()
        elif op == "5":
            submenu_servidores()
        elif op == "6":
            print("Módulo de políticas aún no implementado.")  
        elif op == "7":
            submenu_conexiones()
        elif op == "8":
            break
        else:
            print("Opción inválida.")

def main():

    """Carga opcionalmente un archivo YAML y luego inicia el menú."""
    ruta = None
    # Si se pasa una ruta como argumento, úsala; de lo contrario pregunta al usuario
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
    else:
        ruta = input(
            "Archivo YAML inicial (dejar vacío para continuar sin importar): "
        ).strip()

    if ruta:
        try:
            importar_yaml(ruta)
        except Exception as exc:
            print(f"Error al importar '{ruta}': {exc}")
    
    menu()

if __name__ == '__main__':
    main()
