# pedidos.py
import sqlite3
from database import conectar_bd
from logs import registrar_log
import estoque

# --- Funções de Obras ---

def criar_obra(nome: str, localizacao: str, usuario_id: int):
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO obras (nome, localizacao) VALUES (?, ?)", (nome, localizacao))
        conn.commit()
        registrar_log(usuario_id, "CRIAR_OBRA", f"Obra: {nome}")
        return True, f"Obra '{nome}' criada com sucesso."
    except sqlite3.IntegrityError:
        return False, f"A obra '{nome}' já existe."
    finally:
        conn.close()

def atualizar_obra(obra_id: int, nome: str, localizacao: str, usuario_id: int):
    """Atualiza os dados de uma obra existente."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE obras SET nome = ?, localizacao = ? WHERE id = ?", (nome, localizacao, obra_id))
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Nenhuma obra encontrada com este ID."
        registrar_log(usuario_id, "ATUALIZAR_OBRA", f"Obra ID: {obra_id}, Novo Nome: {nome}")
        return True, f"Obra '{nome}' atualizada com sucesso."
    except sqlite3.IntegrityError:
        return False, f"O nome de obra '{nome}' já está em uso por outra obra."
    finally:
        conn.close()

def listar_obras():
    conn = conectar_bd()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM obras ORDER BY nome")
    obras = cursor.fetchall()
    conn.close()
    return [dict(o) for o in obras]

def get_obra(obra_id: int):
    conn = conectar_bd()
    if not conn: return None
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM obras WHERE id = ?", (obra_id,))
    obra = cursor.fetchone()
    conn.close()
    return dict(obra) if obra else None

def get_materiais_por_obra(obra_id: int):
    """Busca materiais enviados para uma obra específica."""
    conn = conectar_bd()
    if not conn: return []

    # Primeiro, busca o nome da obra para usar no filtro
    cursor = conn.cursor()
    cursor.execute("SELECT nome FROM obras WHERE id = ?", (obra_id,))
    obra = cursor.fetchone()
    if not obra:
        conn.close()
        return []
    
    # Agora, busca as movimentações usando o nome da obra na observação
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.data, i.nome as item_nome, m.quantidade, u.username as usuario_nome
        FROM movimentacoes m
        JOIN itens_estoque i ON m.item_id = i.id
        JOIN usuarios u ON m.usuario_id = u.id
        WHERE m.tipo = 'saida' AND m.observacao LIKE ?
        ORDER BY m.data DESC
    """, (f"Obra: {obra['nome']}%",))
    materiais = cursor.fetchall()
    conn.close()
    return [dict(m) for m in materiais]

# --- Funções de Pedidos ---

def criar_pedido_saida(item_id: int, quantidade: int, obra_id: int, justificativa: str, solicitante_id: int):
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pedidos (item_id, quantidade, tipo, solicitante_id, obra_id, justificativa) VALUES (?, ?, 'saida', ?, ?, ?)",
            (item_id, quantidade, solicitante_id, obra_id, justificativa)
        )
        conn.commit()
        registrar_log(solicitante_id, "CRIAR_PEDIDO_SAIDA", f"Item ID: {item_id}, Qtd: {quantidade}, Obra ID: {obra_id}")
        return True, "Pedido de saída de material enviado para aprovação."
    except Exception as e:
        return False, f"Erro ao criar pedido: {e}"
    finally:
        conn.close()

def criar_pedido_compra(item_id: int, quantidade: int, justificativa: str, solicitante_id: int):
    """Cria um pedido de compra para um item, que fica pendente de aprovação."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pedidos (item_id, quantidade, tipo, solicitante_id, justificativa) VALUES (?, ?, 'compra', ?, ?)",
            (item_id, quantidade, solicitante_id, justificativa)
        )
        conn.commit()
        registrar_log(solicitante_id, "CRIAR_PEDIDO_COMPRA", f"Item ID: {item_id}, Qtd: {quantidade}")
        return True, "Pedido de compra enviado para aprovação."
    except Exception as e:
        return False, f"Erro ao criar pedido de compra: {e}"
    finally:
        conn.close()

def listar_pedidos_pendentes():
    conn = conectar_bd()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.data_solicitacao, p.tipo, p.quantidade, p.justificativa,
               i.nome as item_nome, u.username as solicitante_nome, o.nome as obra_nome
        FROM pedidos p
        JOIN itens_estoque i ON p.item_id = i.id
        JOIN usuarios u ON p.solicitante_id = u.id
        LEFT JOIN obras o ON p.obra_id = o.id
        WHERE p.status = 'pendente'
        ORDER BY p.data_solicitacao ASC
    """)
    pedidos = cursor.fetchall()
    conn.close()
    return [dict(p) for p in pedidos]

def aprovar_pedido(pedido_id: int, aprovador_id: int):
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    cursor = conn.cursor()
    # Busca o pedido e o nome da obra associada
    cursor.execute("""
        SELECT p.*, o.nome as obra_nome 
        FROM pedidos p 
        LEFT JOIN obras o ON p.obra_id = o.id 
        WHERE p.id = ? AND p.status = 'pendente'
    """, (pedido_id,))
    pedido = cursor.fetchone()
    if not pedido:
        conn.close()
        return False, "Pedido não encontrado ou já processado."

    # Efetiva a movimentação no estoque
    observacao = f"Ref. Pedido Aprovado #{pedido_id}"
    if pedido['obra_id'] and pedido['obra_nome']:
        observacao = f"Obra: {pedido['obra_nome']} (Pedido #{pedido_id})"

    # CORREÇÃO: A movimentação é registrada em nome do solicitante original, não do aprovador.
    solicitante_id = pedido['solicitante_id']

    # CORREÇÃO: Padroniza o tipo de movimentação para 'entrada' quando o pedido é de 'compra'.
    tipo_movimentacao = 'entrada' if pedido['tipo'] == 'compra' else pedido['tipo']

    sucesso, msg = estoque._modificar_estoque(pedido['item_id'], pedido['quantidade'], tipo_movimentacao, solicitante_id, observacao)

    if sucesso:
        # Apenas se a movimentação de estoque for bem-sucedida, atualiza o status do pedido.
        cursor.execute("UPDATE pedidos SET status = 'aprovado', aprovador_id = ?, data_decisao = CURRENT_TIMESTAMP WHERE id = ?", (aprovador_id, pedido_id))
        conn.commit()
        registrar_log(aprovador_id, "APROVAR_PEDIDO", f"Pedido ID: {pedido_id}")
    
    conn.close()
    return sucesso, msg

def rejeitar_pedido(pedido_id: int, aprovador_id: int, motivo: str):
    """Altera o status de um pedido para 'rejeitado'."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pedidos WHERE id = ? AND status = 'pendente'", (pedido_id,))
    pedido = cursor.fetchone()
    if not pedido:
        conn.close()
        return False, "Pedido não encontrado ou já processado."

    cursor.execute("UPDATE pedidos SET status = 'rejeitado', aprovador_id = ?, data_decisao = CURRENT_TIMESTAMP, motivo_rejeicao = ? WHERE id = ?", (aprovador_id, motivo, pedido_id))
    conn.commit()
    registrar_log(aprovador_id, "REJEITAR_PEDIDO", f"Pedido ID: {pedido_id}, Motivo: {motivo}")
    conn.close()
    return True, "Pedido rejeitado com sucesso."

def get_pedidos_por_solicitante(solicitante_id: int):
    """Busca todos os pedidos feitos por um usuário específico."""
    conn = conectar_bd()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.data_solicitacao, p.tipo, p.quantidade, p.status, p.justificativa, p.motivo_rejeicao,
               i.nome as item_nome, o.nome as obra_nome
        FROM pedidos p
        JOIN itens_estoque i ON p.item_id = i.id
        LEFT JOIN obras o ON p.obra_id = o.id
        WHERE p.solicitante_id = ?
        ORDER BY p.data_solicitacao DESC
    """, (solicitante_id,))
    pedidos = cursor.fetchall()
    conn.close()
    return [dict(p) for p in pedidos]