import os
from datetime import datetime
from functools import wraps  # NOVO: Importado para criar o decorator

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import google.generativeai as genai  

# Configurações do banco de dados
POSTGRES_USER = os.getenv("POSTGRES_USER", "mercadinho")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "123")
POSTGRES_DB = os.getenv("POSTGRES_DB", "gestao")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "192.168.1.124")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

db = SQLAlchemy()
jwt = JWTManager()
hasher = PasswordHasher()
mail = Mail()
s = None

# NOVO: Decorator para verificar se o usuário está logado
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Acesso negado. Por favor, faça login.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def create_app():
    global s
    app = Flask(__name__)
    app.secret_key = 'supersecretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    CORS(app)
    db.init_app(app)
    jwt.init_app(app)

    # Flask-Mail
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'seuemail@gmail.com'  # Trocar pelo seu e-mail
    app.config['MAIL_PASSWORD'] = 'senha_de_aplicativo' # Trocar pela sua senha de app
    mail.init_app(app)

    # Serializer para tokens
    s = URLSafeTimedSerializer(app.secret_key)
    
    # Modelos do banco de dados (sem alterações)
    class Usuario(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        nome = db.Column(db.String(100), nullable=False)
        email = db.Column(db.String(100), unique=True, nullable=False)
        senha_hash = db.Column(db.String(200), nullable=False)

    class Categoria(db.Model):
        __tablename__ = 'categoria'
        id = db.Column(db.Integer, primary_key=True)
        nome = db.Column(db.String(100), nullable=False)
        produtos = db.relationship('Produto', backref='categoria_ref', lazy=True)

    class Cliente(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        nome = db.Column(db.String(100), nullable=False)
        email = db.Column(db.String(100))
        telefone = db.Column(db.String(20))
        cpf = db.Column(db.String(20))
        endereco = db.Column(db.String(255))
        cidade = db.Column(db.String(100))
        status = db.Column(db.String(20))

    class Fornecedor(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        razao_social = db.Column(db.String(255), nullable=False)
        cnpj = db.Column(db.String(20))
        email = db.Column(db.String(255))
        telefone = db.Column(db.String(20))
        endereco = db.Column(db.String(255))
        status = db.Column(db.String(20))

    class Funcionario(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        nome = db.Column(db.String(255), nullable=False)
        cpf = db.Column(db.String(20))
        cargo = db.Column(db.String(100))
        email = db.Column(db.String(255))
        telefone = db.Column(db.String(20))
        salario = db.Column(db.Numeric(12,2))
        status = db.Column(db.String(20))

    class Produto(db.Model):
        __tablename__ = 'produtos'
        id = db.Column(db.Integer, primary_key=True)
        nome = db.Column(db.String(100), nullable=False)
        codigo = db.Column(db.String(100))
        categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
        preco = db.Column(db.Float, nullable=False)
        custo = db.Column(db.Float, nullable=True)
        estoque = db.Column(db.Integer, default=0)
        validade = db.Column(db.Date, nullable=True)
        descricao = db.Column(db.Text, nullable=True)
        status = db.Column(db.String(20))

    class Venda(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
        quantidade = db.Column(db.Integer, nullable=False)
        data_venda = db.Column(db.DateTime, default=datetime.utcnow)
        produto = db.relationship('Produto')

    with app.app_context():
        db.create_all()

    # --- ROTAS PRINCIPAIS ---
    @app.route("/")
    def home():
        return redirect(url_for("dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"]
            senha = request.form["senha"]
            user = Usuario.query.filter_by(email=email).first()
            if user:
                try:
                    hasher.verify(user.senha_hash, senha)
                    session['user'] = user.nome
                    flash(f'Bem-vindo, {user.nome}!', 'success')
                    return redirect(url_for("dashboard")) # ALTERADO: Redireciona para o dashboard principal
                except VerifyMismatchError:
                    flash('Senha incorreta.', 'danger')
                    return render_template("login.html")
            flash('Usuário não encontrado.', 'danger')
            return render_template("login.html")
        return render_template("login.html")
    
    @app.route("/logout")
    def logout():
        session.pop('user', None)
        flash('Você saiu do sistema.', 'info')
        return redirect(url_for('login'))

    # --- ROTAS DE PÁGINAS PROTEGIDAS ---
    @app.route("/estoque")
    @login_required # DECORATOR ADICIONADO
    def estoque():
        return render_template("estoque.html", nome=session.get("user", "Usuário"))

    @app.route("/vendas")
    @login_required # DECORATOR ADICIONADO
    def vendas():
        return render_template("vendas.html")
    
    @app.route("/financeiro")
    @login_required # DECORATOR ADICIONADO
    def financeiro():
        return render_template("financeiro.html")

    @app.route("/administracao")
    @login_required # DECORATOR ADICIONADO
    def administracao():
        return render_template("administracao.html")
    
    @app.route("/dashboard")
    @login_required # DECORATOR ADICIONADO
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/assistente")
    @login_required
    def assistente():
        return render_template("assistente.html")

    # NOVA ROTA: Relatórios de Análise Financeira
    @app.route("/relatorios")
    @login_required # DECORATOR ADICIONADO
    def relatorios():
        # Estes dados viriam do seu banco de dados após cálculos complexos
        # Aqui, estamos simulando para conectar com o frontend
        dados_financeiros = {
            'receita_liquida': 'R$ 15.2M',
            'margem_liquida': '18.7%',
            'roe': '24.3%',
            'liquidez_corrente': '2.8x',
            'crescimento_receita': '↗ +12.5% vs ano anterior',
            'crescimento_margem': '↗ +2.1 p.p.',
            'crescimento_roe': '↗ +3.8 p.p.',
            'status_liquidez': '↗ Melhoria'
        }
        return render_template("relatorio.html", dados=dados_financeiros)

    @app.route("/cadastros")
    @login_required # DECORATOR ADICIONADO
    def cadastros():
        return render_template("cadastros.html")

    @app.route("/about")
    @login_required # DECORATOR ADICIONADO
    def about():
        return render_template("about.html")
    
    @app.route('/controledevalidade')
    @login_required # DECORATOR ADICIONADO
    def controledevalidade():
        return render_template('controledevalidade.html')

    # --- ROTAS DA API (sem alterações de funcionalidade) ---
    @app.route('/api/produtos', methods=['GET', 'POST'])
    def api_produtos():
        # ... (código da API de produtos permanece o mesmo)
        if request.method == 'POST':
            data = request.json
            validade = data.get('validade')
            if validade:
                validade = datetime.strptime(validade, "%Y-%m-%d").date()
            else:
                validade = None

            novo_produto = Produto(
                nome=data['nome'], codigo=data.get('codigo'),
                categoria_id=data.get('categoria_id'), preco=data.get('preco'),
                custo=data.get('custo'), estoque=data.get('estoque'),
                validade=validade, descricao=data.get('descricao'), status=data.get('status')
            )
            db.session.add(novo_produto)
            db.session.commit()
            return jsonify({'success': True, 'id': novo_produto.id}), 201
        else: # GET
            produtos_lista = Produto.query.all()
            return jsonify([{
                'id': p.id, 'nome': p.nome, 'codigo': p.codigo,
                'categoria_id': p.categoria_id,
                'categoria_nome': p.categoria_ref.nome if p.categoria_ref else 'Sem Categoria',
                'preco': float(p.preco) if p.preco is not None else 0.0,
                'custo': float(p.custo) if p.custo is not None else 0.0,
                'estoque': p.estoque,
                'validade': p.validade.isoformat() if p.validade else None,
                'descricao': p.descricao, 'status': p.status
            } for p in produtos_lista])

    @app.route('/api/produtos/<int:id>', methods=['PUT', 'DELETE'])
    def api_produto_detail(id):
        # ... (código da API de detalhes do produto permanece o mesmo)
        produto = Produto.query.get_or_404(id)
        if request.method == 'DELETE':
            db.session.delete(produto)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Produto excluído com sucesso'})
        if request.method == 'PUT':
            data = request.json
            produto.nome = data.get('nome', produto.nome)
            # ... (resto da lógica de atualização)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Produto atualizado com sucesso'})

    # --- ROTAS DE UTILIDADE (sem alterações) ---
    @app.route('/seed-categorias')
    def seed_categorias():
        # ... (código para popular categorias)
        if Categoria.query.first():
            return "Categorias já existem no banco de dados."
        categorias_iniciais = [
            {'id': 1, 'nome': 'Perecíveis'}, {'id': 2, 'nome': 'Bebidas'},
            {'id': 3, 'nome': 'Verduras'}, {'id': 4, 'nome': 'Frutas'}
        ]
        for cat_data in categorias_iniciais:
            nova_categoria = Categoria(id=cat_data['id'], nome=cat_data['nome'])
            db.session.add(nova_categoria)
        try:
            db.session.commit()
            db.session.execute(db.text("SELECT setval('categoria_id_seq', (SELECT MAX(id) FROM categoria));"))
            db.session.commit()
            return "Categorias iniciais cadastradas com sucesso!"
        except Exception as e:
            db.session.rollback()
            return f"Ocorreu um erro: {e}"
            
    @app.route("/create-admin")
    def create_admin():
        # ... (código para criar admin)
        if Usuario.query.filter_by(email="admin@email.com").first():
            return "Usuário já existe"
        senha = hasher.hash("admin123")
        admin = Usuario(nome="Admin", email="admin@email.com", senha_hash=senha)
        db.session.add(admin)
        db.session.commit()
        return "Usuário admin criado com sucesso"
    
    @app.route('/esqueci_senha', methods=['GET', 'POST'])
    def esqueci_senha():
        # ... (código para esqueci a senha)
        if request.method == 'POST':
            email = request.form['email']
            user = Usuario.query.filter_by(email=email).first()
            if user:
                token = s.dumps(email, salt='redefinir-senha')
                link = url_for('resetar_senha', token=token, _external=True)
                msg = Message('Redefinição de Senha', sender=app.config['MAIL_USERNAME'], recipients=[email])
                msg.body = f'Clique no link para redefinir sua senha: {link}'
                mail.send(msg)
                flash('E-mail enviado. Verifique sua caixa de entrada.', 'success')
            else:
                flash('E-mail não encontrado.', 'danger')
            return redirect(url_for('login'))
        return render_template('esqueci_senha.html')

    @app.route('/resetar/<token>', methods=['GET', 'POST'])
    def resetar_senha(token):
        # ... (código para resetar a senha)
        try:
            email = s.loads(token, salt='redefinir-senha', max_age=3600)
        except (SignatureExpired, BadSignature):
            flash('O link de redefinição é inválido ou expirou.', 'danger')
            return redirect(url_for('login'))

        if request.method == 'POST':
            nova_senha = request.form['senha']
            hash_senha = hasher.hash(nova_senha)
            user = Usuario.query.filter_by(email=email).first()
            if user:
                user.senha_hash = hash_senha
                db.session.commit()
                flash('Senha alterada com sucesso. Faça login com sua nova senha.', 'success')
                return redirect(url_for('login'))
        return render_template('resetar.html')

    @app.route("/chat", methods=["POST"])
    def chat():
        try:
            # --- ALTERAÇÕES APLICADAS AQUI ---
            # 1. Carrega a chave da API a partir do arquivo .env
            api_key = os.getenv("GOOGLE_API_KEY")

            # 2. Verifica se a chave foi carregada com sucesso
            if not api_key:
                print("ERRO: A variável de ambiente GOOGLE_API_KEY não foi encontrada.")
                return jsonify({"error": "A chave da API do assistente não está configurada no servidor."}), 500

            # 3. Configura a biblioteca genai com a chave
            genai.configure(api_key=api_key)
            # --- FIM DAS ALTERAÇÕES ---

            data = request.get_json()
            user_message = data.get("message", "")
            if not user_message:
                return jsonify({"error": "Mensagem não fornecida"}), 400

            # NOVO: Verifica se a mensagem do usuário é uma saudação simples
            saudacoes = ['oi', 'ola', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'eai', 'tudo bem?']
            if user_message.lower().strip() in saudacoes:
                # Se for uma saudação, retorna uma resposta padrão sem chamar a IA
                return jsonify({"reply": "Olá! Eu sou seu assistente de gestão e contabilidade. Como posso te ajudar hoje?"})

            # Se não for uma saudação, usa a lógica completa da IA
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                f"Você é um assistente especialista em contabilidade e gestão empresarial no Brasil. "
                f"Utilize de linguagem clara e acessível, evitando jargões técnicos. "
                f"Foque-se nas leis e regulamentações brasileiras. "
                f"Retorne respostas detalhadas e alinhadas às necessidades do usuário. "
                f"Haja como um consultor e administrador experiente de pequenas, médias e grandes empresas."
                f"Considere realizar cálculos financeiros e contábeis como: fluxo de caixa, margem de lucro, ponto de equilíbrio, análise de custos, entre outros. "
                f"Haja o mais próximo de um ser humano possível. "
                f"Retorne a resposta em português, utilizando de paragráfos e listas, mantenha o espaçamento entre as linhas para que não fique um bloco só."
                f"Responda de forma clara, prática e acessível: {user_message}"
            )
            return jsonify({"reply": response.text})

        except Exception as e:
            print(f"Erro na rota de chat: {e}")
            return jsonify({"error": "Ocorreu um erro interno no assistente."}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)