# auth.py
import hashlib
import sqlite3
from database import conectar_bd
from logs import registrar_log

# Mapeamento de permissões por perfil
PERMISSOES = {
    'administracao': ['all', 'cadastrar_item'],
    'engenheiro': ['ver_estoque', 'requisitar_saida', 'ver_relatorios'],
    'encarregado': ['ver_estoque', 'registrar_entrada', 'registrar_saida', 'cadastrar_item', 'ver_relatorios'],
    'comercial': ['ver_estoque', 'ver_relatorios']
}

def hash_password(password: str) -> str:
    """Gera um hash seguro para a senha."""
    return hashlib.sha256(password.encode()).hexdigest()

def criar_usuario(username, password, role, ator_id):
    """Cria um novo usuário. Apenas administradores podem fazer isso."""
    if role not in PERMISSOES:
        return False, f"Erro: Perfil '{role}' é inválido."

    conn = conectar_bd()
    if not conn:
        return False, "Erro: Falha na conexão com o banco de dados."

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role)
        )
        conn.commit()
        registrar_log(ator_id, "CRIACAO_USUARIO", f"Usuário: {username}, Perfil: {role}")
        return True, f"Usuário '{username}' criado com sucesso com o perfil '{role}'."
    except sqlite3.IntegrityError:
        return False, f"Erro: O nome de usuário '{username}' já existe."
    except Exception as e:
        return False, f"Ocorreu um erro ao criar o usuário: {e}"
    finally:
        conn.close()

def autenticar_usuario(username, password):
    """Autentica um usuário e retorna seus dados se as credenciais estiverem corretas."""
    conn = conectar_bd()
    if not conn: return None
    
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM usuarios WHERE username = ? AND password_hash = ?",
        (username, hash_password(password))
    )
    usuario = cursor.fetchone()
    conn.close()
    
    if usuario:
        registrar_log(usuario['id'], "LOGIN_SUCESSO", f"Usuário '{username}' logou.")
        return dict(usuario) # Retorna como um dicionário
    else:
        print("Login falhou: usuário ou senha incorretos.")
        # Não registramos o usuário em caso de falha para evitar enumeração de usuários
        registrar_log(0, "LOGIN_FALHA", f"Tentativa de login para usuário '{username}'.")
        return None

def tem_permissao(role: str, acao: str) -> bool:
    """Verifica se um perfil tem permissão para uma determinada ação."""
    permissoes_do_role = PERMISSOES.get(role, [])
    if 'all' in permissoes_do_role:
        return True
    return acao in permissoes_do_role

def listar_usuarios():
    """Lista todos os usuários cadastrados no sistema."""
    conn = conectar_bd()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM usuarios ORDER BY username")
    usuarios = cursor.fetchall()
    conn.close()
    return [dict(user) for user in usuarios]

def get_usuario(user_id: int):
    """Busca um usuário pelo seu ID."""
    conn = conectar_bd()
    if not conn: return None
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM usuarios WHERE id = ?", (user_id,))
    usuario = cursor.fetchone()
    conn.close()
    return dict(usuario) if usuario else None

def atualizar_usuario(user_id: int, username: str, role: str, ator_id: int):
    """Atualiza o username e o perfil de um usuário."""
    if role not in PERMISSOES:
        return False, f"Erro: Perfil '{role}' é inválido."
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET username = ?, role = ? WHERE id = ?", (username, role, user_id))
        conn.commit()
        registrar_log(ator_id, "ATUALIZAR_USUARIO", f"ID do Usuário: {user_id}, Novo Username: {username}, Novo Perfil: {role}")
        return True, "Usuário atualizado com sucesso."
    except sqlite3.IntegrityError:
        return False, f"O nome de usuário '{username}' já está em uso."
    finally:
        conn.close()

def excluir_usuario(user_id: int, ator_id: int):
    """Exclui um usuário do sistema."""
    conn = conectar_bd()
    if not conn: return False, "Falha na conexão com o banco de dados."
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
        conn.commit()
        registrar_log(ator_id, "EXCLUIR_USUARIO", f"ID do Usuário: {user_id}")
        return True, "Usuário excluído com sucesso."
    except Exception as e:
        return False, f"Erro ao excluir usuário: {e}"
    finally:
        conn.close()
