from __future__ import annotations

from typing import List, Optional

import chess
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from src.chess_logic import apply_move, derive_turn_and_check
from src.db import get_db
from src.models import Game, GameSnapshot, Move, User
from src.schemas import (
    CreateGameRequest,
    ErrorResponse,
    GameResponse,
    LoadGameRequest,
    MoveResponse,
    SaveGameRequest,
    SnapshotResponse,
    SubmitMoveRequest,
)

router = APIRouter(prefix="/games", tags=["games"])


def _serialize_move(m: Move) -> MoveResponse:
    return MoveResponse(
        id=m.id,
        move_number=m.move_number,
        uci=m.uci,
        san=m.san,
        created_at=m.created_at,
    )


def _serialize_game(game: Game) -> GameResponse:
    turn, is_check = derive_turn_and_check(game.fen)
    return GameResponse(
        id=game.id,
        white_user_id=game.white_user_id,
        black_user_id=game.black_user_id,
        fen=game.fen if game.fen != "startpos" else chess.Board().fen(),
        turn=turn,
        status=game.status,
        is_check=is_check,
        moves=[_serialize_move(m) for m in game.moves],
    )


def _require_user_if_provided(db: Session, user_id: Optional[str]) -> None:
    if user_id is None:
        return
    if not db.get(User, user_id):
        raise HTTPException(status_code=400, detail=f"User '{user_id}' does not exist.")


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=GameResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
    summary="Create a new game",
    description="Create a new chess game. Players are optional; if provided, they must exist.",
    operation_id="create_game",
)
def create_game(payload: CreateGameRequest, db: Session = Depends(get_db)) -> GameResponse:
    """Create a game initialized to the standard starting position."""
    _require_user_if_provided(db, payload.white_user_id)
    _require_user_if_provided(db, payload.black_user_id)

    game = Game(
        white_user_id=payload.white_user_id,
        black_user_id=payload.black_user_id,
        fen="startpos",
        status="active",
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return _serialize_game(game)


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[GameResponse],
    summary="List games (optionally filtered by user)",
    description="List games. If userId is provided, returns games where the user is white or black.",
    operation_id="list_games",
)
def list_games(
    userId: Optional[str] = Query(None, description="Filter games by participant userId."),
    db: Session = Depends(get_db),
) -> List[GameResponse]:
    """List games with an optional user filter."""
    stmt = select(Game).order_by(Game.updated_at.desc())
    if userId:
        stmt = stmt.where(or_(Game.white_user_id == userId, Game.black_user_id == userId))
    games = db.execute(stmt).scalars().unique().all()

    # Eagerly load moves for consistent API output
    for g in games:
        _ = g.moves

    return [_serialize_game(g) for g in games]


# PUBLIC_INTERFACE
@router.get(
    "/{game_id}",
    response_model=GameResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a game by ID",
    description="Fetch a game including current state and move history.",
    operation_id="get_game",
)
def get_game(game_id: str, db: Session = Depends(get_db)) -> GameResponse:
    """Fetch a game by ID."""
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")
    _ = game.moves
    return _serialize_game(game)


# PUBLIC_INTERFACE
@router.post(
    "/{game_id}/moves",
    response_model=GameResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Submit a move",
    description="Submit a chess move (SAN or UCI). The move is validated and applied if legal.",
    operation_id="submit_move",
)
def submit_move(game_id: str, payload: SubmitMoveRequest, db: Session = Depends(get_db)) -> GameResponse:
    """Validate and apply a move to a game, persisting the result and move history."""
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")

    if game.status != "active":
        raise HTTPException(status_code=400, detail=f"Game is not active (status={game.status}).")

    _ = game.moves
    move_number = len(game.moves) + 1

    try:
        result = apply_move(game.fen, uci=payload.uci, san=payload.san)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    move = Move(
        game_id=game.id,
        move_number=move_number,
        uci=result.uci,
        san=result.san,
        fen_before=result.fen_before,
        fen_after=result.fen_after,
    )

    game.fen = result.fen_after
    game.status = result.status

    db.add(move)
    db.commit()
    db.refresh(game)

    # Reload move relationship for response
    _ = game.moves
    return _serialize_game(game)


# PUBLIC_INTERFACE
@router.post(
    "/{game_id}/save",
    response_model=SnapshotResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Save a named snapshot",
    description="Save the current game state (FEN + move_count) as a named snapshot. Upserts by name.",
    operation_id="save_game_snapshot",
)
def save_game_snapshot(game_id: str, payload: SaveGameRequest, db: Session = Depends(get_db)) -> SnapshotResponse:
    """Save the current game state into a snapshot that can be restored later."""
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")
    _ = game.moves

    stmt = select(GameSnapshot).where(GameSnapshot.game_id == game_id, GameSnapshot.name == payload.name)
    existing = db.execute(stmt).scalars().first()

    if existing:
        existing.fen = game.fen
        existing.move_count = len(game.moves)
        snapshot = existing
    else:
        snapshot = GameSnapshot(
            game_id=game.id,
            name=payload.name,
            fen=game.fen,
            move_count=len(game.moves),
        )
        db.add(snapshot)

    db.commit()
    db.refresh(snapshot)
    return SnapshotResponse(
        id=snapshot.id,
        game_id=snapshot.game_id,
        name=snapshot.name,
        fen=snapshot.fen,
        move_count=snapshot.move_count,
        created_at=snapshot.created_at,
    )


# PUBLIC_INTERFACE
@router.post(
    "/{game_id}/load",
    response_model=GameResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Load a named snapshot",
    description="Restore game state from a named snapshot. Moves after snapshot move_count are discarded.",
    operation_id="load_game_snapshot",
)
def load_game_snapshot(game_id: str, payload: LoadGameRequest, db: Session = Depends(get_db)) -> GameResponse:
    """Load a snapshot by name and restore game state and move history accordingly."""
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")

    stmt = select(GameSnapshot).where(GameSnapshot.game_id == game_id, GameSnapshot.name == payload.name)
    snapshot = db.execute(stmt).scalars().first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found.")

    # Validate snapshot FEN is parseable
    try:
        if snapshot.fen == "startpos":
            _ = chess.Board()
        else:
            _ = chess.Board(snapshot.fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Snapshot FEN is invalid.") from e

    # Delete moves beyond snapshot move_count
    if snapshot.move_count >= 0:
        delete_stmt = delete(Move).where(Move.game_id == game_id, Move.move_number > snapshot.move_count)
        db.execute(delete_stmt)

    # Restore game to snapshot FEN and set status back to active (or derive from snapshot position)
    game.fen = snapshot.fen
    # Derive status from snapshot position to keep consistent
    try:
        from src.chess_logic import apply_move as _apply_move  # noqa: F401  # not used directly
        # reuse internal status logic by constructing board
        board = chess.Board() if snapshot.fen == "startpos" else chess.Board(snapshot.fen)
        if board.is_checkmate():
            game.status = "checkmate"
        elif board.is_stalemate():
            game.status = "stalemate"
        elif board.is_insufficient_material() or board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
            game.status = "draw"
        else:
            game.status = "active"
    except Exception:
        game.status = "active"

    db.commit()
    db.refresh(game)
    _ = game.moves
    return _serialize_game(game)


# PUBLIC_INTERFACE
@router.delete(
    "/{game_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a game (optional)",
    description="Delete a game and its moves/snapshots.",
    operation_id="delete_game",
)
def delete_game(game_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a game and related records."""
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")
    db.delete(game)
    db.commit()
    return None
