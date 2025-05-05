import json
import os
import smtplib
import string
import uuid
import random
import string

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
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
        rooms[game_code] = {
            'player1_ready': False,
            'player2_ready': False,
            'size': '3v3',
            'type': 'friend'
        }
        return {'game_code': game_code}
    except Exception as e:
        app.logger.error(f"Error creating game: {str(e)}")
        return {'error': str(e)}, 500


@app.route('/tictactoe/<game_code>/<size>/<player>/<game_type>')
def tictactoe(game_code, size, player, game_type):
    if game_code not in rooms:
        flash('Игра не найдена', 'danger')
        return redirect(url_for('home_logged'))

    # Проверяем, готовы ли оба игрока
    room = rooms[game_code]
    if room['player1_ready'] and room['player2_ready']:
        return render_template('tictactoe.html')

    # Устанавливаем флаг готовности для текущего игрока
    if player == 'v1':
        room['player1_ready'] = True
        # Для игрока 1 показываем пригласительную ссылку
        return render_template('tictactoe_settings.html',
                               game_code=game_code,
                               invite_link=f"{request.host_url}tictactoe/{game_code}/3v3/v2/friend")
    else:
        room['player2_ready'] = True
        # Для игрока 2 показываем кнопку "Начать игру"
        return render_template('tictactoe_settings.html',
                               game_code=game_code,
                               is_player2=True)

@app.route('/start_tictactoe_game', methods=['POST'])
def start_tictactoe_game():
    data = request.get_json()
    game_code = data.get('game_code')
    if game_code in rooms:
        rooms[game_code]['player2_ready'] = True
    return {'status': 'success'}



if __name__ == '__main__':
    app.run(debug=True)
