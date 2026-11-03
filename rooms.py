"""Salas online: lobby, entrada por código e token por jogador (sem lógica de regras)."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional

from .engine import MAX_PLAYERS, Game, GameError

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # sem I e O, para não confundir com 1 e 0


class RoomNotFound(GameError):
    pass


class Unauthorized(GameError):
    pass


@dataclass
class Member:
    name: str
    token: str


@dataclass
class Room:
    code: str
    members: list[Member]
    game: Optional[Game] = None


def _clean_name(name: str, existing: list[Member]) -> str:
    n = " ".join((name or "").split())
    if not 1 <= len(n) <= 20:
        raise GameError("O nome deve ter de 1 a 20 caracteres.")
    if n.lower() in {m.name.lower() for m in existing}:
        raise GameError("Já existe um jogador com esse nome na sala.")
    return n


class RoomStore:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))
            if code not in self.rooms:
                return code

    def get(self, code: str) -> Room:
        room = self.rooms.get((code or "").strip().upper())
        if room is None:
            raise RoomNotFound("Sala não encontrada.")
        return room

    def create(self, name: str) -> tuple[Room, Member]:
        member = Member(_clean_name(name, []), secrets.token_urlsafe(16))
        room = Room(self._new_code(), [member])
        self.rooms[room.code] = room
        return room, member

    def join(self, code: str, name: str) -> tuple[Room, Member]:
        room = self.get(code)
        if room.game is not None:
            raise GameError("A partida já começou.")
        if len(room.members) >= MAX_PLAYERS:
            raise GameError(f"Sala cheia (máximo de {MAX_PLAYERS} jogadores).")
        member = Member(_clean_name(name, room.members), secrets.token_urlsafe(16))
        room.members.append(member)
        return room, member

    def auth(self, code: str, token: str) -> tuple[Room, int]:
        room = self.get(code)
        for i, m in enumerate(room.members):
            if secrets.compare_digest(m.token, token or ""):
                return room, i
        raise Unauthorized("Sessão inválida para esta sala.")

    def start(self, code: str, token: str) -> Room:
        room, idx = self.auth(code, token)
        if idx != 0:
            raise GameError("Só o anfitrião pode iniciar a partida.")
        if room.game is not None:
            raise GameError("A partida já começou.")
        room.game = Game([m.name for m in room.members])
        return room


def room_view(room: Room, idx: int) -> dict:
    """Visão da sala para o jogador `idx` (mostra só a mão dele)."""
    view = {
        "code": room.code,
        "started": room.game is not None,
        "members": [m.name for m in room.members],
        "you_index": idx,
        "is_host": idx == 0,
        "game": None,
        "log": [],
    }
    if room.game is not None:
        view["game"] = room.game.to_dict(viewer_id=f"p{idx + 1}")
        view["log"] = room.game.log_entries[-12:]
    return view
