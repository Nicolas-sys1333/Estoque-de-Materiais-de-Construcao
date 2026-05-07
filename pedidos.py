# pedidos.py
import sqlite3
from datetime import datetime
from database import conectar_bd
from logs import registrar_log
import estoque

# --- Funções de Obras ---

def criar_obra(nome: str, cep: str, endereco: str, bairro: str, cidade: str, responsavel: str, usuario_id: int, status: str = 'Planejamento', previsao_conclusao: str = None):
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO obras (nome, cep, endereco, bairro, cidade, responsavel, status, previsao_conclusao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (nome, cep, endereco, bairro, cidade, responsavel, status, previsao_conclusao))
        conn.commit()
        registrar_log(usuario_id, "CRIAR_OBRA", f"Obra: {nome}")
        return True, f"Obra '{nome}' criada com sucesso."
    except sqlite3.IntegrityError:
        return False, f"A obra '{nome}' já existe."
    finally:
        conn.close()

def atualizar_obra(obra_id: int, nome: str, cep: str, endereco: str, bairro: str, cidade: str, responsavel: str, usuario_id: int, status: str, previsao_conclusao: str):
    """Atualiza os dados de uma obra existente."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE obras SET nome = ?, cep = ?, endereco = ?, bairro = ?, cidade = ?, responsavel = ?, status = ?, previsao_conclusao = ? WHERE id = ?", (nome, cep, endereco, bairro, cidade, responsavel, status, previsao_conclusao, obra_id))
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
    obra_row = cursor.fetchone()
    conn.close()
    if not obra_row:
        return None
    
    obra_dict = dict(obra_row)
    # Converte a string de data para um objeto datetime para que o Jinja2 possa formatá-la
    if obra_dict.get('previsao_conclusao'):
        try:
            # O formato armazenado no banco é 'YYYY-MM-DD HH:MM:SS'
            obra_dict['previsao_conclusao'] = datetime.strptime(obra_dict['previsao_conclusao'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            # Se a conversão falhar, define como None para evitar erros no template
            obra_dict['previsao_conclusao'] = None
    return obra_dict

# --- Funções de Pedidos ---

def criar_pedido_saida_com_itens(itens_pedido: list, obra_id: int, justificativa: str, solicitante_id: int):
    """
    Cria um único pedido de saída com múltiplos itens para uma obra.
    itens_pedido: lista de dicionários, ex: [{'item_id': 1, 'quantidade': 10}, ...]
    """
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    
    try:
        cursor = conn.cursor()
        # 1. Criar o pedido principal (sem item_id e quantidade)
        cursor.execute(
            "INSERT INTO pedidos (tipo, solicitante_id, obra_id, justificativa) VALUES ('saida', ?, ?, ?)",
            (solicitante_id, obra_id, justificativa)
        )
        pedido_id = cursor.lastrowid
        
        # 2. Inserir cada item na tabela 'itens_pedido'
        itens_inseridos = 0
        for item in itens_pedido:
            item_id = item['item_id']
            quantidade = item['quantidade']
            cursor.execute(
                "INSERT INTO itens_pedido (pedido_id, item_id, quantidade) VALUES (?, ?, ?)",
                (pedido_id, item_id, quantidade)
            )
            itens_inseridos += 1
        
        conn.commit()
        registrar_log(solicitante_id, "CRIAR_PEDIDO_SAIDA", f"Pedido ID: {pedido_id} com {itens_inseridos} itens para Obra ID: {obra_id}")
        return True, f"Pedido #{pedido_id} com {itens_inseridos} item(ns) enviado para aprovação."
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao criar pedidos: {e}"
    finally:
        if conn: conn.close()

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
    # Primeiro, busca os pedidos principais
    cursor.execute("""
        SELECT p.id, p.data_solicitacao, p.tipo, p.justificativa,
               u.username as solicitante_nome, o.nome as obra_nome
        FROM pedidos p
        JOIN usuarios u ON p.solicitante_id = u.id
        LEFT JOIN obras o ON p.obra_id = o.id
        WHERE p.status = 'pendente'
        ORDER BY p.data_solicitacao ASC
    """)
    pedidos_rows = cursor.fetchall()
    
    pedidos_formatados = []
    for p_row in pedidos_rows:
        pedido_dict = dict(p_row)
        pedido_dict['data_solicitacao'] = datetime.strptime(pedido_dict['data_solicitacao'], '%Y-%m-%d %H:%M:%S')
        
        # Agora, busca os itens para cada pedido
        if pedido_dict['tipo'] == 'saida':
            cursor.execute("""
                SELECT ip.quantidade, i.nome as item_nome
                FROM itens_pedido ip
                JOIN itens_estoque i ON ip.item_id = i.id
                WHERE ip.pedido_id = ?
            """, (pedido_dict['id'],))
            pedido_dict['itens'] = [dict(item) for item in cursor.fetchall()]
        else: # Pedido de compra, ainda usa o modelo antigo
            cursor.execute("""
                SELECT p.quantidade, i.nome as item_nome
                FROM pedidos p
                JOIN itens_estoque i ON p.item_id = i.id
                WHERE p.id = ?
            """, (pedido_dict['id'],))
            item_compra = cursor.fetchone()
            if item_compra:
                 pedido_dict['itens'] = [dict(item_compra)]
            else:
                 pedido_dict['itens'] = []

        pedidos_formatados.append(pedido_dict)
        
    conn.close()
    return pedidos_formatados

def aprovar_pedido(pedido_id: int, aprovador_id: int):
    from logistica import criar_despacho
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pedidos WHERE id = ? AND status = 'pendente'", (pedido_id,))
        pedido = cursor.fetchone()
        if not pedido:
            return False, "Pedido não encontrado ou já processado."

        # Se for um pedido de COMPRA, a aprovação significa entrada no estoque.
        if pedido['tipo'] == 'compra':
            observacao = f"Ref. Pedido de Compra Aprovado #{pedido_id}"
            sucesso, msg = estoque._modificar_estoque(
                pedido['item_id'], pedido['quantidade'], 'entrada', pedido['solicitante_id'], observacao, cursor=cursor
            )
            if not sucesso:
                conn.rollback()
                return False, msg
            
            # Atualiza o status do pedido de compra
            cursor.execute("UPDATE pedidos SET status = 'aprovado', aprovador_id = ?, data_decisao = CURRENT_TIMESTAMP WHERE id = ?", (aprovador_id, pedido_id))
            msg_final = f"Pedido de compra #{pedido_id} aprovado e estoque atualizado."

        # Se for um pedido de SAÍDA, a aprovação cria um DESPACHO automaticamente.
        elif pedido['tipo'] == 'saida':
            # 1. Buscar todos os itens do pedido
            cursor.execute("SELECT ip.item_id, ip.quantidade FROM itens_pedido ip WHERE ip.pedido_id = ?", (pedido_id,))
            itens_do_pedido = cursor.fetchall()
            if not itens_do_pedido:
                conn.rollback()
                return False, f"Pedido de saída #{pedido_id} não contém itens."

            # 2. Preparar dados e criar o despacho dentro da mesma transação
            itens_despacho_lista = [{'item_id': item['item_id'], 'quantidade': item['quantidade']} for item in itens_do_pedido]
            obra_id = pedido['obra_id']
            if not obra_id:
                conn.rollback()
                return False, "Pedido de saída não está associado a uma obra."

            sucesso_despacho, despacho_info = criar_despacho(
                obra_id=obra_id,
                nome_entregador="A Definir",
                telefone_entregador="",
                itens_despacho_lista=itens_despacho_lista,
                usuario_id=aprovador_id,
                observacoes=f"Gerado a partir do Pedido #{pedido_id}",
                pedido_id=pedido_id,
                cursor=cursor
            )
            
            if not sucesso_despacho:
                conn.rollback()
                return False, f"Falha ao criar despacho: {despacho_info}"
            
            cursor.execute("UPDATE pedidos SET status = 'aprovado', aprovador_id = ?, data_decisao = CURRENT_TIMESTAMP WHERE id = ?", (aprovador_id, pedido_id))
            msg_final = f"Pedido #{pedido_id} aprovado. Despacho #{despacho_info} foi criado automaticamente."

        else:
            conn.rollback()
            return False, f"Tipo de pedido '{pedido['tipo']}' desconhecido."
        
        conn.commit()
        registrar_log(aprovador_id, "APROVAR_PEDIDO", f"Pedido ID: {pedido_id}, Mensagem: {msg_final}")
        return True, msg_final
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Erro ao aprovar pedido: {e}"
    finally:
        if conn: conn.close()

def rejeitar_pedido(pedido_id: int, aprovador_id: int, motivo: str):
    """Altera o status de um pedido para 'rejeitado'."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pedidos WHERE id = ? AND status = 'pendente'", (pedido_id,))
        pedido = cursor.fetchone()
        if not pedido:
            return False, f"Pedido #{pedido_id} não encontrado, já foi processado ou não está mais pendente."
    except Exception as e:
        return False, f"Erro ao buscar pedido para rejeição: {e}"

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
        SELECT p.id, p.data_solicitacao, p.tipo, p.status, p.justificativa, p.motivo_rejeicao,
               o.nome as obra_nome
        FROM pedidos p
        LEFT JOIN obras o ON p.obra_id = o.id
        WHERE p.solicitante_id = ?
        ORDER BY p.data_solicitacao DESC
    """, (solicitante_id,))
    pedidos_rows = cursor.fetchall()
    
    pedidos_formatados = []
    for p_row in pedidos_rows:
        pedido_dict = dict(p_row)
        if pedido_dict.get('data_solicitacao'):
            pedido_dict['data_solicitacao'] = datetime.strptime(pedido_dict['data_solicitacao'], '%Y-%m-%d %H:%M:%S')
        
        # Busca os itens
        if pedido_dict['tipo'] == 'saida':
            cursor.execute("""
                SELECT ip.quantidade, i.nome as item_nome
                FROM itens_pedido ip
                JOIN itens_estoque i ON ip.item_id = i.id
                WHERE ip.pedido_id = ?
            """, (pedido_dict['id'],))
            pedido_dict['itens'] = [dict(item) for item in cursor.fetchall()]
        else: # Compra
            cursor.execute("""
                SELECT p.quantidade, i.nome as item_nome
                FROM pedidos p
                JOIN itens_estoque i ON p.item_id = i.id
                WHERE p.id = ?
            """, (pedido_dict['id'],))
            item_compra = cursor.fetchone()
            pedido_dict['itens'] = [dict(item_compra)] if item_compra else []
            
        pedidos_formatados.append(pedido_dict)
        
    conn.close()
    return pedidos_formatados