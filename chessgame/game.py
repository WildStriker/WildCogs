"""module contains Game class and helper function to list variants"""
from typing import Optional, Tuple

import cairosvg
import chess
import chess.svg
import chess.variant


class Game:
    """class used to hold state of a game"""

    _style = 'text {' \
        'fill: orange' \
        '}'

    def __init__(self, player_black_id, player_white_id, variant_name=None):
        if not variant_name:
            variant_name = 'Standard'

        self._board = chess.variant.find_variant(variant_name)()

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

    def move_piece(self, move) -> Tuple[bool, Optional[str], str]:
        """move piece, if a valid move returns a tuple with game over flag and message

        Args:
            move: san movement of the next piece

        Returns:
            Tuple[bool, str, str]: returns a tuple with three values
                                bool - True if the game is over
                                str - this is an id of the player that is being notified
                                str - this is a template message to be displayed,
                                      use mention_id to fill in user id
        """

        _, player_turn, player_next = self.order

        move: chess.Move = self._board.push_san(move)
        self._arrows = [(move.from_square, move.to_square)]

        # Chess variants
        if self._board.is_variant_loss():
            mention = f"<@{self.player_black_id}>"
            return True, mention, f"{mention} wins!"

        if self._board.is_variant_win():
            mention = f"<@{self.player_white_id}>"
            return True, mention, f"{mention} wins!"

        if self._board.is_variant_draw():
            return True, None, "Draw! Game Over!"

        # Checkmate.
        if self._board.is_checkmate():
            mention = f"<@{player_turn}>"
            return True, mention, f"Checkmate! {mention} Wins!"

        # Seventyfive-move rule or fivefold repetition.
        if self._board.is_seventyfive_moves():
            return True, None, "Draw by seventyfive moves rule!" \
                "There are been no captures or pawns moved in the last 75 moves"

        if self._board.is_fivefold_repetition():
            return True, None, "Draw by fivefold repetition!" \
                "Position has occured five times"

        # Insufficient material.
        if self._board.is_insufficient_material():
            return True, None, "Draw by insufficient material!\n" \
                "Neither player has enough pieces to win"

        mention = f"<@{player_next}>"
        # Stalemate.
        if self._board.is_stalemate():
            return True, mention, "Draw by stalemate!\n" \
                f"{mention} has no moves!"

        if self._board.is_check():
            return False, mention, f"{mention} you are in check. Your move is next."

        return False, mention, f"{mention} you're up next!"

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
            return 'Black', self.player_black_id, self.player_white_id

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

    @property
    def type(self):
        """return the first alias"""
        return self._board.aliases[0]


def start_help_text():
    """list the variant aliases that can be used"""
    message = []

    message.append('start a new game\n')
    message.append('_Standard is the default when no game type is given_')
    for count, variant in enumerate(chess.variant.VARIANTS, 1):
        aliases = ', '.join(variant.aliases)
        message.append(f'__**{count}**__: {aliases}')

    return '\n'.join(message)
