# database.py
import sqlite3
import logging

DB_NAME = "estoque.db"

def conectar_bd():
    """Conecta ao banco de dados SQLite e retorna a conexão."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logging.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def _get_table_schema(cursor, table_name):
    """Retorna o esquema de uma tabela como um dicionário."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {col['name']: col for col in cursor.fetchall()}
    except sqlite3.OperationalError:
        return {} # Tabela não existe

def _recreate_table(conn, cursor, table_name, create_sql):
    """Procedimento seguro para recriar uma tabela, preservando os dados."""
    print(f"Recriando tabela '{table_name}' para aplicar novo esquema...")
    temp_table_name = f"{table_name}_old_temp"
    
    cursor.execute("BEGIN TRANSACTION")
    try:
        # 1. Renomeia a tabela antiga
        cursor.execute(f"ALTER TABLE {table_name} RENAME TO {temp_table_name}")
        
        # 2. Cria a nova tabela com o esquema correto
        cursor.execute(create_sql)
        
        # 3. Copia os dados da tabela antiga para a nova, mapeando colunas
        old_cols_rows = cursor.execute(f"PRAGMA table_info({temp_table_name})").fetchall()
        old_cols = [col['name'] for col in old_cols_rows]
        
        new_cols_rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        new_cols = [col['name'] for col in new_cols_rows]
        
        common_cols = ", ".join([col for col in old_cols if col in new_cols])
        
        cursor.execute(f"INSERT INTO {table_name} ({common_cols}) SELECT {common_cols} FROM {temp_table_name}")
        
        # 4. Remove a tabela temporária
        cursor.execute(f"DROP TABLE {temp_table_name}")
        
        conn.commit()
        print(f"Tabela '{table_name}' migrada com sucesso.")
    except Exception as e:
        conn.rollback()
        print(f"ERRO ao migrar a tabela '{table_name}': {e}. A operação foi desfeita.")

def criar_tabelas():
    """Cria e/ou atualiza as tabelas do banco de dados de forma segura."""
    conn = conectar_bd()
    if not conn:
        return

    cursor = conn.cursor()
    
    # --- Definições SQL para o esquema final ---
    
    create_usuarios_sql = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('administracao', 'engenheiro', 'encarregado', 'comercial'))
    );"""
    
    create_descricoes_sql = "CREATE TABLE IF NOT EXISTS descricoes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL);"
    
    create_itens_estoque_sql = """
    CREATE TABLE IF NOT EXISTS itens_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL, descricao_id INTEGER,
        quantidade INTEGER NOT NULL DEFAULT 0, preco_unitario REAL,
        FOREIGN KEY (descricao_id) REFERENCES descricoes (id)
    );"""
    
    create_logs_auditoria_sql = """
    CREATE TABLE IF NOT EXISTS logs_auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, usuario_id INTEGER,
        acao TEXT NOT NULL, detalhes TEXT, FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    );"""

    create_movimentacoes_sql = """
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('entrada', 'saida', 'compra')),
        quantidade INTEGER NOT NULL, data DATETIME DEFAULT CURRENT_TIMESTAMP, usuario_id INTEGER,
        observacao TEXT, FOREIGN KEY (item_id) REFERENCES itens_estoque (id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    );"""

    create_obras_sql = """
    CREATE TABLE IF NOT EXISTS obras (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL, cep TEXT, endereco TEXT,
        bairro TEXT, cidade TEXT, responsavel TEXT, status TEXT, previsao_conclusao DATETIME
    );"""

    # Esquema final para despachos_obras
    create_despachos_obras_sql = """
    CREATE TABLE despachos_obras (
        id INTEGER PRIMARY KEY AUTOINCREMENT, obra_id INTEGER NOT NULL, data_despacho DATETIME,
        nome_entregador TEXT NOT NULL, telefone_entregador TEXT, nome_recebedor TEXT,
        status_entrega TEXT NOT NULL DEFAULT 'Pendente' CHECK(status_entrega IN ('Pendente', 'Em Rota', 'Entregue', 'Problema')),
        data_entrega DATETIME, usuario_despacho_id INTEGER NOT NULL, observacoes TEXT,
        FOREIGN KEY (obra_id) REFERENCES obras (id),
        FOREIGN KEY (usuario_despacho_id) REFERENCES usuarios (id)
    );"""

    create_itens_despacho_sql = """
    CREATE TABLE IF NOT EXISTS itens_despacho (
        id INTEGER PRIMARY KEY AUTOINCREMENT, despacho_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
        quantidade INTEGER NOT NULL, FOREIGN KEY (despacho_id) REFERENCES despachos_obras (id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES itens_estoque (id)
    );"""

    # Esquema final para pedidos
    create_pedidos_sql = """
    CREATE TABLE pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, quantidade INTEGER,
        tipo TEXT NOT NULL CHECK(tipo IN ('compra', 'saida')),
        status TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente', 'aprovado', 'rejeitado')),
        data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP, solicitante_id INTEGER NOT NULL,
        data_decisao DATETIME, aprovador_id INTEGER, obra_id INTEGER, despacho_id INTEGER,
        justificativa TEXT, motivo_rejeicao TEXT,
        FOREIGN KEY (item_id) REFERENCES itens_estoque (id),
        FOREIGN KEY (solicitante_id) REFERENCES usuarios (id),
        FOREIGN KEY (aprovador_id) REFERENCES usuarios (id),
        FOREIGN KEY (obra_id) REFERENCES obras (id)
    );"""

    create_itens_pedido_sql = """
    CREATE TABLE IF NOT EXISTS itens_pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
        quantidade INTEGER NOT NULL, FOREIGN KEY (pedido_id) REFERENCES pedidos (id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES itens_estoque (id)
    );"""

    # --- Execução da criação e migração ---
    
    cursor.execute(create_usuarios_sql)
    cursor.execute(create_descricoes_sql)
    cursor.execute(create_itens_estoque_sql)
    cursor.execute(create_logs_auditoria_sql)
    cursor.execute(create_movimentacoes_sql)
    cursor.execute(create_obras_sql)
    cursor.execute(create_itens_despacho_sql)
    cursor.execute(create_itens_pedido_sql)

    # --- Migrações de esquema para tabelas existentes ---
    
    # Migração para 'pedidos' (remover NOT NULL)
    pedidos_schema = _get_table_schema(cursor, 'pedidos')
    if pedidos_schema and (
        (pedidos_schema.get('item_id') and pedidos_schema['item_id']['notnull']) or
        (pedidos_schema.get('quantidade') and pedidos_schema['quantidade']['notnull'])
    ):
        _recreate_table(conn, cursor, 'pedidos', create_pedidos_sql)
    else:
        cursor.execute(create_pedidos_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))

    # Migração para 'despachos_obras' (remover DEFAULT de data_despacho e NOT NULL de telefone)
    despachos_schema = _get_table_schema(cursor, 'despachos_obras')
    if despachos_schema and (
        (despachos_schema.get('data_despacho') and despachos_schema['data_despacho']['dflt_value'] is not None) or
        (despachos_schema.get('telefone_entregador') and despachos_schema['telefone_entregador']['notnull'])
    ):
        _recreate_table(conn, cursor, 'despachos_obras', create_despachos_obras_sql)
    else:
        cursor.execute(create_despachos_obras_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))

    conn.commit()
    print("Tabelas verificadas/atualizadas com sucesso.")
    conn.close()

if __name__ == '__main__':
    criar_tabelas()
    print(f"Banco de dados '{DB_NAME}' e tabelas foram criados/verificados.")
