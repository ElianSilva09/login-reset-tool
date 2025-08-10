# app.py
import os
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime, timedelta
from functools import wraps

# --- Configurações ---
APP_SECRET = os.environ.get("APP_SECRET", "troque_isto_para_uma_senha_forte")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "troque_isto_para_admin")  # use env var em produção
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///usuarios_server.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = APP_SECRET
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Modelo de usuário ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    bloqueado = db.Column(db.Boolean, default=False)
    data_expiracao = db.Column(db.Date, nullable=True)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)

# --- Inicializa DB se necessário ---
with app.app_context():
    db.create_all()

# --- Helpers ---
def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if session.get("admin_logged"):
            return f(*args, **kwargs)
        return redirect(url_for("admin_login"))
    return wrapped

# --- API para clientes (JSON) ---
@app.route("/api/cadastrar", methods=["POST"])
def api_cadastrar():
    data = request.get_json() or {}
    usuario = data.get("usuario")
    senha = data.get("senha")
    # tempo padrão de 180 dias (6 meses)
    dias = int(data.get("dias", 180))
    if not usuario or not senha:
        return jsonify({"ok": False, "message": "usuario e senha obrigatórios"}), 400
    if Usuario.query.filter_by(usuario=usuario).first():
        return jsonify({"ok": False, "message": "Usuário já existe"}), 400
    senha_hash = generate_password_hash(senha)
    expiracao = date.today() + timedelta(days=dias)
    novo = Usuario(usuario=usuario, senha_hash=senha_hash, data_expiracao=expiracao)
    db.session.add(novo)
    db.session.commit()
    return jsonify({"ok": True, "message": "Usuário cadastrado", "expiracao": expiracao.isoformat()}), 200

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    usuario = data.get("usuario")
    senha = data.get("senha")
    if not usuario or not senha:
        return jsonify({"ok": False, "message": "usuario e senha obrigatórios"}), 400
    user = Usuario.query.filter_by(usuario=usuario).first()
    if not user:
        return jsonify({"ok": False, "message": "Usuário não encontrado"}), 404
    if not user.check_password(senha):
        return jsonify({"ok": False, "message": "Senha incorreta"}), 401
    if user.bloqueado:
        return jsonify({"ok": False, "message": "Usuário bloqueado", "bloqueado": True}), 403
    if user.data_expiracao and date.today() > user.data_expiracao:
        return jsonify({"ok": False, "message": "Assinatura expirada", "expirada": True, "contato": "seuemail@seudominio.com"}), 403
    # login ok
    return jsonify({"ok": True, "message": "Login OK", "bloqueado": False, "expiracao": user.data_expiracao.isoformat() if user.data_expiracao else None}), 200

# --- API administrativas (para chamadas internas ou scripts) ---
@app.route("/api/admin/listar", methods=["GET"])
def api_listar():
    users = Usuario.query.all()
    out = []
    for u in users:
        out.append({
            "usuario": u.usuario,
            "bloqueado": bool(u.bloqueado),
            "expiracao": u.data_expiracao.isoformat() if u.data_expiracao else None
        })
    return jsonify({"ok": True, "usuarios": out}), 200

# Botões administrativos também via painel web abaixo

# --- Painel Web do Admin ---
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    # senha de admin simples via env var - substitua por SSO ou usuário DB se quiser
    if request.method == "POST":
        senha = request.form.get("senha", "")
        if senha == ADMIN_PASSWORD:
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template_string(ADMIN_LOGIN_TPL, error="Senha incorreta")
    return render_template_string(ADMIN_LOGIN_TPL)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    users = Usuario.query.order_by(Usuario.usuario).all()
    return render_template_string(ADMIN_DASH_TPL, users=users)

@app.route("/admin/create_user", methods=["POST"])
@admin_required
def admin_create_user():
    usuario = request.form.get("usuario")
    senha = request.form.get("senha")
    dias = int(request.form.get("dias", 180))
    if not usuario or not senha:
        return redirect(url_for("admin_dashboard"))
    if Usuario.query.filter_by(usuario=usuario).first():
        return redirect(url_for("admin_dashboard"))
    novo = Usuario(usuario=usuario, senha_hash=generate_password_hash(senha), data_expiracao=date.today() + timedelta(days=dias))
    db.session.add(novo)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/block/<string:usuario>")
@admin_required
def admin_block(usuario):
    u = Usuario.query.filter_by(usuario=usuario).first()
    if u:
        u.bloqueado = True
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/unblock/<string:usuario>")
@admin_required
def admin_unblock(usuario):
    u = Usuario.query.filter_by(usuario=usuario).first()
    if u:
        u.bloqueado = False
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<string:usuario>")
@admin_required
def admin_delete(usuario):
    u = Usuario.query.filter_by(usuario=usuario).first()
    if u:
        db.session.delete(u)
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/set_time/<string:usuario>", methods=["POST"])
@admin_required
def admin_set_time(usuario):
    dias = int(request.form.get("dias", 0))
    u = Usuario.query.filter_by(usuario=usuario).first()
    if u:
        u.data_expiracao = date.today() + timedelta(days=dias)
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

# --- Templates (simples) ---
ADMIN_LOGIN_TPL = """
<!doctype html>
<title>Admin Login</title>
<h2>Painel Admin</h2>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post">
  <label>Senha Admin:</label><br>
  <input type="password" name="senha" required>
  <button type="submit">Entrar</button>
</form>
"""

ADMIN_DASH_TPL = """
<!doctype html>
<title>Admin Dashboard</title>
<h2>Painel de Administração</h2>
<p><a href="{{ url_for('admin_logout') }}">Logout</a></p>

<h3>Cadastrar usuário</h3>
<form method="post" action="{{ url_for('admin_create_user') }}">
  Usuário: <input name="usuario" required>
  Senha: <input name="senha" required>
  Dias (acesso): <input name="dias" value="180" type="number">
  <button type="submit">Criar</button>
</form>

<h3>Lista de usuários</h3>
<table border="1" cellpadding="6">
  <tr><th>Usuário</th><th>Status</th><th>Expira</th><th>Ações</th></tr>
  {% for u in users %}
  <tr>
    <td>{{ u.usuario }}</td>
    <td>{{ 'Bloqueado' if u.bloqueado else 'Ativo' }}</td>
    <td>{{ u.data_expiracao or '-' }}</td>
    <td>
      {% if not u.bloqueado %}
        <a href="{{ url_for('admin_block', usuario=u.usuario) }}">Bloquear</a>
      {% else %}
        <a href="{{ url_for('admin_unblock', usuario=u.usuario) }}">Desbloquear</a>
      {% endif %}
      | <a href="{{ url_for('admin_delete', usuario=u.usuario) }}" onclick="return confirm('Deletar?')">Deletar</a>
      | <form style="display:inline" method="post" action="{{ url_for('admin_set_time', usuario=u.usuario) }}">
          <input name="dias" type="number" placeholder="dias" required>
          <button type="submit">Definir tempo</button>
        </form>
    </td>
  </tr>
  {% endfor %}
</table>
"""

# --- Página simples para checks ---
@app.route("/")
def index():
    return "API de autenticação rodando."

# --- Rodar ---
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)