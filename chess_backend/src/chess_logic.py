from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import chess


@dataclass(frozen=True)
class AppliedMove:
    """Result of applying a move to a position."""

    fen_before: str
    fen_after: str
    uci: str
    san: str
    status: str  # active/checkmate/stalemate/draw


def _board_from_fen_or_startpos(fen: str) -> chess.Board:
    if fen == "startpos":
        return chess.Board()
    return chess.Board(fen)


def _status_from_board(board: chess.Board) -> str:
    # Basic detection (good enough for typical apps).
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "draw"
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        # Claimable draws; treat as draw for simplicity.
        return "draw"
    return "active"


# PUBLIC_INTERFACE
def apply_move(fen: str, *, uci: Optional[str], san: Optional[str]) -> AppliedMove:
    """Apply a chess move to a given FEN (or 'startpos').

    The move must be legal for the side to move. This enforces:
    - turn order
    - legal move generation
    - king safety (no moving into check)

    Args:
        fen: Current position as FEN, or the literal string 'startpos'.
        uci: UCI move string (e.g. 'e2e4', 'e7e8q')
        san: SAN move string (e.g. 'e4', 'Nf3', 'O-O')

    Returns:
        AppliedMove containing before/after FEN, SAN and UCI, and derived game status.

    Raises:
        ValueError: when the move is missing or illegal/invalid.
    """
    if not uci and not san:
        raise ValueError("Either 'uci' or 'san' must be provided.")

    board = _board_from_fen_or_startpos(fen)
    fen_before = board.fen()

    try:
        if san:
            move = board.parse_san(san)
            san_norm = board.san(move)
        else:
            move = chess.Move.from_uci(uci)  # type: ignore[arg-type]
            if move not in board.legal_moves:
                raise ValueError("Illegal move for the current position.")
            san_norm = board.san(move)

        board.push(move)
    except ValueError as e:
        # parse_san / from_uci can raise ValueError
        raise ValueError(str(e)) from e
    except Exception as e:
        raise ValueError("Invalid move input.") from e

    fen_after = board.fen()
    status = _status_from_board(board)

    return AppliedMove(
        fen_before=fen_before,
        fen_after=fen_after,
        uci=move.uci(),
        san=san_norm,
        status=status,
    )


# PUBLIC_INTERFACE
def derive_turn_and_check(fen: str) -> Tuple[str, bool]:
    """Return (turn, is_check) for a given FEN (or 'startpos')."""
    board = _board_from_fen_or_startpos(fen)
    turn = "w" if board.turn == chess.WHITE else "b"
    return turn, board.is_check()
