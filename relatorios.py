# relatorios.py
from database import conectar_bd

def get_todas_movimentacoes(page=1, per_page=15):
    """Busca todas as movimentações do estoque de forma paginada."""
    conn = conectar_bd()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            m.id,
            m.data,
            i.nome as item_nome,
            m.tipo,
            m.quantidade,
            u.username as usuario_nome,
            m.observacao
        FROM movimentacoes m
        JOIN itens_estoque i ON m.item_id = i.id
        JOIN usuarios u ON m.usuario_id = u.id
        ORDER BY m.data DESC
        LIMIT ? OFFSET ?
    """, (per_page, (page - 1) * per_page))
    movimentacoes = [dict(row) for row in cursor.fetchall()]

    # Pega o total de registros para calcular o total de páginas
    cursor.execute("SELECT COUNT(*) as total FROM movimentacoes")
    total = cursor.fetchone()['total']

    conn.close()
    return {
        "movimentacoes": movimentacoes,
        "total": total,
        "page": page,
        "per_page": per_page
    }

def get_ultimas_movimentacoes(limit=5):
    """Busca as últimas N movimentações do estoque."""
    conn = conectar_bd()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            m.data,
            i.nome as item_nome,
            m.tipo,
            m.quantidade,
            u.username as usuario_nome
        FROM movimentacoes m
        JOIN itens_estoque i ON m.item_id = i.id
        JOIN usuarios u ON m.usuario_id = u.id
        ORDER BY m.data DESC
        LIMIT ?
    """, (limit,))
    movimentacoes = cursor.fetchall()
    conn.close()
    return [dict(mov) for mov in movimentacoes]

def get_dados_graficos():
    """Prepara dados agregados para os gráficos do dashboard de relatórios."""
    conn = conectar_bd()
    if not conn:
        return {
            "mov_por_tipo": {"labels": [], "data": []},
            "top_saidas": {"labels": [], "data": []}
        }

    cursor = conn.cursor()

    # 1. Dados para o gráfico de movimentações por tipo
    cursor.execute("SELECT tipo, COUNT(*) as count FROM movimentacoes GROUP BY tipo")
    mov_por_tipo_raw = cursor.fetchall()
    mov_por_tipo = {
        "labels": [row['tipo'].capitalize() for row in mov_por_tipo_raw],
        "data": [row['count'] for row in mov_por_tipo_raw]
    }

    # 2. Dados para o gráfico de top 5 itens com mais saída (por quantidade)
    cursor.execute("""
        SELECT i.nome, SUM(m.quantidade) as total_saida
        FROM movimentacoes m
        JOIN itens_estoque i ON m.item_id = i.id
        WHERE m.tipo = 'saida'
        GROUP BY i.nome
        ORDER BY total_saida DESC
        LIMIT 5
    """)
    top_saidas_raw = cursor.fetchall()
    top_saidas = {
        "labels": [row['nome'] for row in top_saidas_raw],
        "data": [row['total_saida'] for row in top_saidas_raw]
    }

    conn.close()
    return {"mov_por_tipo": mov_por_tipo, "top_saidas": top_saidas}

def relatorio_saldo_geral():
    """Calcula e retorna o valor total do estoque."""
    conn = conectar_bd()
    if not conn: 
        return 0.0

    cursor = conn.cursor()
    # Calcula o valor total (quantidade * preço unitário) para cada item e soma tudo
    cursor.execute("SELECT SUM(quantidade * preco_unitario) as valor_total FROM itens_estoque")
    resultado = cursor.fetchone()
    conn.close()

    valor_total = resultado['valor_total'] if resultado['valor_total'] else 0.0
    return valor_total

def get_movimentacoes_do_dia():
    """Calcula o total de entradas e saídas do dia atual."""
    conn = conectar_bd()
    if not conn:
        return {"total_entrada": 0, "total_saida": 0}

    cursor = conn.cursor()

    # Total de entradas no dia
    cursor.execute("SELECT SUM(quantidade) as total FROM movimentacoes WHERE tipo = 'entrada' AND DATE(data, 'localtime') = DATE('now', 'localtime')")
    entrada_dia = cursor.fetchone()['total'] or 0

    # Total de saídas no dia
    cursor.execute("SELECT SUM(quantidade) as total FROM movimentacoes WHERE tipo = 'saida' AND DATE(data, 'localtime') = DATE('now', 'localtime')")
    saida_dia = cursor.fetchone()['total'] or 0

    conn.close()
    return {
        "total_entrada": entrada_dia,
        "total_saida": saida_dia
    }
