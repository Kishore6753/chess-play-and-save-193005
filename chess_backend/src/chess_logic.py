from __future__ import annotations

from dataclasses import dataclass
import random
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


def _piece_value(piece_type: int) -> int:
    # chess.PAWN..chess.KING
    return {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0,
    }.get(piece_type, 0)


def _material_score(board: chess.Board) -> int:
    """Material score from White's perspective (positive means White is ahead)."""
    score = 0
    for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        score += len(board.pieces(piece_type, chess.WHITE)) * _piece_value(piece_type)
        score -= len(board.pieces(piece_type, chess.BLACK)) * _piece_value(piece_type)
    return score


def _center_bonus(move: chess.Move) -> float:
    # Encourage moves into/affecting central squares.
    center = {chess.D4, chess.E4, chess.D5, chess.E5}
    bonus = 0.0
    if move.to_square in center:
        bonus += 0.25
    # Small preference for developing towards center-ish squares
    if move.to_square in {chess.C3, chess.F3, chess.C6, chess.F6}:
        bonus += 0.10
    return bonus


def _static_eval_for_side(board: chess.Board, side: chess.Color) -> float:
    """Rough evaluation from `side` perspective (positive is good for `side`)."""
    # Terminal conditions take precedence.
    if board.is_checkmate():
        # If it's checkmate and it's current side's turn, current side is checkmated.
        return -9999.0
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0.0

    mat = _material_score(board)
    mat_for_side = float(mat if side == chess.WHITE else -mat)
    # Prefer giving check a bit.
    check_bonus = 0.25 if board.is_check() else 0.0
    return mat_for_side + check_bonus


def _choose_ai_move(board: chess.Board, *, level: int) -> chess.Move:
    """Choose a legal move for the current side-to-move using a simple heuristic.

    Level meaning:
      - 1: random legal move
      - 2: prefer captures / center / checks using one-ply eval
      - 3: simple 1-ply with a basic opponent response (very small minimax depth=2)
    """
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        raise ValueError("No legal moves available for this position.")

    if level <= 1:
        return random.choice(legal_moves)

    side = board.turn

    def score_move_one_ply(m: chess.Move) -> float:
        # Prefer captures and promotions.
        capture_bonus = 0.0
        if board.is_capture(m):
            capture_bonus += 0.5
            captured_piece = board.piece_at(m.to_square)
            if captured_piece:
                capture_bonus += 0.1 * _piece_value(captured_piece.piece_type)

        promo_bonus = 0.0
        if m.promotion:
            promo_bonus += 1.0

        center = _center_bonus(m)

        board.push(m)
        try:
            eval_after = _static_eval_for_side(board, side)
        finally:
            board.pop()

        return capture_bonus + promo_bonus + center + eval_after

    def score_move_level3(m: chess.Move) -> float:
        # Two-ply: AI chooses m, then assume opponent plays best response.
        board.push(m)
        try:
            if board.is_checkmate():
                return 9999.0  # immediate mate
            opp_moves = list(board.legal_moves)
            if not opp_moves:
                # No moves: either mate/stalemate, handled above, but be safe.
                return _static_eval_for_side(board, side)

            # Opponent tries to minimize AI's evaluation.
            worst_for_us = float("inf")
            for om in opp_moves:
                board.push(om)
                try:
                    val = _static_eval_for_side(board, side)
                finally:
                    board.pop()
                if val < worst_for_us:
                    worst_for_us = val

            # Small bonuses still matter.
            return worst_for_us + _center_bonus(m) + (0.2 if board.is_check() else 0.0)
        finally:
            board.pop()

    scorer = score_move_level3 if level >= 3 else score_move_one_ply
    scored = [(scorer(m), m) for m in legal_moves]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Keep some variety among top choices
    top_n = max(1, min(5, len(scored)))
    top_slice = scored[:top_n]

    # If everything is equal-ish, just pick randomly
    return random.choice([m for _, m in top_slice])


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
def generate_ai_move(fen: str, *, ai_level: int = 1) -> AppliedMove:
    """Generate and apply a legal AI move for the current side-to-move.

    This is a lightweight heuristic-based AI (no external engines).
    It chooses among legal moves, preferring (at higher levels) captures,
    promotions, central control, checks, and slightly better material outcomes.

    Args:
        fen: Current position as FEN, or the literal string 'startpos'.
        ai_level: Difficulty level 1-3.

    Returns:
        AppliedMove result of the chosen move.

    Raises:
        ValueError: if the position is invalid or no legal moves exist.
    """
    board = _board_from_fen_or_startpos(fen)
    fen_before = board.fen()

    move = _choose_ai_move(board, level=max(1, min(3, ai_level)))
    san_norm = board.san(move)

    board.push(move)
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


# PUBLIC_INTERFACE
def derive_position_flags(fen: str) -> Tuple[str, bool, bool, bool, bool]:
    """Return (turn, is_check, is_checkmate, is_stalemate, is_draw) for FEN/startpos."""
    board = _board_from_fen_or_startpos(fen)
    turn = "w" if board.turn == chess.WHITE else "b"
    is_check = board.is_check()
    is_checkmate = board.is_checkmate()
    is_stalemate = board.is_stalemate()
    is_draw = (
        board.is_insufficient_material()
        or board.can_claim_fifty_moves()
        or board.can_claim_threefold_repetition()
        or is_stalemate
    )
    return turn, is_check, is_checkmate, is_stalemate, is_draw
