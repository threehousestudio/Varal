import unittest

from app.engine import GameError
from app.rooms import RoomNotFound, RoomStore, Unauthorized, room_view


class Salas(unittest.TestCase):
    def setUp(self):
        self.s = RoomStore()

    def test_criar_entrar_iniciar(self):
        room, host = self.s.create("Ana")
        _, bia = self.s.join(room.code.lower(), "Bia")
        self.assertEqual(len(room.code), 4)
        with self.assertRaises(GameError):
            self.s.start(room.code, bia.token)  # só o anfitrião
        self.s.start(room.code, host.token)
        self.assertIsNotNone(room.game)
        with self.assertRaises(GameError):
            self.s.join(room.code, "Caio")  # já começou
        with self.assertRaises(GameError):
            self.s.start(room.code, host.token)

    def test_visao_mostra_so_a_propria_mao(self):
        room, host = self.s.create("Ana")
        _, bia = self.s.join(room.code, "Bia")
        self.s.start(room.code, host.token)
        v0, v1 = room_view(room, 0), room_view(room, 1)
        self.assertIn("hand", v0["game"]["players"][0])
        self.assertNotIn("hand", v0["game"]["players"][1])
        self.assertIn("hand", v1["game"]["players"][1])
        self.assertNotIn("hand", v1["game"]["players"][0])

    def test_auth_e_erros(self):
        room, host = self.s.create("Ana")
        with self.assertRaises(Unauthorized):
            self.s.auth(room.code, "token-falso")
        with self.assertRaises(RoomNotFound):
            self.s.get("ZZZZ")
        with self.assertRaises(GameError):
            self.s.join(room.code, "ana")  # nome repetido
        with self.assertRaises(GameError):
            self.s.create("   ")

    def test_sala_cheia(self):
        room, _ = self.s.create("P0")
        for i in range(1, 6):
            self.s.join(room.code, f"P{i}")
        with self.assertRaises(GameError):
            self.s.join(room.code, "P6")

    def test_jogador_2_joga_na_vez_dele(self):
        room, host = self.s.create("Ana")
        _, bia = self.s.join(room.code, "Bia")
        self.s.start(room.code, host.token)
        room.game.end_turn("p1")
        self.assertEqual(room_view(room, 1)["game"]["current_player"], "p2")


if __name__ == "__main__":
    unittest.main()
