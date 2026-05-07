import sqlite3
from datetime import datetime
from database import conectar_bd
from logs import registrar_log
import estoque # Para registrar a saída do estoque

def criar_despacho(obra_id: int, nome_entregador: str, telefone_entregador: str, itens_despacho_lista: list, usuario_id: int, observacoes: str = "", pedido_id: int = None, cursor=None):
    """
    Cria um novo despacho. Pode operar em uma transação existente se um cursor for fornecido.
    Retorna (True, despacho_id) em sucesso, ou (False, error_message) em falha.
    """
    manage_transaction = cursor is None
    conn = None
    if manage_transaction:
        conn = conectar_bd()
        if not conn: return False, "Falha na conexão com o banco de dados."
        cursor = conn.cursor()

    try:
        
        # 1. Criar o despacho principal
        cursor.execute(
            "INSERT INTO despachos_obras (obra_id, nome_entregador, telefone_entregador, nome_recebedor, usuario_despacho_id, observacoes) VALUES (?, ?, ?, ?, ?, ?)",
            (obra_id, nome_entregador, telefone_entregador, None, usuario_id, observacoes)
        )
        despacho_id = cursor.lastrowid

        # 2. Adicionar os itens ao despacho e registrar saída do estoque
        for item_data in itens_despacho_lista:
            item_id = int(item_data['item_id'])
            quantidade = int(item_data['quantidade'])
            
            # Registrar saída do estoque
            sucesso_saida, msg_saida = estoque._modificar_estoque(
                item_id, 
                quantidade, 
                'saida', 
                usuario_id, 
                f"Saída para Despacho #{despacho_id} - Obra ID: {obra_id}",
                cursor=cursor)
            if not sucesso_saida:
                if manage_transaction: conn.rollback()
                return False, f"Erro ao registrar saída do item {item_id}: {msg_saida}"
            
            # Adicionar item ao despacho
            cursor.execute(
                "INSERT INTO itens_despacho (despacho_id, item_id, quantidade) VALUES (?, ?, ?)",
                (despacho_id, item_id, quantidade)
            )
        
        # 3. Se o despacho foi originado de um pedido, vincular os dois
        if pedido_id:
            cursor.execute(
                "UPDATE pedidos SET despacho_id = ? WHERE id = ?",
                (despacho_id, pedido_id)
            )
        
        if manage_transaction:
            conn.commit()
        
        registrar_log(usuario_id, "CRIAR_DESPACHO", f"Despacho ID: {despacho_id}, Obra ID: {obra_id}")
        # Return despacho_id on success
        return True, despacho_id
    except sqlite3.IntegrityError as e:
        if manage_transaction: conn.rollback()
        return False, f"Erro de integridade ao criar despacho: {e}"
    except Exception as e:
        if manage_transaction: conn.rollback()
        return False, f"Erro ao criar despacho: {e}"
    finally:
        if manage_transaction and conn:
            conn.close()

def listar_despachos():
    """Lista todos os despachos com informações básicas."""
    conn = conectar_bd()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT do.id, do.data_despacho, o.nome as obra_nome, do.nome_entregador, do.status_entrega, do.data_entrega, u.username as usuario_despacho_nome
        FROM despachos_obras do
        JOIN obras o ON do.obra_id = o.id
        JOIN usuarios u ON do.usuario_despacho_id = u.id
        ORDER BY do.data_despacho DESC
    """)
    despachos_rows = cursor.fetchall()
    conn.close()
    
    despachos_formatados = []
    for d_row in despachos_rows:
        d_dict = dict(d_row)
        if d_dict.get('data_despacho'):
            d_dict['data_despacho'] = datetime.strptime(d_dict['data_despacho'], '%Y-%m-%d %H:%M:%S')
        if d_dict.get('data_entrega'):
            d_dict['data_entrega'] = datetime.strptime(d_dict['data_entrega'], '%Y-%m-%d %H:%M:%S')
        despachos_formatados.append(d_dict)
    return despachos_formatados

def get_despacho(despacho_id: int):
    """Busca os detalhes de um despacho específico, incluindo seus itens."""
    conn = conectar_bd()
    if not conn: return None
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT do.*, o.nome as obra_nome, o.cep, o.endereco, o.bairro, o.cidade, o.responsavel as obra_responsavel, u.username as usuario_despacho_nome
        FROM despachos_obras do
        JOIN obras o ON do.obra_id = o.id
        JOIN usuarios u ON do.usuario_despacho_id = u.id
        WHERE do.id = ?
    """, (despacho_id,))
    despacho = cursor.fetchone()
    
    if despacho:
        despacho_dict = dict(despacho)
        # Converte as strings de data para objetos datetime
        if despacho_dict.get('data_despacho'):
            despacho_dict['data_despacho'] = datetime.strptime(despacho_dict['data_despacho'], '%Y-%m-%d %H:%M:%S')
        if despacho_dict.get('data_entrega'):
            despacho_dict['data_entrega'] = datetime.strptime(despacho_dict['data_entrega'], '%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            SELECT id.quantidade, ie.nome as item_nome, ie.id as item_id
            FROM itens_despacho id
            JOIN itens_estoque ie ON id.item_id = ie.id
            WHERE id.despacho_id = ?
        """, (despacho_id,))
        itens = cursor.fetchall()
        despacho_dict['itens'] = [dict(item) for item in itens]
        conn.close()
        return despacho_dict
    
    conn.close()
    return None

def get_despachos_por_obra(obra_id: int):
    """Busca todos os despachos para uma obra específica, incluindo seus itens e totais."""
    conn = conectar_bd()
    if not conn: return []
    
    try:
        cursor = conn.cursor()
        
        # 1. Busca todos os despachos para a obra
        cursor.execute("""
            SELECT 
                do.id, do.data_despacho, do.nome_entregador, do.status_entrega, 
                do.data_entrega, u.username as usuario_despacho_nome
            FROM despachos_obras do
            JOIN usuarios u ON do.usuario_despacho_id = u.id
            WHERE do.obra_id = ?
            ORDER BY do.data_despacho DESC
        """, (obra_id,))
        despachos = cursor.fetchall()
        
        despachos_com_itens = []
        for despacho in despachos:
            despacho_dict = dict(despacho)
            
            # Converte as strings de data para objetos datetime para uso no template
            if despacho_dict.get('data_despacho'):
                despacho_dict['data_despacho'] = datetime.strptime(despacho_dict['data_despacho'], '%Y-%m-%d %H:%M:%S')
            if despacho_dict.get('data_entrega'):
                despacho_dict['data_entrega'] = datetime.strptime(despacho_dict['data_entrega'], '%Y-%m-%d %H:%M:%S')
            
            # 2. Para cada despacho, busca seus itens
            cursor.execute("""
                SELECT 
                    id.quantidade, ie.nome as item_nome, ie.id as item_id
                FROM itens_despacho id
                JOIN itens_estoque ie ON id.item_id = ie.id
                WHERE id.despacho_id = ?
            """, (despacho_dict['id'],))
            itens = [dict(item) for item in cursor.fetchall()]
            despacho_dict['itens'] = itens
            despachos_com_itens.append(despacho_dict)
            
        return despachos_com_itens
    finally:
        if conn: conn.close()

def atualizar_status_entrega(despacho_id: int, novo_status: str, data_entrega_str: str, nome_recebedor_atualizado: str, usuario_id: int, nome_entregador: str, telefone_entregador: str):
    """Atualiza o status de entrega de um despacho e a data de entrega, se aplicável."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        
        # Busca o estado atual do despacho para tomar a decisão
        cursor.execute("SELECT data_despacho FROM despachos_obras WHERE id = ?", (despacho_id,))
        despacho_atual = cursor.fetchone()
        if not despacho_atual:
            return False, "Despacho não encontrado."

        # Validar o status e a data de entrega (data_entrega é NOT NULL se status for 'Entregue')
        status_permitidos = ['Pendente', 'Em Rota', 'Entregue', 'Problema']
        if novo_status not in status_permitidos:
            return False, "Status de entrega inválido."
        
        if not nome_entregador:
            return False, "O nome do entregador é obrigatório."

        data_entrega = None
        if novo_status == 'Entregue':
            if not data_entrega_str:
                return False, "A data de entrega é obrigatória para o status 'Entregue'."
            if not nome_recebedor_atualizado:
                return False, "O nome do recebedor é obrigatório para o status 'Entregue'."
            try:
                data_entrega = datetime.strptime(data_entrega_str, '%Y-%m-%d').strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                return False, "Formato de data de entrega inválido. Use YYYY-MM-DD."
        else:
            # Se o status não é 'Entregue', o nome do recebedor deve ser NULL
            nome_recebedor_atualizado = None
        
        set_clauses = [
            "nome_entregador = ?",
            "telefone_entregador = ?",
            "status_entrega = ?",
            "data_entrega = ?",
            "nome_recebedor = ?"
        ]
        params = [nome_entregador, telefone_entregador, novo_status, data_entrega, nome_recebedor_atualizado]

        # Se o novo status for 'Em Rota' e a data do despacho ainda não foi definida,
        # adiciona a atualização da data do despacho para o momento atual.
        if novo_status == 'Em Rota' and despacho_atual['data_despacho'] is None:
            set_clauses.append("data_despacho = CURRENT_TIMESTAMP")

        query = f"UPDATE despachos_obras SET {', '.join(set_clauses)} WHERE id = ?"
        params.append(despacho_id)
        
        cursor.execute(query, params)
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Despacho não encontrado."
        
        registrar_log(usuario_id, "ATUALIZAR_DESPACHO", f"Despacho ID: {despacho_id}, Entregador: {nome_entregador}, Status: {novo_status}")
        return True, f"Status do despacho #{despacho_id} atualizado para '{novo_status}'."
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao atualizar status do despacho: {e}"
    finally:
        conn.close()