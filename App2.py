import json
import os
import smtplib
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from shutil import copyfile
from PIL import Image

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATA_FILE = 'data.json'
UPLOAD_FOLDER = 'avatar'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    if 'username' in session:
        return render_template('base.html', username=session['username'], avatar=session.get('avatar'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    data = load_data()
    if username in data and data[username]['password'] == password:
        session['username'] = username
        session['user_id'] = data[username]['id']
        session['avatar'] = data[username].get('avatar', 'default.png')
        flash("Успешный вход!", "success")
        return redirect(url_for('home'))
    flash("Неверные данные", "danger")
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm']
        email = request.form['email']

        data = load_data()

        if username in data:
            flash("Имя занято", "danger")
            return redirect(url_for('register'))
        if password != confirm:
            flash("Пароли не совпадают", "danger")
            return redirect(url_for('register'))

        user_id = str(len(data))
        avatar_filename = f"{user_id}.png"
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        default_avatar_path = os.path.join('static', 'default.png')
        Image.open(default_avatar_path).save(os.path.join(UPLOAD_FOLDER, avatar_filename))

        data[username] = {
            'password': password,
            'email': email,
            'id': user_id,
            'avatar': avatar_filename
        }
        save_data(data)
        flash("Регистрация успешна", "success")
        return redirect(url_for('home'))
    return render_template('register.html')

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
            flash("Пароль обновлён", "success")
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
    username = session.get('username')
    if not username:
        return redirect(url_for('home'))

    data = load_data()
    user_data = data.get(username)

    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']
        avatar_file = request.files.get('avatar')

        if new_username != username and new_username in data:
            flash("Имя занято", "danger")
            return redirect(url_for('settings'))

        if avatar_file:
            avatar_filename = f"{user_data['id']}.png"
            avatar_path = os.path.join(UPLOAD_FOLDER, avatar_filename)
            image = Image.open(avatar_file)
            image.save(avatar_path)
            user_data['avatar'] = avatar_filename

        if new_password:
            user_data['password'] = new_password

        if new_username != username:
            data[new_username] = data.pop(username)
            session['username'] = new_username
        else:
            data[username] = user_data

        session['avatar'] = user_data['avatar']
        save_data(data)
        flash("Настройки обновлены", "success")
        return redirect(url_for('home'))

    return render_template('settings.html',
                           username=username,
                           password=user_data['password'],
                           avatar=user_data['avatar'])

@app.route('/avatar/<filename>')
def avatar(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
