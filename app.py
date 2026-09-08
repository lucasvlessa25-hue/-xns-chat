from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import threading

app = Flask(__name__)

app.secret_key = "xns-chat-chave"

socketio = SocketIO(app, cors_allowed_origins="*")


# ==========================================
# BANCO DE DADOS
# ==========================================

def conectar_banco():
    banco = sqlite3.connect("chat.db")
    banco.row_factory = sqlite3.Row
    return banco


def criar_banco():
    banco = conectar_banco()

    banco.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    banco.execute("""
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            grupo_id INTEGER,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    banco.execute("""
        CREATE TABLE IF NOT EXISTS grupos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            criador_id INTEGER NOT NULL
        )
    """)

    banco.commit()
    banco.close()


criar_banco()


# ==========================================
# MOSTRAR USUÁRIOS
# ==========================================

def mostrar_usuarios():

    banco = conectar_banco()

    usuarios = banco.execute(
        """
        SELECT id, username, senha
        FROM usuarios
        ORDER BY id
        """
    ).fetchall()

    banco.close()

    print()
    print("======================================")
    print("             USUÁRIOS")
    print("======================================")

    if not usuarios:

        print("Nenhum usuário cadastrado.")

    else:

        for usuario in usuarios:

            print(f"ID:      {usuario['id']}")
            print(f"Usuário: {usuario['username']}")
            print(f"Hash:    {usuario['senha']}")
            print("--------------------------------------")

    print()


# ==========================================
# TERMINAL
# ==========================================

def terminal_comandos():

    print()
    print("======================================")
    print("             XNS CHAT")
    print("======================================")
    print()
    print("Site: http://127.0.0.1:5000")
    print()
    print("Comandos:")
    print("  usuarios  - mostrar usuários")
    print("  grupos    - mostrar grupos")
    print("  sair      - encerrar servidor")
    print()

    while True:

        try:

            comando = input("XNS > ").strip().lower()

        except (EOFError, KeyboardInterrupt):

            print()
            print("Encerrando servidor...")

            break

        if comando == "usuarios":

            mostrar_usuarios()

        elif comando == "grupos":

            mostrar_grupos()

        elif comando == "sair":

            print("Encerrando servidor...")

            # Finaliza o processo do Python
            raise SystemExit

        elif comando == "":

            continue

        else:

            print("Comando desconhecido.")
            print("Use: usuarios, grupos ou sair.")


# ==========================================
# MOSTRAR GRUPOS
# ==========================================

def mostrar_grupos():

    banco = conectar_banco()

    grupos = banco.execute(
        """
        SELECT id, nome, criador_id
        FROM grupos
        ORDER BY id
        """
    ).fetchall()

    banco.close()

    print()
    print("======================================")
    print("              GRUPOS")
    print("======================================")

    if not grupos:

        print("Nenhum grupo criado.")

    else:

        for grupo in grupos:

            print(f"ID:       {grupo['id']}")
            print(f"Nome:     {grupo['nome']}")
            print(f"Criador:  {grupo['criador_id']}")
            print("--------------------------------------")

    print()


# ==========================================
# PÁGINA INICIAL
# ==========================================

@app.route("/")
def inicio():

    if "usuario_id" in session:

        return redirect(url_for("chat"))

    return redirect(url_for("login"))


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    erro = None

    if request.method == "POST":

        username = request.form["username"].strip()
        senha = request.form["senha"]

        banco = conectar_banco()

        usuario = banco.execute(
            """
            SELECT *
            FROM usuarios
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        banco.close()

        if usuario and check_password_hash(
            usuario["senha"],
            senha
        ):

            session["usuario_id"] = usuario["id"]
            session["usuario"] = usuario["username"]

            return redirect(url_for("chat"))

        erro = "Usuário ou senha incorretos."

    return render_template(
        "login.html",
        erro=erro
    )


# ==========================================
# CADASTRO
# ==========================================

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    erro = None

    if request.method == "POST":

        username = request.form["username"].strip()
        senha = request.form["senha"]

        if len(username) < 3:

            erro = "O usuário precisa ter pelo menos 3 caracteres."

            return render_template(
                "cadastro.html",
                erro=erro
            )

        if len(senha) < 4:

            erro = "A senha precisa ter pelo menos 4 caracteres."

            return render_template(
                "cadastro.html",
                erro=erro
            )

        senha_hash = generate_password_hash(senha)

        banco = conectar_banco()

        try:

            banco.execute(
                """
                INSERT INTO usuarios
                (username, senha)
                VALUES (?, ?)
                """,
                (
                    username,
                    senha_hash
                )
            )

            banco.commit()
            banco.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            banco.close()

            erro = "Esse usuário já existe."

    return render_template(
        "cadastro.html",
        erro=erro
    )


# ==========================================
# CHAT GLOBAL
# ==========================================

@app.route("/chat")
def chat():

    if "usuario_id" not in session:

        return redirect(url_for("login"))

    banco = conectar_banco()

    mensagens = banco.execute(
        """
        SELECT usuario, mensagem, data
        FROM mensagens
        WHERE grupo_id IS NULL
        ORDER BY id ASC
        LIMIT 100
        """
    ).fetchall()

    grupos = banco.execute(
        """
        SELECT id, nome
        FROM grupos
        ORDER BY nome ASC
        """
    ).fetchall()

    banco.close()

    return render_template(
        "chat.html",
        usuario=session["usuario"],
        mensagens=mensagens,
        grupos=grupos,
        grupo=None
    )


# ==========================================
# CRIAR GRUPO
# ==========================================

@app.route("/criar_grupo", methods=["POST"])
def criar_grupo():

    if "usuario_id" not in session:

        return redirect(url_for("login"))

    nome = request.form["nome"].strip()
    senha = request.form["senha"]

    if len(nome) < 2 or len(nome) > 50:

        return redirect(url_for("chat"))

    if len(senha) < 4:

        return redirect(url_for("chat"))

    senha_hash = generate_password_hash(senha)

    banco = conectar_banco()

    try:

        banco.execute(
            """
            INSERT INTO grupos
            (nome, senha, criador_id)
            VALUES (?, ?, ?)
            """,
            (
                nome,
                senha_hash,
                session["usuario_id"]
            )
        )

        banco.commit()

    except sqlite3.IntegrityError:

        pass

    banco.close()

    return redirect(url_for("chat"))


# ==========================================
# ENTRAR NO GRUPO
# ==========================================

@app.route(
    "/grupo/<int:grupo_id>/entrar",
    methods=["GET", "POST"]
)
def entrar_grupo(grupo_id):

    if "usuario_id" not in session:

        return redirect(url_for("login"))

    banco = conectar_banco()

    grupo = banco.execute(
        """
        SELECT id, nome, senha
        FROM grupos
        WHERE id = ?
        """,
        (grupo_id,)
    ).fetchone()

    banco.close()

    if grupo is None:

        return redirect(url_for("chat"))

    erro = None

    if request.method == "POST":

        senha = request.form["senha"]

        if check_password_hash(
            grupo["senha"],
            senha
        ):

            session[f"grupo_{grupo_id}"] = True

            return redirect(
                url_for(
                    "abrir_grupo",
                    grupo_id=grupo_id
                )
            )

        erro = "Senha do grupo incorreta."

    return render_template(
        "senha_grupo.html",
        grupo=grupo,
        erro=erro
    )


# ==========================================
# ABRIR GRUPO
# ==========================================

@app.route("/grupo/<int:grupo_id>")
def abrir_grupo(grupo_id):

    if "usuario_id" not in session:

        return redirect(url_for("login"))

    if not session.get(
        f"grupo_{grupo_id}",
        False
    ):

        return redirect(
            url_for(
                "entrar_grupo",
                grupo_id=grupo_id
            )
        )

    banco = conectar_banco()

    grupo = banco.execute(
        """
        SELECT id, nome
        FROM grupos
        WHERE id = ?
        """,
        (grupo_id,)
    ).fetchone()

    if grupo is None:

        banco.close()

        return redirect(url_for("chat"))

    mensagens = banco.execute(
        """
        SELECT usuario, mensagem, data
        FROM mensagens
        WHERE grupo_id = ?
        ORDER BY id ASC
        LIMIT 100
        """,
        (grupo_id,)
    ).fetchall()

    grupos = banco.execute(
        """
        SELECT id, nome
        FROM grupos
        ORDER BY nome ASC
        """
    ).fetchall()

    banco.close()

    return render_template(
        "chat.html",
        usuario=session["usuario"],
        mensagens=mensagens,
        grupos=grupos,
        grupo=grupo
    )


# ==========================================
# SOCKET — ENTRAR NO GRUPO
# ==========================================

@socketio.on("entrar_grupo")
def socket_entrar_grupo(data):

    if "usuario" not in session:

        return

    grupo_id = data.get("grupo_id")

    if not grupo_id:

        return

    if not session.get(
        f"grupo_{grupo_id}",
        False
    ):

        return

    join_room(
        f"grupo_{grupo_id}"
    )


# ==========================================
# SOCKET — CHAT GLOBAL
# ==========================================

@socketio.on("mensagem_global")
def mensagem_global(data):

    if "usuario" not in session:

        return

    mensagem = str(
        data.get("mensagem", "")
    ).strip()

    if not mensagem:

        return

    if len(mensagem) > 500:

        return

    usuario = session["usuario"]

    banco = conectar_banco()

    banco.execute(
        """
        INSERT INTO mensagens
        (usuario, mensagem, grupo_id)
        VALUES (?, ?, NULL)
        """,
        (
            usuario,
            mensagem
        )
    )

    banco.commit()
    banco.close()

    emit(
        "nova_mensagem",
        {
            "usuario": usuario,
            "mensagem": mensagem
        },
        broadcast=True
    )


# ==========================================
# SOCKET — MENSAGEM DE GRUPO
# ==========================================

@socketio.on("mensagem_grupo")
def mensagem_grupo(data):

    if "usuario" not in session:

        return

    grupo_id = data.get("grupo_id")

    mensagem = str(
        data.get("mensagem", "")
    ).strip()

    if not grupo_id:

        return

    if not mensagem:

        return

    if len(mensagem) > 500:

        return

    if not session.get(
        f"grupo_{grupo_id}",
        False
    ):

        return

    banco = conectar_banco()

    grupo = banco.execute(
        """
        SELECT id
        FROM grupos
        WHERE id = ?
        """,
        (grupo_id,)
    ).fetchone()

    if grupo is None:

        banco.close()

        return

    usuario = session["usuario"]

    banco.execute(
        """
        INSERT INTO mensagens
        (usuario, mensagem, grupo_id)
        VALUES (?, ?, ?)
        """,
        (
            usuario,
            mensagem,
            grupo_id
        )
    )

    banco.commit()
    banco.close()

    emit(
        "nova_mensagem_grupo",
        {
            "usuario": usuario,
            "mensagem": mensagem,
            "grupo_id": int(grupo_id)
        },
        room=f"grupo_{grupo_id}"
    )


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ==========================================
# INICIAR SERVIDOR
# ==========================================

if __name__ == "__main__":

    # Inicia o terminal de comandos
    thread = threading.Thread(
        target=terminal_comandos,
        daemon=True
    )

    thread.start()

    # Evita que o modo debug crie outro processo
    # e duplique o terminal de comandos.
    socketio.run(
        app,
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )

