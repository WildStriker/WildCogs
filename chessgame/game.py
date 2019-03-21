"""module contains Game class"""
from typing import Tuple

import cairosvg
import chess
import chess.svg


class Game:
    """class used to hold state of a game"""

    _style = 'text {' \
        'fill: orange' \
        '}'

    def __init__(self, player_black_id, player_white_id):

        self._board = chess.Board()
        self._arrows = ()

        self._player_black_id = player_black_id
        self._player_white_id = player_white_id

    def get_board_text(self) -> str:
        """returns the game board as text"""
        return str(self._board)

    def get_board_image(self) -> bytes:
        """returns the game as an image

        can't embed svg, so convert to png first
        """

        lastmove = self._board.peek() if self._board.move_stack else None
        check = self._board.king(
            self._board.turn) if self._board.is_check() else None

        # get svg string
        svg_board = chess.svg.board(
            board=self._board,
            lastmove=lastmove,
            check=check,
            arrows=self._arrows,
            style=self._style).encode()

        # convert to png
        image_board = cairosvg.svg2png(bytestring=svg_board)
        return image_board

    def move_piece(self, move) -> Tuple[bool, str]:
        """move piece, if a valid move returns a tuple with game over flag and message"""

        _, player_turn, player_next = self.order

        move: chess.Move = self._board.push_san(move)
        self._arrows = [(move.from_square, move.to_square)]

        # Checkmate.
        if self._board.is_checkmate():
            return True, f"Checkmate! <@{player_turn}> Wins!"

        # Seventyfive-move rule or fivefold repetition.
        if self._board.is_seventyfive_moves():
            return True, "Draw by seventyfive moves rule!" \
                "There are been no captures or pawns moved in the last 75 moves"

        if self._board.is_fivefold_repetition():
            return True, "Draw by fivefold repetition!" \
                "Position has occured five times"

        # Insufficient material.
        if self._board.is_insufficient_material():
            return True, "Draw by insufficient material!\n" \
                "Neither player has enough pieces to win"

        # Stalemate.
        if self._board.is_stalemate():
            return True, "Draw by stalemate!\n" \
                f"<@{player_next.id}> has no moves!"

        if self._board.is_check():
            return False, f"<@{player_next}> you are in check. Your move is next."

        return False, f"<@{player_next}> you're up next!"

    @property
    def total_moves(self) -> int:
        """total moves taken"""
        return len(self._board.move_stack)

    @property
    def order(self):
        """return color, player id turn and player id that is next"""

        if self._board.turn == chess.WHITE:
            return 'White', self.player_white_id, self.player_black_id
        else:
            return 'Black', self.player_black_id, self.player_black_id

    @property
    def player_white_id(self) -> str:
        """returns the player assigned to white pieces"""
        return self._player_white_id

    @property
    def player_black_id(self) -> str:
        """returns the player assigned to black pieces"""
        return self._player_black_id

    @property
    def can_claim_draw(self):
        """true if players can claim a draw"""
        return self._board.can_claim_draw()

    @property
    def can_claim_fifty_moves(self):
        """true if players can claim a draw by fifty moves"""
        return self._board.can_claim_fifty_moves()

    @property
    def can_claim_threefold_repetition(self):
        """true if players can claim a draw by threefold repetition"""
        return self._board.can_claim_threefold_repetition()
