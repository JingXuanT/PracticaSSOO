from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import time
import random

app= Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins ="*")

partidas ={}
CATEGORIAS_BASE =['nombre', 'apellido', 'animal', 'comida', 'fruta', 'color', 'pais', 'objeto']

def temporizador_partida(room):
    socketio.sleep(60) 

    if room in partidas and partidas[room]['activa']:
        partidas[room]['activa'] = False
        socketio.emit('fin_juego', {
            'razon': '¡Tiempo agotado!',
            'tablero': partidas[room]['categorias']
        }, room=room)

@socketio.on('iniciar_juego')
def iniciar(data):
    room = str(data['room'])
    letra_elegida = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    partidas[room] = {
        'letra': letra_elegida,
        'categorias': {cat: "" for cat in CATEGORIAS_BASE},
        'activa': True
    }
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
        }, to=request.sid) 
@app.route('/stop/<int:game_id>')
def index(game_id):
    return render_template('juego.html', game_id = game_id)

@socketio.on('join')
def handle_join(data):
    room = str(data['room'])
    join_room(room)
    if room not in partidas:
        partidas[room] = {'categorias': {}}
    print(f"Jugador unido a la partida: {room}")

@socketio.on('escribiendo')
def handle_typing(data):
    room = str(data['room'])
    cat = data['categoria']

    emit ('bloquear_categoria', {'cat':cat}, room = room, include_self= False)

@socketio.on('palabra_lista')
def handle_word(data): 
    room = str(data['room'])
    cat = data ['categoria']
    val = data['valor']

    partidas[room]['categorias'][cat]=val

    emit('actualizar_tablero', {'cat': cat, 'val':val}, room = room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port =5000)
