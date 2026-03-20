from bottle import route, run, response, static_file
from datetime import datetime
import json
import subprocess

@route('/')
def inicio():
    return static_file('index.html', root='/var/www/html')

@route('/hi')
def hi():
    actual = datetime.now()
    fecha = actual.strftime("%d/%m/%Y")
    hora = actual.strftime("%H:%M:%S")
    response.content_type = 'application/json'
    return f'Hola, hoy es {fecha} y son las {hora}'

@route('/status')
def status():
    resultado = subprocess.run(
        ['systemctl', 'list-units', '--type=service', '--state=running', '--no-pager', '--plain'],
        capture_output=True,
        text=True
    )
    servicios = []
    for linea in resultado.stdout.strip().split('\n')[1:]:
        partes = linea.split()
        if partes:
            servicios.append(partes[0])
    response.content_type = 'application/json'
    return json.dumps({'servicios': servicios})


@route('/prueba')
def prueba():
    return 'Esto es una prueba de ruta'

run (host ='0.0.0.0', port=8080)
