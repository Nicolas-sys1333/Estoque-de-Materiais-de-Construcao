# logs.py
from database import conectar_bd

def registrar_log(usuario_id: int, acao: str, detalhes: str = ""):
    """Registra uma ação no log de auditoria."""
    conn = conectar_bd()
    if not conn:
        print("ERRO: Não foi possível registrar o log por falha na conexão com o BD.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs_auditoria (usuario_id, acao, detalhes) VALUES (?, ?, ?)",
            (usuario_id, acao, detalhes)
        )
        conn.commit()
    except Exception as e:
        print(f"Erro ao registrar log: {e}")
    finally:
        conn.close()
