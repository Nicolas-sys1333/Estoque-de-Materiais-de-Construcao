# app.py (antigo main.py)
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, Response
import pdfkit
from database import criar_tabelas
import auth
import estoque
import relatorios
import gerenciamento
import pedidos
import excel_handler
import os

app = Flask(__name__)
app.secret_key = os.urandom(24) # Chave secreta para gerenciar sessões de usuário

@app.context_processor
def inject_permissions():
    """Disponibiliza o dicionário de permissões para todos os templates."""
    return dict(PERMISSOES=auth.PERMISSOES)

@app.context_processor
def inject_auth():
    """Disponibiliza o módulo 'auth' para todos os templates."""
    return dict(auth=auth)

@app.context_processor
def inject_notifications():
    """Disponibiliza notificações (ex: pedidos pendentes) para todos os templates."""
    if 'usuario' in session and session['usuario']['role'] == 'administracao':
        pedidos_pendentes_count = len(pedidos.listar_pedidos_pendentes())
        return dict(pedidos_pendentes_count=pedidos_pendentes_count)
    return dict(pedidos_pendentes_count=0)

# --- Rotas de Autenticação ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usuario = auth.autenticar_usuario(username, password)
        if usuario:
            session['usuario'] = usuario # Armazena dados do usuário na sessão
            flash(f"Bem-vindo(a), {usuario['username']}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Usuário ou senha incorretos.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    usuario_nome = session.get('usuario', {}).get('username', 'Desconhecido')
    session.clear() # Limpa toda a sessão, incluindo flash messages pendentes
    flash(f"Usuário {usuario_nome} deslogado com sucesso.", "info")
    return redirect(url_for('login'))

# --- Rotas Principais ---

@app.route('/')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    # Apenas administradores veem o alerta de estoque baixo
    itens_baixo_estoque = []
    if session['usuario']['role'] == 'administracao':
        itens_baixo_estoque = estoque.listar_itens_estoque_baixo()
    
    return render_template(
        'dashboard.html', 
        usuario=session['usuario'], 
        itens_baixo_estoque=itens_baixo_estoque)

@app.route('/estoque')
def ver_estoque():
    usuario = session.get('usuario')
    if not usuario:
        return redirect(url_for('login'))

    # Verifica se o perfil do usuário tem permissão para ver o estoque
    if not auth.tem_permissao(usuario['role'], 'ver_estoque'):
        flash("Você não tem permissão para acessar esta página.", "danger")
        return redirect(url_for('dashboard'))

    itens_estoque = estoque.listar_itens()
    descricoes_disponiveis = gerenciamento.listar_descricoes()
    return render_template('estoque.html', usuario=usuario, itens=itens_estoque, descricoes=descricoes_disponiveis)

@app.route('/estoque/adicionar', methods=['POST'])
def adicionar_novo_item():
    usuario = session.get('usuario')
    if not usuario or not auth.tem_permissao(usuario['role'], 'cadastrar_item'):
        flash("Você não tem permissão para realizar esta ação.", "danger")
        return redirect(url_for('ver_estoque'))

    nome = request.form['nome']
    descricao_id = request.form['descricao_id']
    # Converte para float, tratando vírgula como separador decimal
    preco_unitario = float(request.form['preco_unitario'].replace('.', '').replace(',', '.'))
    quantidade = int(request.form['quantidade'])

    sucesso, msg = estoque.criar_novo_item(nome, descricao_id, preco_unitario, quantidade, usuario['id'])
    
    flash(msg, "success" if sucesso else "danger")
    return redirect(url_for('ver_estoque'))

@app.route('/estoque/pedir_compra', methods=['POST'])
def pedir_compra_item():
    usuario = session.get('usuario')
    if not usuario:
        return redirect(url_for('login'))

    item_id = int(request.form['item_id'])
    quantidade = int(request.form['quantidade'])
    justificativa = request.form['justificativa']

    sucesso, msg = pedidos.criar_pedido_compra(item_id, quantidade, justificativa, usuario['id'])
    
    if sucesso:
        flash("Pedido de compra enviado com sucesso! Aguardando aprovação do administrador.", "success")
    else:
        flash(msg, "danger") # Mostra a mensagem de erro específica, se houver falha.
    return redirect(url_for('ver_estoque'))

@app.route('/estoque/editar/<int:id>', methods=['GET', 'POST'])
def editar_item(id):
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('ver_estoque'))

    if request.method == 'POST':
        nome = request.form['nome']
        descricao_id = int(request.form['descricao_id'])
        preco_unitario = float(request.form['preco_unitario'].replace('.', '').replace(',', '.'))
        
        sucesso, msg = estoque.atualizar_item(id, nome, descricao_id, preco_unitario, usuario['id'])
        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('ver_estoque'))

    item_para_editar = estoque.get_item(id)
    if not item_para_editar:
        flash("Item não encontrado.", "warning")
        return redirect(url_for('ver_estoque'))
    
    descricoes_disponiveis = gerenciamento.listar_descricoes()
    return render_template('estoque_item_editar.html', usuario=usuario, item=item_para_editar, descricoes=descricoes_disponiveis)

@app.route('/movimentacao', methods=['GET', 'POST'])
def registrar_movimentacao():
    usuario = session.get('usuario')
    if not usuario:
        return redirect(url_for('login'))

    # Verifica se o usuário tem permissão para entrar ou sair
    pode_entrar = auth.tem_permissao(usuario['role'], 'registrar_entrada')
    pode_sair = auth.tem_permissao(usuario['role'], 'registrar_saida')
    if not (pode_entrar or pode_sair):
        flash("Você não tem permissão para acessar esta página.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        item_id = int(request.form['item_id'])
        quantidade = int(request.form['quantidade'])
        tipo = request.form['tipo']
        observacao = request.form['observacao']

        if tipo == 'entrada' and pode_entrar:
            sucesso, msg = estoque.registrar_entrada(item_id, quantidade, usuario['id'], observacao)
        elif tipo == 'saida' and pode_sair:
            sucesso, msg = estoque.registrar_saida(item_id, quantidade, usuario['id'], observacao)
        else:
            sucesso, msg = False, "Tipo de movimentação inválida ou sem permissão."

        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('registrar_movimentacao'))

    itens_estoque = estoque.listar_itens()
    ultimas_movimentacoes = relatorios.get_ultimas_movimentacoes(limit=5)
    return render_template('movimentacao.html', usuario=usuario, itens=itens_estoque, ultimas_movimentacoes=ultimas_movimentacoes, pode_entrar=pode_entrar, pode_sair=pode_sair)

@app.route('/relatorios')
def ver_relatorios():
    usuario = session.get('usuario')
    if not usuario:
        return redirect(url_for('login'))

    if not auth.tem_permissao(usuario['role'], 'ver_relatorios'):
        flash("Você não tem permissão para acessar esta página.", "danger")
        return redirect(url_for('dashboard'))

    # Paginação para a tabela de histórico
    page = request.args.get('page', 1, type=int)
    pagination_data = relatorios.get_todas_movimentacoes(page=page, per_page=15)
    movimentacoes = pagination_data.get('movimentacoes', [])
    valor_total_estoque = relatorios.relatorio_saldo_geral()
    dados_graficos = relatorios.get_dados_graficos()
    movimentacoes_dia = {"total_entrada": 0, "total_saida": 0}
    pedidos_usuario = []
    pedidos_usuario_stats = {"pendentes": 0, "total": 0}

    if usuario['role'] == 'administracao':
        movimentacoes_dia = relatorios.get_movimentacoes_do_dia()
    else:
        # Para não-administradores, busca o histórico de seus próprios pedidos
        pedidos_usuario = pedidos.get_pedidos_por_solicitante(usuario['id'])
        pedidos_usuario_stats['total'] = len(pedidos_usuario)
        pedidos_usuario_stats['pendentes'] = len([p for p in pedidos_usuario if p['status'] == 'pendente'])


    return render_template('relatorios.html',
                           usuario=usuario, 
                           movimentacoes=movimentacoes, 
                           valor_total=valor_total_estoque, 
                           dados_graficos=dados_graficos,
                           movimentacoes_dia=movimentacoes_dia,
                           pedidos_usuario=pedidos_usuario,
                           pedidos_usuario_stats=pedidos_usuario_stats,
                           pagination_data=pagination_data)

@app.route('/relatorios/exportar_pdf')
def exportar_relatorio_pdf():
    usuario = session.get('usuario')
    if not usuario or not auth.tem_permissao(usuario['role'], 'ver_relatorios'):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    # Reutiliza a lógica de busca de dados (sem paginação para o PDF)
    movimentacoes = relatorios.get_todas_movimentacoes(page=1, per_page=999999)['movimentacoes']
    valor_total_estoque = relatorios.relatorio_saldo_geral()

    # Renderiza um template HTML específico para o PDF
    html_para_pdf = render_template(
        'relatorio_pdf.html',
        movimentacoes=movimentacoes,
        valor_total=valor_total_estoque
    )

    # Gera o PDF em memória e o retorna como um download
    try:
        # Caminho para o executável do wkhtmltopdf (padrão de instalação)
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        
        # Gera o PDF a partir do HTML
        pdf = pdfkit.from_string(html_para_pdf, False, configuration=config)
        return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": "inline;filename=relatorio_estoque.pdf"})
    except FileNotFoundError:
        flash("ERRO: O programa 'wkhtmltopdf' não foi encontrado no caminho padrão. Verifique a instalação.", "danger")
        return redirect(url_for('ver_relatorios'))

@app.route('/obras/<int:id>/exportar_pdf')
def exportar_relatorio_obra_pdf(id):
    usuario = session.get('usuario')
    if not usuario:
        return redirect(url_for('login'))

    # Busca os dados para o relatório
    obra = pedidos.get_obra(id)
    if not obra:
        flash("Obra não encontrada.", "warning")
        return redirect(url_for('listar_obras_public'))
        
    materiais_enviados = pedidos.get_materiais_por_obra(id)

    # Renderiza um template HTML específico para o PDF
    html_para_pdf = render_template('obra_relatorio_pdf.html', obra=obra, materiais=materiais_enviados)

    # Gera o PDF e o retorna como um download
    try:
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdf = pdfkit.from_string(html_para_pdf, False, configuration=config)
        filename = f"relatorio_obra_{obra['nome'].replace(' ', '_')}.pdf"
        return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f"inline;filename={filename}"})
    except FileNotFoundError:
        flash("ERRO: O programa 'wkhtmltopdf' não foi encontrado no caminho padrão. Verifique a instalação.", "danger")
        return redirect(url_for('detalhes_obra', id=id))


# --- Rotas de Administração e Excel ---

@app.route('/admin/usuarios', methods=['GET', 'POST'])
def gerenciar_usuarios():
    usuario = session.get('usuario')
    # Verificação de segurança: Apenas administradores logados
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado. Apenas administradores podem gerenciar usuários.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        sucesso, msg = auth.criar_usuario(username, password, role, usuario['id'])
        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('gerenciar_usuarios'))

    lista_de_usuarios = auth.listar_usuarios()
    perfis_disponiveis = auth.PERMISSOES.keys()
    return render_template('admin_usuarios.html', usuario=usuario, usuarios=lista_de_usuarios, perfis=perfis_disponiveis)

@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    usuario_sessao = session.get('usuario')
    if not usuario_sessao or usuario_sessao['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        # Pega a nova senha. Se estiver vazia, será None.
        nova_senha = request.form.get('password') or None
        sucesso, msg = auth.atualizar_usuario(id, username, role, usuario_sessao['id'], nova_senha)
        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('gerenciar_usuarios'))

    usuario_para_editar = auth.get_usuario(id)
    if not usuario_para_editar:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for('gerenciar_usuarios'))
    
    perfis_disponiveis = auth.PERMISSOES.keys()
    return render_template('admin_usuario_editar.html', usuario=usuario_sessao, usuario_para_editar=usuario_para_editar, perfis=perfis_disponiveis)

@app.route('/admin/usuarios/excluir/<int:id>')
def excluir_usuario(id):
    usuario_sessao = session.get('usuario')
    if not usuario_sessao or usuario_sessao['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    
    sucesso, msg = auth.excluir_usuario(id, usuario_sessao['id'])
    flash(msg, "success" if sucesso else "danger")
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/admin/obras', methods=['GET', 'POST'])
def gerenciar_obras():
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nome = request.form['nome']
        localizacao = request.form['localizacao']
        sucesso, msg = pedidos.criar_obra(nome, localizacao, usuario['id'])
        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('gerenciar_obras'))

    lista_obras = pedidos.listar_obras()
    return render_template('admin_obras.html', usuario=usuario, obras=lista_obras)

@app.route('/admin/obras/editar/<int:id>', methods=['GET', 'POST'])
def editar_obra(id):
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nome = request.form['nome']
        localizacao = request.form['localizacao']
        sucesso, msg = pedidos.atualizar_obra(id, nome, localizacao, usuario['id'])
        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('gerenciar_obras'))

    obra = pedidos.get_obra(id)
    if not obra:
        flash("Obra não encontrada.", "warning")
        return redirect(url_for('gerenciar_obras'))
    return render_template('admin_obra_editar.html', usuario=usuario, obra=obra)

@app.route('/admin/pedidos')
def gerenciar_pedidos():
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    
    pedidos_pendentes = pedidos.listar_pedidos_pendentes()
    return render_template('admin_pedidos.html', usuario=usuario, pedidos=pedidos_pendentes)

@app.route('/admin/pedidos/aprovar/<int:id>')
def aprovar_pedido(id):
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    
    sucesso, msg = pedidos.aprovar_pedido(id, usuario['id'])
    # flash(msg, "success" if sucesso else "danger") # Removido para não poluir a tela
    return redirect(url_for('gerenciar_pedidos'))

@app.route('/admin/pedidos/rejeitar', methods=['POST'])
def rejeitar_pedido():
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
    
    pedido_id = request.form['pedido_id']
    motivo = request.form['motivo_rejeicao']
    sucesso, msg = pedidos.rejeitar_pedido(int(pedido_id), usuario['id'], motivo)
    flash(msg, "success" if sucesso else "danger")
    return redirect(url_for('gerenciar_pedidos'))

@app.route('/obras')
def listar_obras_public():
    usuario = session.get('usuario')
    if not usuario: return redirect(url_for('login'))
    
    lista_obras = pedidos.listar_obras()
    return render_template('obras_lista.html', usuario=usuario, obras=lista_obras)

@app.route('/obras/<int:id>', methods=['GET', 'POST'])
def detalhes_obra(id):
    usuario = session.get('usuario')
    if not usuario: return redirect(url_for('login'))

    if request.method == 'POST':
        item_id = int(request.form['item_id'])
        quantidade = int(request.form['quantidade'])
        justificativa = request.form['justificativa']
        sucesso, msg = pedidos.criar_pedido_saida(item_id, quantidade, id, justificativa, usuario['id'])
        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('detalhes_obra', id=id))

    obra = pedidos.get_obra(id)
    materiais_enviados = pedidos.get_materiais_por_obra(id)
    
    # Calcula os totais para os cards
    total_quantidade_enviada = sum(m['quantidade'] for m in materiais_enviados)
    total_solicitacoes = len(materiais_enviados)

    itens_estoque = estoque.listar_itens()
    return render_template('obra_detalhes.html', usuario=usuario, obra=obra, materiais=materiais_enviados, itens_estoque=itens_estoque,
                           total_quantidade_enviada=total_quantidade_enviada, total_solicitacoes=total_solicitacoes)

@app.route('/admin/descricoes', methods=['GET', 'POST'])
def gerenciar_descricoes():
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nome_descricao = request.form['nome']
        sucesso, msg = gerenciamento.criar_descricao(nome_descricao, usuario['id'])
        flash(msg, "success" if sucesso else "danger")
        return redirect(url_for('gerenciar_descricoes'))

    lista_descricoes = gerenciamento.listar_descricoes()
    return render_template('admin_descricoes.html', usuario=usuario, descricoes=lista_descricoes)

@app.route('/admin/descricoes/excluir/<int:id>')
def excluir_descricao(id):
    usuario = session.get('usuario')
    if not usuario or usuario['role'] != 'administracao':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
        
    sucesso, msg = gerenciamento.excluir_descricao(id, usuario['id'])
    flash(msg, "success" if sucesso else "danger")
    return redirect(url_for('gerenciar_descricoes'))

@app.route('/admin/importar', methods=['POST'])
def importar_excel():
    usuario = session.get('usuario')
    if not usuario or not auth.tem_permissao(usuario['role'], 'all'):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    if 'planilha' not in request.files:
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for('dashboard'))

    file = request.files['planilha']
    if file.filename == '':
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for('dashboard'))

    if file and (file.filename.endswith('.xls') or file.filename.endswith('.xlsx')):
        # Salva o arquivo temporariamente para ser lido pelo pandas
        caminho_temporario = os.path.join("uploads", file.filename)
        os.makedirs("uploads", exist_ok=True)
        file.save(caminho_temporario)

        mensagem, categoria = excel_handler.importar_do_excel(caminho_temporario)
        flash(mensagem, categoria)

        os.remove(caminho_temporario) # Limpa o arquivo temporário
    else:
        flash("Formato de arquivo inválido. Use .xls ou .xlsx", "danger")

    return redirect(url_for('dashboard'))

@app.route('/admin/exportar')
def exportar_excel():
    usuario = session.get('usuario')
    if not usuario or not auth.tem_permissao(usuario['role'], 'all'):
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))

    caminho_arquivo, mensagem = excel_handler.exportar_para_excel()
    if caminho_arquivo:
        flash(mensagem, "success")
        return send_file(caminho_arquivo, as_attachment=True)
    else:
        flash(mensagem, "danger")
        return redirect(url_for('dashboard'))


def inicializar_sistema():
    """Função para ser executada uma vez na inicialização do servidor."""
    print("Inicializando o sistema...")
    criar_tabelas()
    # Cria um usuário administrador padrão se o banco de dados estiver vazio
    conn = auth.conectar_bd()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM usuarios")
            if cursor.fetchone()['count'] == 0:
                print("Nenhum usuário encontrado. Criando usuário 'admin' padrão com senha 'admin'.")
                # ID 0 para 'sistema' que está criando o primeiro usuário
                auth.criar_usuario("admin", "admin", "administracao", 0)
        except Exception as e:
            print(f"Erro ao verificar/criar usuário admin: {e}")
        finally:
            conn.close()
    print("Sistema pronto.")

if __name__ == "__main__":
    inicializar_sistema()
    # O modo debug recarrega o servidor a cada alteração de código.
    # Não use em produção!
    app.run(debug=True)
