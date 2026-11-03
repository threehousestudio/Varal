"""API REST + salas online do jogo Varal. Estado em memória (reiniciar apaga tudo)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .engine import SCORING_TABLE, Game, GameError
from .rooms import RoomNotFound, RoomStore, Unauthorized, room_view

app = FastAPI(title="Varal API", version="0.2.0")

GAMES: dict[str, Game] = {}
STORE = RoomStore()
LOCK = threading.Lock()  # as rotas síncronas rodam em threads; serializa as mutações
STATIC = Path(__file__).parent / "static"


# ---------------------------------------------------------------- modelos
class ActionBody(BaseModel):
    type: Literal["hang", "pin", "play_action", "collect", "reposition", "end_turn"]
    card_id: Optional[str] = None  # hang, pin, play_action
    piece_ids: Optional[list[str]] = None  # pin (1-2 peças), collect
    piece_id: Optional[str] = None  # reposition: peça a mover
    position: Optional[int] = None  # hang: posição (padrão: final); reposition: posição final
    params: dict = Field(default_factory=dict)  # play_action


class ActionRequest(ActionBody):
    player_id: str


class RoomActionRequest(ActionBody):
    token: str


class CreateGameRequest(BaseModel):
    players: list[str] = Field(..., min_length=1, max_length=6)
    seed: Optional[int] = None


class NameRequest(BaseModel):
    name: str


class TokenRequest(BaseModel):
    token: str


# ---------------------------------------------------------------- helpers
def _need(value, name: str, action: str):
    if value is None:
        raise HTTPException(422, f"'{name}' é obrigatório para a ação '{action}'.")
    return value


def _err(e: GameError) -> HTTPException:
    if isinstance(e, RoomNotFound):
        return HTTPException(404, str(e))
    if isinstance(e, Unauthorized):
        return HTTPException(403, str(e))
    return HTTPException(400, str(e))


def _apply(game: Game, player_id: str, req: ActionBody) -> dict:
    t = req.type
    if t == "hang":
        game.hang(player_id, _need(req.card_id, "card_id", t), req.position)
    elif t == "pin":
        game.pin(player_id, _need(req.card_id, "card_id", t), _need(req.piece_ids, "piece_ids", t))
    elif t == "play_action":
        game.play_action(player_id, _need(req.card_id, "card_id", t), req.params)
    elif t == "collect":
        return game.collect(player_id, _need(req.piece_ids, "piece_ids", t))
    elif t == "reposition":
        game.reposition(player_id, _need(req.piece_id, "piece_id", t), _need(req.position, "position", t))
    elif t == "end_turn":
        return {"weather": game.end_turn(player_id)}
    return {}


# ---------------------------------------------------------------- tela e utilidades
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/rules/scoring")
def scoring() -> list[dict]:
    return SCORING_TABLE


# ---------------------------------------------------------------- salas online
@app.post("/rooms", status_code=201)
def create_room(req: NameRequest) -> dict:
    with LOCK:
        try:
            room, member = STORE.create(req.name)
        except GameError as e:
            raise _err(e)
        return {"code": room.code, "token": member.token, "view": room_view(room, 0)}


@app.post("/rooms/{code}/join")
def join_room(code: str, req: NameRequest) -> dict:
    with LOCK:
        try:
            room, member = STORE.join(code, req.name)
        except GameError as e:
            raise _err(e)
        return {"code": room.code, "token": member.token, "view": room_view(room, len(room.members) - 1)}


@app.get("/rooms/{code}")
def get_room(code: str, token: str = Query(...)) -> dict:
    with LOCK:
        try:
            room, idx = STORE.auth(code, token)
        except GameError as e:
            raise _err(e)
        return room_view(room, idx)


@app.post("/rooms/{code}/start")
def start_room(code: str, req: TokenRequest) -> dict:
    with LOCK:
        try:
            room = STORE.start(code, req.token)
            _, idx = STORE.auth(code, req.token)
        except GameError as e:
            raise _err(e)
        return room_view(room, idx)


@app.post("/rooms/{code}/actions")
def room_action(code: str, req: RoomActionRequest) -> dict:
    with LOCK:
        try:
            room, idx = STORE.auth(code, req.token)
            if room.game is None:
                raise GameError("A partida ainda não começou.")
            _apply(room.game, f"p{idx + 1}", req)
        except GameError as e:
            raise _err(e)
        return room_view(room, idx)


# ---------------------------------------------------------------- API direta (sem sala, sem autenticação)
@app.post("/games", status_code=201)
def create_game(req: CreateGameRequest) -> dict:
    try:
        game = Game(req.players, seed=req.seed)
    except GameError as e:
        raise HTTPException(400, str(e))
    with LOCK:
        GAMES[game.id] = game
    return game.to_dict()


def _get_game(game_id: str) -> Game:
    game = GAMES.get(game_id)
    if game is None:
        raise HTTPException(404, "Partida não encontrada.")
    return game


@app.get("/games/{game_id}")
def get_game(game_id: str, player_id: Optional[str] = Query(None)) -> dict:
    with LOCK:
        return _get_game(game_id).to_dict(viewer_id=player_id)


@app.get("/games/{game_id}/log")
def get_log(game_id: str) -> list[str]:
    with LOCK:
        return _get_game(game_id).log_entries


@app.post("/games/{game_id}/actions")
def do_action(game_id: str, req: ActionRequest) -> dict:
    with LOCK:
        game = _get_game(game_id)
        try:
            outcome = _apply(game, req.player_id, req)
        except GameError as e:
            raise HTTPException(400, str(e))
        return {"outcome": outcome, "state": game.to_dict(viewer_id=req.player_id)}
