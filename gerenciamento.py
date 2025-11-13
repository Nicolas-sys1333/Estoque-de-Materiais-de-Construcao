# gerenciamento.py
import sqlite3
from database import conectar_bd
from logs import registrar_log

def listar_descricoes():
    """Lista todas as descrições do catálogo."""
    conn = conectar_bd()
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM descricoes ORDER BY nome")
    descricoes = cursor.fetchall()
    conn.close()
    return [dict(d) for d in descricoes]

def criar_descricao(nome: str, usuario_id: int):
    """Cria uma nova descrição no catálogo."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO descricoes (nome) VALUES (?)", (nome,))
        conn.commit()
        registrar_log(usuario_id, "CRIAR_DESCRICAO", f"Descrição: {nome}")
        return True, f"Descrição '{nome}' criada com sucesso."
    except sqlite3.IntegrityError:
        return False, f"A descrição '{nome}' já existe."
    finally:
        conn.close()

def excluir_descricao(descricao_id: int, usuario_id: int):
    """Exclui uma descrição do catálogo."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM descricoes WHERE id = ?", (descricao_id,))
        conn.commit()
        registrar_log(usuario_id, "EXCLUIR_DESCRICAO", f"ID da Descrição: {descricao_id}")
        return True, "Descrição excluída com sucesso."
    except sqlite3.IntegrityError:
        return False, "Erro: Esta descrição está em uso por um ou mais itens e não pode ser excluída."
    finally:
        conn.close()