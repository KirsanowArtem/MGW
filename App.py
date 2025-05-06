import json
import os
import smtplib
import string
import uuid
import random
import string

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory,request, jsonify
import time
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from shutil import copyfile
from PIL import Image
import uuid
import qrcode
import io
import base64
from io import BytesIO


app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATA_FILE = 'data.json'
UPLOAD_FOLDER = 'avatar'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

rooms = {}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def send_email(to_email, subject, body):
    with open('credentials.json') as f:
        creds = json.load(f)
    msg = MIMEText(body, "html")
    msg['Subject'] = subject
    msg['From'] = creds['email']
    msg['To'] = to_email
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(creds['email'], creds['password'])
    server.send_message(msg)
    server.quit()



@app.route('/')
def home():
    return render_template('login.html', title="Вход")

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    data = load_data()
    if username in data and data[username]['password'] == password:
        session['username'] = username
        return redirect(url_for('home_logged'))
    else:
        flash("Неверные данные", "danger")
        return redirect(url_for('home'))

@app.route('/register')
def register():
    return render_template('register.html', title="Регистрация")

@app.route('/register', methods=['POST'])
def register_post():
    username = request.form['username']
    password = request.form['password']
    confirm = request.form['confirm']
    email = request.form['email']
    data = load_data()

    if username in data:
        flash("Имя занято", "danger")
        return redirect(url_for('register'))
    if any(user['email'] == email for user in data.values()):
        flash("Почта уже используется", "danger")
        return redirect(url_for('register'))
    if password != confirm:
        flash("Пароли не совпадают", "danger")
        return redirect(url_for('register'))

    avatar_path = f"{username}.png"
    data[username] = {'password': password, 'email': email, 'avatar': avatar_path}
    save_data(data)

    copyfile('static/default.png', f'avatar/{avatar_path}')

    subject = "Добро пожаловать на сайт!"
    body = f"""
    <h2>Поздравляем, {username}!</h2>
    <p>Вы успешно зарегистрировались на сайте.</p>
    <ul>
        <li>Имя: {username}</li>
        <li>Почта: {email}</li>
        <li>Пароль: {password}</li>
    </ul>
    """
    try:
        send_email(email, subject, body)
    except Exception as e:
        flash(f"Ошибка при отправке письма: {e}", "danger")

    flash("Регистрация успешна, письмо отправлено", "success")
    return redirect(url_for('home'))

@app.route('/forgot')
def forgot():
    return render_template('forgot.html', title="Сброс пароля")

@app.route('/forgot', methods=['POST'])
def forgot_post():
    username = request.form['username']
    email = request.form['email']
    data = load_data()
    if username in data and data[username]['email'] == email:
        token = str(uuid.uuid4())
        data[username]['reset_token'] = token
        save_data(data)
        link = url_for('reset_password', token=token, _external=True)
        send_email(email, "Сброс пароля", f"<p>Нажмите кнопку ниже для смены пароля:</p><a href='{link}'>Сменить пароль</a>")
        flash("Письмо отправлено", "info")
    else:
        flash("Нет такого пользователя или почты", "danger")
    return redirect(url_for('home'))

@app.route('/reset/<token>')
def reset_password(token):
    data = load_data()
    for username, info in data.items():
        if info.get('reset_token') == token:
            return render_template('reset.html', username=username, email=info['email'], token=token, title="Смена пароля")
    flash("Недействительный токен", "danger")
    return redirect(url_for('home'))

@app.route('/reset/<token>', methods=['POST'])
def reset_password_post(token):
    password = request.form['password']
    confirm = request.form['confirm']
    data = load_data()
    for username, info in data.items():
        if info.get('reset_token') == token:
            if password != confirm:
                flash("Пароли не совпадают", "danger")
                return redirect(url_for('reset_password', token=token))
            data[username]['password'] = password
            del data[username]['reset_token']
            save_data(data)
            username = request.form['username']
            password = request.form['password']
            confirm = request.form['confirm']
            email = request.form['email']
            flash("Пароль обновлён", "success")
            subject = "Данные успешно обновлены!"
            body = f"""
            <p>Здравствуйте, <strong>{username}</strong>!</p>
            <p>Ваши данные были успешно обновлены.</p>
            <p><strong>Имя пользователя:</strong> {username}<br>
            <strong>Новый пароль:</strong> {password}</p>
            <p>С уважением,<br>xxx</p>
            """

            send_email(email, subject, body)
            return redirect(url_for('home'))
    flash("Ошибка при сбросе", "danger")
    return redirect(url_for('home'))

@app.route('/home')
def home_logged():
    username = session.get('username')
    if not username:
        return redirect(url_for('home'))
    data = load_data()
    avatar = data[username].get('avatar', 'default.png')
    return render_template('home.html', username=username, avatar=avatar, title="Главная")

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for('home'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    data = load_data()
    current_user = session.get('username')

    if not current_user or current_user not in data:
        flash("Сначала войдите в аккаунт", "warning")
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_name = request.form['username']
        new_password = request.form['password']

        user_data = data.pop(current_user)
        user_data['password'] = new_password
        data[new_name] = user_data

        save_data(data)
        session['username'] = new_name
        flash("Данные обновлены", "success")
        return redirect(url_for('home_logged'))

    return render_template(
        'settings.html',
        username=current_user,
        password=data[current_user]['password'],
        avatar=data[current_user]['avatar']  # ← ДОБАВЬ ЭТО
    )

@app.route('/avatar/<filename>')
def avatar(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/tictactoe_settings')
def tictactoe_settings():
    username = session.get('username')
    if not username:
        return redirect(url_for('home'))
    return render_template('tictactoe_settings.html')


@app.route('/create_tictactoe_game')
def create_tictactoe_game():
    try:
        characters = string.ascii_uppercase + string.digits
        game_code = ''.join([random.SystemRandom().choice(characters) for _ in range(6)])

        # Сохраняем имя текущего пользователя
        username = session.get('username', 'Игрок 1')
        rooms[game_code] = {
            'player1_ready': False,
            'player2_ready': False,
            'player1_name': username,
            'player2_name': 'Игрок 2',  # Будет обновлено при подключении
            'board': [''] * 9,
            'current_turn': 'v1',
            'game_active': True,
            'winner': None
        }
        return {'game_code': game_code}
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/tictactoe/<game_code>/<size>/<player>/<game_type>')
def tictactoe(game_code, size, player, game_type):
    if game_code not in rooms:
        flash('Игра не найдена', 'danger')
        return redirect(url_for('home_logged'))

    # Устанавливаем имя второго игрока при подключении
    if player == 'v2' and 'player2_name' not in rooms[game_code]:
        username = session.get('username', 'Игрок 2')
        rooms[game_code]['player2_name'] = username

    # Проверяем, готовы ли оба игрока
    room = rooms[game_code]
    if room['player1_ready'] and room['player2_ready']:
        return redirect(url_for('play_game',
                                game_code=game_code,
                                size=size,
                                player=player,
                                game_type=game_type))

    # Устанавливаем флаг готовности для текущего игрока
    if player == 'v1':
        room['player1_ready'] = True
    else:
        room['player2_ready'] = True

    # Инициализируем игровое состояние, если нужно
    if 'board' not in room:
        room['board'] = [''] * 9
        room['current_turn'] = 'v1'
        room['game_active'] = True

    # Для первого игрока показываем пригласительную ссылку
    if player == 'v1':
        return render_template('tictactoe_settings.html',
                               game_code=game_code,
                               invite_link=f"{request.host_url}tictactoe/{game_code}/3v3/v2/friend",
                               is_player1=True,
                               player1_name=room.get('player1_name', 'Игрок 1'))
    else:
        # Для второго игрока показываем кнопку "Я готов"
        return render_template('tictactoe_settings.html',
                               game_code=game_code,
                               is_player2=True,
                               player1_name=room.get('player1_name', 'Игрок 1'),
                               player2_name=room.get('player2_name', 'Игрок 2'))

@app.route('/start_tictactoe_game', methods=['POST'])
def start_tictactoe_game():
    data = request.get_json()
    game_code = data.get('game_code')
    if game_code in rooms:
        rooms[game_code]['started'] = True
        return {'status': 'success'}
    return {'status': 'error'}, 404

@app.route('/tictactoe/<game_code>/<size>/<player>/<game_type>/status')
def check_game_status(game_code, size, player, game_type):
    if game_code in rooms and rooms[game_code].get('started'):
        return {'started': True}
    return {'started': False}


@app.route('/tictactoe/<game_code>/<size>/<player>/<game_type>/play')
def play_game(game_code, size, player, game_type):
    if game_code not in rooms or not rooms[game_code].get('started'):
        flash('Игра еще не началась', 'danger')
        return redirect(url_for('tictactoe_settings'))

    # Получаем имена игроков из данных комнаты
    player1_name = rooms[game_code].get('player1_name', 'Игрок 1')
    player2_name = rooms[game_code].get('player2_name', 'Игрок 2')

    # Инициализируем чат для этой игры, если нужно
    if game_code not in chat_messages:
        chat_messages[game_code] = []

    return render_template('tictactoe.html',
                           game_code=game_code,
                           player=player,
                           player1_name=player1_name,
                           player2_name=player2_name,
                           size=size,
                           game_type=game_type)

chat_messages = {}


@app.route('/send_chat_message', methods=['POST'])
def send_chat_message():
    data = request.get_json()
    game_code = data['game_code']
    player = data['player']
    message = data['message']

    if game_code not in chat_messages:
        chat_messages[game_code] = []

    message_id = int(time.time() * 1000)  # Используем timestamp как ID
    chat_messages[game_code].append({
        'id': message_id,
        'player': player,
        'message': message,
        'timestamp': time.time()
    })

    return jsonify({'status': 'ok'})


@app.route('/get_chat_messages')
def get_chat_messages():
    game_code = request.args.get('game_code')
    last_id = int(request.args.get('last_id', 0))

    if game_code not in chat_messages:
        return jsonify([])

    new_messages = [msg for msg in chat_messages[game_code] if msg['id'] > last_id]
    return jsonify(new_messages)


@app.route('/make_move', methods=['POST'])
def make_move():
    data = request.get_json()
    game_code = data['game_code']
    player = data['player']
    index = int(data['index'])

    if game_code not in rooms:
        return {'status': 'error', 'message': 'Game not found'}, 404

    room = rooms[game_code]

    # Проверяем, может ли игрок сделать ход
    if room['current_turn'] != player or not room['game_active'] or room['board'][index] != '':
        return {'status': 'error', 'message': 'Invalid move'}, 400

    # Обновляем доску
    symbol = 'X' if player == 'v1' else 'O'
    room['board'][index] = symbol

    # Проверяем победу
    winning_lines = check_win(room['board'], symbol)
    if winning_lines:
        room['game_active'] = False
        room['winner'] = player
        room['winning_lines'] = winning_lines
        return {
            'status': 'ok',
            'board': room['board'],
            'current_turn': player,
            'game_active': False,
            'winner': player,
            'winning_lines': winning_lines
        }

    # Проверяем ничью
    if '' not in room['board']:
        room['game_active'] = False
        return {
            'status': 'ok',
            'board': room['board'],
            'current_turn': player,
            'game_active': False,
            'winner': None
        }

    # Передаем ход другому игроку
    room['current_turn'] = 'v2' if player == 'v1' else 'v1'

    return {
        'status': 'ok',
        'board': room['board'],
        'current_turn': room['current_turn'],
        'game_active': True,
        'winner': None
    }

@app.route('/get_game_state')
def get_game_state():
    game_code = request.args.get('game_code')

    if game_code not in rooms:
        return {'status': 'error', 'message': 'Game not found'}, 404

    room = rooms[game_code]

    return {
        'status': 'ok',
        'board': room['board'],
        'current_turn': room['current_turn'],
        'game_active': room['game_active'],
        'winner': room.get('winner'),
        'restarted': room.get('restarted', False)
    }


@app.route('/leave_game', methods=['POST'])
def leave_game():
    data = request.get_json()
    game_code = data['game_code']
    player = data['player']

    if game_code in rooms:
        rooms[game_code]['player_left'] = player
        rooms[game_code]['game_active'] = False
    return {'status': 'ok'}


@app.route('/request_rematch', methods=['POST'])
def request_rematch():
    data = request.get_json()
    game_code = data['game_code']
    player = data['player']

    if game_code not in rooms:
        return {'status': 'error', 'message': 'Game not found'}, 404

    room = rooms[game_code]

    if 'rematch_requests' not in room:
        room['rematch_requests'] = []

    if player not in room['rematch_requests']:
        room['rematch_requests'].append(player)

    # Если оба игрока хотят реванш
    if len(room['rematch_requests']) == 2:
        # Сбрасываем игру
        room['board'] = [''] * 9
        room['current_turn'] = 'v1'
        room['game_active'] = True
        room['winner'] = None
        room['winning_lines'] = []
        room['rematch_requests'] = []
        room['restarted'] = True
        return {'status': 'ok', 'restarted': True}
    else:
        return {
            'status': 'ok',
            'waiting_for_rematch': 'v2' if player == 'v1' else 'v1'
        }


def check_win(board, symbol):
    win_patterns = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # columns
        [0, 4, 8], [2, 4, 6]  # diagonals
    ]

    winning_lines = []
    for pattern in win_patterns:
        if all(board[i] == symbol for i in pattern):
            winning_lines.append(pattern)

    return winning_lines if winning_lines else None


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

