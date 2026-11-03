# Varal API

Motor + API REST do jogo Varal (1 a 6 jogadores). Estado em memória.

## Rodar
    pip install -r requirements.txt
    uvicorn app.main:app --reload      # docs interativas em /docs

## Testes do motor (sem dependências)
    python -m unittest discover -s tests -v

## Jogar online
Abra a URL do servidor (`/`). Um jogador cria a sala e passa o código (ou o link `/?sala=CODE`) aos outros;
o anfitrião inicia a partida (1 a 6 jogadores). A tela atualiza sozinha (polling a cada 1,5 s) e
a sessão fica salva no navegador, então recarregar a página não tira você da sala.
Rotas: `POST /rooms`, `POST /rooms/{code}/join`, `GET /rooms/{code}?token=`, `POST /rooms/{code}/start`, `POST /rooms/{code}/actions`.

## Fluxo (API direta, sem sala nem autenticação)
1. `POST /games` `{"players": ["Ana","Bia"]}` → cria a partida (já compra a carta do 1º turno).
2. `GET /games/{id}?player_id=p1` → estado (mostra a mão só desse jogador).
3. `POST /games/{id}/actions` (até 2 por turno), `type`:
   - `hang` {card_id, position?}  – estender roupa
   - `pin` {card_id, piece_ids[1-2]} – qualquer carta vira pregador
   - `play_action` {card_id, params}
   - `collect` {piece_ids[]} – recolher um conjunto válido (peças adjacentes); pregadores vão para o descarte
   - `reposition` {piece_id, position} – mover uma peça no varal (custa 1 ação)
   - `end_turn` – revela o clima e passa a vez
4. `GET /games/{id}/log`, `GET /rules/scoring`.

## Onde ajustar
- `GameConfig` (engine.py): cores, quantidade de cartas, composição do Baralho de Clima, mão inicial.
- `ACTION_EFFECTS` (engine.py): efeitos das cartas de Ação (hoje só existe `nenhum`).
- Comentários `ASSUNÇÃO` marcam decisões que as regras não definiam.
