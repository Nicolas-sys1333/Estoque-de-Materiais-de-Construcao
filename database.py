# database.py
import sqlite3
import logging

DB_NAME = "estoque.db"

def conectar_bd():
    """Conecta ao banco de dados SQLite e retorna a conexão e o cursor."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome
        return conn
    except sqlite3.Error as e:
        logging.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def criar_tabelas():
    """Cria as tabelas iniciais do banco de dados se não existirem."""
    conn = conectar_bd()
    if not conn:
        return

    cursor = conn.cursor()
    
    # Tabela de Usuários com perfis de acesso
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('administracao', 'engenheiro', 'encarregado', 'comercial'))
    );
    """)

    # Tabela de Descrições (catálogo)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS descricoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    );
    """)

    # Tabela de Itens do Estoque
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        descricao_id INTEGER,
        quantidade INTEGER NOT NULL DEFAULT 0,
        preco_unitario REAL,
        FOREIGN KEY (descricao_id) REFERENCES descricoes (id)
    );
    """)

    # Tabela de Log de Auditoria
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs_auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER,
        acao TEXT NOT NULL,
        detalhes TEXT,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    );
    """)
    
    # Tabela de Movimentações (Entrada, Saída, Compra)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('entrada', 'saida', 'compra')),
        quantidade INTEGER NOT NULL,
        data DATETIME DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER,
        observacao TEXT,
        FOREIGN KEY (item_id) REFERENCES itens_estoque (id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    );
    """)

    # Tabela de Obras
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS obras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        localizacao TEXT
    );
    """)

    # Tabela de Pedidos (de compra ou de saída para obras)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        quantidade INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('compra', 'saida')),
        status TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente', 'aprovado', 'rejeitado')),
        data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        solicitante_id INTEGER NOT NULL,
        data_decisao DATETIME,
        aprovador_id INTEGER,
        obra_id INTEGER,
        justificativa TEXT,
        motivo_rejeicao TEXT,
        FOREIGN KEY (item_id) REFERENCES itens_estoque (id),
        FOREIGN KEY (solicitante_id) REFERENCES usuarios (id),
        FOREIGN KEY (aprovador_id) REFERENCES usuarios (id),
        FOREIGN KEY (obra_id) REFERENCES obras (id)
    );
    """)

    print("Tabelas verificadas/criadas com sucesso.")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Este bloco permite criar o banco de dados executando `python database.py`
    criar_tabelas()
    print(f"Banco de dados '{DB_NAME}' e tabelas foram criados/verificados.")
