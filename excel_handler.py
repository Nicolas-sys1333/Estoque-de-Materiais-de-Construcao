# excel_handler.py
import pandas as pd
import unicodedata
from database import conectar_bd

def importar_do_excel(caminho_arquivo: str):
    """
    Lê uma planilha Excel e insere/atualiza os itens no banco de dados.
    A planilha deve ter as colunas: 'Nome', 'Descricao', 'Preco_Unitario', 'Quantidade'.
    """
    try:
        # Especifica o motor 'openpyxl' para garantir compatibilidade com .xlsx
        # Para .xls, o pandas tentará usar 'xlrd' se estiver instalado.
        engine = 'openpyxl' if caminho_arquivo.endswith('.xlsx') else None
        df = pd.read_excel(caminho_arquivo, engine=engine)

        # --- MELHORIA: Normaliza os nomes das colunas ---
        def normalize_header(header):
            # Remove acentos, espaços, converte para minúsculo e remove caracteres especiais
            s = ''.join(c for c in unicodedata.normalize('NFD', header) if unicodedata.category(c) != 'Mn')
            return s.lower().replace(" ", "").replace("_", "")

        df.columns = [normalize_header(col) for col in df.columns]
        # Mapeamento de nomes de coluna normalizados para os nomes esperados no banco de dados
        column_mapping = {
            'nome': 'Nome', 'descricao': 'Descricao', 'precounitario': 'Preco_Unitario', 'quantidade': 'Quantidade'
        }
        df.rename(columns=column_mapping, inplace=True)

    except FileNotFoundError:
        return "ERRO: Arquivo não encontrado.", "error"
    except Exception as e:
        return f"ERRO ao ler o arquivo Excel: {e}", "error"

    required_cols = ['Nome', 'Descricao', 'Preco_Unitario', 'Quantidade']
    # --- MELHORIA: Mensagem de erro mais específica ---
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return f"ERRO: A planilha não foi importada. Coluna(s) faltando: {', '.join(missing_cols)}. Verifique se o nome das colunas no arquivo Excel está correto.", "danger"

    conn = conectar_bd()
    if not conn:
        return "ERRO: Falha na conexão com o banco de dados.", "error"

    cursor = conn.cursor()
    count_sucesso = 0
    for _, row in df.iterrows():
        try:
            # Tenta inserir. Se o item já existe (UNIQUE constraint no nome), ignora.
            # Primeiro, encontra ou cria o ID da descrição
            descricao_nome = row['Descricao']
            cursor.execute("SELECT id FROM descricoes WHERE nome = ?", (descricao_nome,))
            descricao_row = cursor.fetchone()
            if descricao_row:
                descricao_id = descricao_row['id']
            else:
                # Se a descrição não existe, cria e pega o ID
                cursor.execute("INSERT INTO descricoes (nome) VALUES (?)", (descricao_nome,))
                descricao_id = cursor.lastrowid

            # Insere o item com o ID da descrição
            cursor.execute(
                "INSERT OR IGNORE INTO itens_estoque (nome, descricao_id, preco_unitario, quantidade) VALUES (?, ?, ?, ?)",
                (row['Nome'], descricao_id, row['Preco_Unitario'], row['Quantidade'])
            )
            if cursor.rowcount > 0:
                count_sucesso += 1
        except Exception as e:
            conn.close()
            return f"ERRO ao inserir o item '{row['Nome']}': {e}", "error"
    
    conn.commit()
    conn.close()
    return f"{count_sucesso} novos itens importados com sucesso da planilha.", "success"

def exportar_para_excel():
    """Exporta o saldo atual do estoque para um arquivo Excel."""
    conn = conectar_bd()
    if not conn:
        return None, "ERRO: Falha na conexão com o banco de dados."

    # Usamos o Pandas para ler diretamente a query do SQL para um DataFrame
    df = pd.read_sql_query("""
        SELECT i.id, i.nome, d.nome as descricao, i.quantidade, i.preco_unitario
        FROM itens_estoque i
        LEFT JOIN descricoes d ON i.descricao_id = d.id
        ORDER BY i.nome
    """, conn)
    conn.close()

    caminho_saida = "saldo_estoque_exportado.xlsx"
    df.to_excel(caminho_saida, index=False, engine='openpyxl')

    return caminho_saida, f"Estoque exportado com sucesso para '{caminho_saida}'."