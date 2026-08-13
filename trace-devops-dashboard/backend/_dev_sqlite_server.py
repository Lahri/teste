"""
Sobe o backend de verdade (app.main:app + repo_sqlite.py real, nao mock)
com alguns itens de exemplo, pra rodar localmente sem precisar de
Docker/Oracle/conta em nada. E' o modo "zero setup" pra desenvolver e
demonstrar o painel ja'.

Uso:
    python _dev_sqlite_server.py
Depois abra http://localhost:8000/
"""
import os

os.environ.setdefault("DB_BACKEND", "sqlite")

import uvicorn  # noqa: E402

from app import repo  # noqa: E402

_SEED = [
    ("611742", "Larissa", "NEF", "APIs do BB no Contas a Receber", "Em testes", "2026-06-12"),
    ("600100", "Larissa", "RH", "Ajuste de folha de pagamento mensal", "Em análise", "2026-01-01"),
    ("548213", "Maurício", "NEF", "Controle de compras e pagamento de cartão", "Em Desenvolvimento", None),
]


def seed():
    conn = repo._impl._connect()
    for id_demanda, analista, sigla, descricao, status, previsao in _SEED:
        conn.execute(
            """INSERT OR IGNORE INTO itens (id_demanda, analista, sigla, descricao, status, previsao_analise)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (id_demanda, analista, sigla, descricao, status, previsao),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed()
    from app.main import app
    uvicorn.run(app, host="0.0.0.0", port=8000)
