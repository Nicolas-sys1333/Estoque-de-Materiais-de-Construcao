# estoque.py
import sqlite3
from database import conectar_bd
from logs import registrar_log

def criar_novo_item(nome, descricao_id, preco_unitario, quantidade, usuario_id):
    """Adiciona um novo item ao catálogo do estoque."""
    conn = conectar_bd()
    if not conn:
        return False, "Falha na conexão com o banco de dados."

    try:
        cursor = conn.cursor()
        # 1. Insere o item com quantidade 0 para garantir que ele exista antes da movimentação.
        cursor.execute(
            "INSERT INTO itens_estoque (nome, descricao_id, preco_unitario, quantidade) VALUES (?, ?, ?, 0)",
            (nome, descricao_id, preco_unitario)
        )
        item_id = cursor.lastrowid
        registrar_log(usuario_id, "CADASTRO_ITEM", f"Item: {nome}, ID: {item_id}")

        # 2. Se houver quantidade inicial, registra como uma movimentação de entrada.
        if quantidade > 0:
            conn.commit() # Comita a criação do item antes de chamar a outra função
            conn.close()
            # A função registrar_entrada já abre e fecha sua própria conexão.
            return registrar_entrada(item_id, quantidade, usuario_id, "Entrada inicial de estoque.")

        conn.commit()
        return True, f"Item '{nome}' cadastrado com sucesso."
    except sqlite3.IntegrityError:
        return False, f"Erro: O item '{nome}' já existe no catálogo."
    finally:
        if conn:
            conn.close()

def get_item(item_id: int):
    """Busca um item do estoque pelo seu ID."""
    conn = conectar_bd()
    if not conn: return None
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM itens_estoque WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    return dict(item) if item else None

def atualizar_item(item_id: int, nome: str, descricao_id: int, preco_unitario: float, usuario_id: int):
    """Atualiza os dados de um item do estoque."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE itens_estoque SET nome = ?, descricao_id = ?, preco_unitario = ? WHERE id = ?",
            (nome, descricao_id, preco_unitario, item_id)
        )
        conn.commit()
        registrar_log(usuario_id, "ATUALIZAR_ITEM", f"Item ID: {item_id}, Novo Nome: {nome}")
        return True, f"Item '{nome}' atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, f"O nome de item '{nome}' já está em uso."
    except Exception as e:
        return False, f"Erro ao atualizar item: {e}"
    finally:
        conn.close()

def _modificar_estoque(item_id, quantidade, tipo_movimentacao, usuario_id, observacao=""):
    """Função interna para registrar movimentação e atualizar quantidade."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."

    try:
        cursor = conn.cursor()
        
        # 1. Verificar se o item existe e obter a quantidade atual
        cursor.execute("SELECT quantidade, nome FROM itens_estoque WHERE id = ?", (item_id,))
        resultado = cursor.fetchone()
        if not resultado:
            return False, f"Erro: Item com ID {item_id} não encontrado."
        
        qtd_atual, nome_item = resultado

        # 2. Calcular nova quantidade e validar
        if tipo_movimentacao == 'saida':
            if qtd_atual < quantidade:
                return False, f"Erro: Estoque insuficiente para o item '{nome_item}'. Disponível: {qtd_atual}, Requisitado: {quantidade}"
            nova_quantidade = qtd_atual - quantidade
        else: # entrada ou compra
            nova_quantidade = qtd_atual + quantidade

        # 3. Atualizar a quantidade na tabela de itens
        cursor.execute("UPDATE itens_estoque SET quantidade = ? WHERE id = ?", (nova_quantidade, item_id))

        # 4. Registrar a movimentação
        cursor.execute(
            "INSERT INTO movimentacoes (item_id, tipo, quantidade, usuario_id, observacao) VALUES (?, ?, ?, ?, ?)",
            (item_id, tipo_movimentacao, quantidade, usuario_id, observacao)
        )
        
        conn.commit()
        mensagem = f"Movimentação '{tipo_movimentacao}' de {quantidade} unidade(s) do item '{nome_item}' registrada com sucesso."
        registrar_log(usuario_id, f"MOVIMENTACAO_{tipo_movimentacao.upper()}", f"Item ID: {item_id}, Qtd: {quantidade}, Novo Saldo: {nova_quantidade}")
        return True, mensagem

    except Exception as e:
        conn.rollback()
        return False, f"Erro ao modificar estoque: {e}"
    finally:
        conn.close()

def registrar_entrada(item_id, quantidade, usuario_id, observacao=""):
    return _modificar_estoque(item_id, quantidade, 'entrada', usuario_id, observacao)

def registrar_saida(item_id, quantidade, usuario_id, observacao=""):
    return _modificar_estoque(item_id, quantidade, 'saida', usuario_id, observacao)

def registrar_compra(item_id, quantidade, usuario_id, observacao=""):
    return _modificar_estoque(item_id, quantidade, 'compra', usuario_id, observacao)

def listar_itens():
    """Lista todos os itens do estoque com suas quantidades."""
    conn = conectar_bd()
    if not conn: return []
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.nome, i.quantidade, i.preco_unitario, d.nome as descricao
        FROM itens_estoque i
        LEFT JOIN descricoes d ON i.descricao_id = d.id
        ORDER BY i.nome
    """)
    itens = cursor.fetchall()
    conn.close()
    return [dict(item) for item in itens] # Converte para lista de dicionários

def listar_itens_estoque_baixo(minimo=50):
    """Lista todos os itens com quantidade igual ou abaixo do mínimo."""
    conn = conectar_bd()
    if not conn: return []
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.nome, i.quantidade
        FROM itens_estoque i
        WHERE i.quantidade <= ?
        ORDER BY i.quantidade ASC
    """, (minimo,))
    itens = cursor.fetchall()
    conn.close()
    return [dict(item) for item in itens]
