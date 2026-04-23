from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import time
import random

app= Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins ="*")

partidas ={}
CATEGORIAS_BASE =['nombre', 'apellido', 'animal', 'comida', 'fruta', 'color', 'pais', 'objeto']

def temporizador_partida(room):
    socketio.sleep(90)
    if room in partidas and partidas[room]['activa']:
        finalizador_partidas(room, "¡Tiempo agotado!")

def desbloquear_categoria_auto(room, cat):
    socketio.sleep(5)
    if room in partidas and cat in partidas [room]['bloqueos']: 
        del partidas[room]['bloqueos'][cat]
        socketio.emit('desbloquear_categoria', {'cat': cat}, room= room)

def finalizador_partidas(room,razon):
    if room in partidas: 
        partidas[room]['activa'] = False
        socketio.emit('fin_juego', {'razon': razon, 'tablero':partidas[room]['categorias']}, room=room)

@socketio.on('iniciar_juego')
def iniciar(data):
    room = str(data['room'])
    letra_elegida = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")    
    partidas[room] = ({
        'letra': letra_elegida,
        'categorias': {cat: "" for cat in CATEGORIAS_BASE},
        'activa': True
        'bloqueo': {}
        })

    emit('juego_iniciado', {'letra': letra_elegida, 'tiempo': 60}, room=room)
    socketio.start_background_task(temporizador_partida, room)

@socketio.on('palabra_lista')
def recibir_palabra(data):
    room = str(data['room'])
    cat = data['categoria']
    palabra = data['valor'].strip().upper() 

    partida = partidas.get(room)

    if not partida or not partida['activa']:
        return

    letra_juego = partida['letra']

    if palabra.startswith(letra_juego):
        partida['categorias'][cat] = palabra
        if cat in partida['bloqueos']: del partida['bloqueos'][cat]

        emit('actualizar_tablero', {'cat': cat, 'val': palabra}, room=room)

        tablero_lleno = all(valor != "" for valor in partida['categorias'].values())
        if tablero_lleno:
            partida['activa'] = False

            emit('fin_juego', {
                'razon': '¡Tablero completado!', 
                'tablero': partida['categorias']
            }, room=room)

    else:
        emit('error', {
            'msg': f'La palabra debe empezar por la letra {letra_juego}'

@app.route('/stop/<int:game_id>')
def index(game_id):
    return render_template('juego.html', game_id = game_id)

@socketio.on('join')
def handle_join(data):
    room = str(data['room'])
    join_room(room)

    if room not in partidas:
        partidas[room] = {'categorias': {cat: "" for cat in CATEGORIAS_BASE}}
    
    if 'jugadores' not in partidas[room]: 
        partidas [room]['jugadores'] = set()
    
    partidas[room]['jugadores'].add(request.sid)

    cantidad_actual = len(partidas[room]['jugadores'])
    emit('actualizar_jugadores', {'cantidad': cantidad_actual}, room= room)
    print(f"Jugador unido a la partida: {room}. Total: {cantidad_actual}")

@socketio.on('escribiendo')
def handle_typing(data):
    room = str(data['room'])
    cat = data['categoria']

    emit ('bloquear_categoria', {'cat':cat}, room = room, include_self= False)

@app.route('/stop/new')
def crear_partida():
    game_id = str(random.randint(1000,9999))
    partidas[game_id] = {
            'letra': None,
            'activa': False,
            'categorias': { cat: "" for cat in CATEGORIAS_BASE},
            'jugadores': set()
            }
    return redirect(url_for('index', game_id=gameid))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port =5000)
