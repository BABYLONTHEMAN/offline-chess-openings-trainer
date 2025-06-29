import json
import tkinter as tk
from tkinter import ttk
import chess

# Unicode glyphs for pieces
UNICODE_PIECES = {
    chess.PAWN:   ('♙', '♟'),
    chess.KNIGHT: ('♘', '♞'),
    chess.BISHOP: ('♗', '♝'),
    chess.ROOK:   ('♖', '♜'),
    chess.QUEEN:  ('♕', '♛'),
    chess.KING:   ('♔', '♚'),
}

class OpeningTrainer(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg="#16182a")
        self.master = master
        self.master.title("Offline Chess Opening Trainer")
        self.pack(fill="both", expand=True)

        # Load opening book
        self.position_book = self.load_book("openings.json")

        # Chess state
        self.board = chess.Board()
        self.history = []

        # UI setup
        self.create_widgets()
        self.render_board()
        self.show_position_book()

    def load_book(self, path):
        """Load openings.json into a dict mapping FEN→{origins,next_moves}."""
        with open(path) as f:
            openings = json.load(f)

        book = {}
        for o in openings:
            g = chess.Board()
            toks = o["moves"].split()
            for i, san in enumerate(toks):
                try:
                    g.push_san(san)
                except ValueError:
                    break
                fen = g.fen()
                entry = book.setdefault(fen, {"origins": [], "next_moves": []})
                entry["origins"].append({
                    "eco": o["eco"],
                    "name": o["name"],
                    "moves": " ".join(toks[:i+1])
                })
                if i+1 < len(toks):
                    nxt = toks[i+1]
                    if nxt not in entry["next_moves"]:
                        entry["next_moves"].append(nxt)
        return book

    def create_widgets(self):
        # Title
        ttk.Style().configure(
            "TLabel",
            background="#16182a",
            foreground="#ffc843",
            font=("Sans", 16)
        )
        tk.Label(
            self,
            text="Offline Chess Opening Trainer",
            font=("Sans", 20, "bold"),
            background="#16182a",
            foreground="#ffc843"
        ).pack(pady=(10, 5))

        # Reset button
        tk.Button(
            self,
            text="Reset Board",
            command=self.reset_position,
            bg="#ffc843",
            fg="#222",
            relief="flat",
            padx=6,
            pady=2
        ).pack(pady=(0, 10))

        # Info panel
        self.info = tk.Text(
            self, width=40, height=5,
            bg="#232c43", fg="white",
            bd=0, wrap="word"
        )
        self.info.pack(pady=5, padx=10, fill="x")

        # Board frame
        board_frame = tk.Frame(self, bg="#444")
        board_frame.pack(padx=10, pady=10)
        self.squares = {}
        for r in range(8):
            for c in range(8):
                sq_name = chess.square_name(chess.square(c, 7-r))
                color = "#f7e5c3" if (r+c) % 2 == 0 else "#725a40"
                lbl = tk.Label(
                    board_frame, text="", font=("Sans", 24),
                    width=2, height=1, bg=color, fg="#000",
                    borderwidth=1, relief="flat"
                )
                lbl.grid(row=r, column=c, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, sq=sq_name: self.on_click(sq))
                self.squares[sq_name] = lbl

        # Next-move buttons
        self.moves_frame = tk.Frame(self, bg="#16182a")
        self.moves_frame.pack(pady=5)

    def reset_position(self):
        """Reset to the starting position."""
        self.board = chess.Board()
        self.history = []
        if hasattr(self, "selected"):
            self.clear_selection()
        self.render_board()
        self.show_position_book()

    def render_board(self):
        """Draw the board from the current self.board position."""
        for sq, lbl in self.squares.items():
            piece = self.board.piece_at(chess.parse_square(sq))
            if piece:
                glyph = UNICODE_PIECES[piece.piece_type][
                    0 if piece.color == chess.WHITE else 1
                ]
                lbl.config(text=glyph)
            else:
                lbl.config(text="")

    def on_click(self, sq):
        """Handle a click on square `sq` (e.g. 'e4')."""
        # Deselect if clicking same square twice
        if hasattr(self, "selected") and self.selected == sq:
            self.clear_selection()
            return

        # If a square is already selected, try to move there
        if hasattr(self, "selected"):
            uci_move = f"{self.selected}{sq}"
            move = chess.Move.from_uci(uci_move)
            if move in self.board.legal_moves:
                san = self.board.san(move)        # compute SAN before pushing
                self.board.push(move)
                self.history.append(san)
                self.clear_selection()
                self.render_board()
                self.show_position_book()
            else:
                self.clear_selection()
            return

        # No selection yet: select if there's a piece of the right color
        pc = self.board.piece_at(chess.parse_square(sq))
        if pc and pc.color == self.board.turn:
            self.selected = sq
            self.squares[sq].config(
                relief="solid",
                highlightbackground="#00ffa3",
                highlightthickness=3
            )

    def clear_selection(self):
        if hasattr(self, "selected"):
            lbl = self.squares[self.selected]
            lbl.config(relief="flat", highlightthickness=0)
            del self.selected

    def show_position_book(self):
        """Update info panel and next-move buttons based on current FEN."""
        fen = self.board.fen()
        entry = self.position_book.get(fen, {})
        origins = entry.get("origins", [])
        next_moves = entry.get("next_moves", [])

        self.info.config(state="normal")
        self.info.delete("1.0", "end")
        if origins:
            for o in origins:
                self.info.insert(
                    "end",
                    f"{o['moves']} → {o['name']} ({o['eco']})\n",
                    "movesofar"
                )
        else:
            self.info.insert("end", "No book lines from here.\n")
        self.info.config(state="disabled")

        # Rebuild next-move buttons
        for w in self.moves_frame.winfo_children():
            w.destroy()
        for mv in next_moves:
            b = tk.Button(
                self.moves_frame,
                text=mv,
                command=lambda m=mv: self.apply_book_move(m),
                bg="#ffc843",
                fg="#222",
                relief="flat",
                padx=6,
                pady=2
            )
            b.pack(side="left", padx=4)

    def apply_book_move(self, san):
        """Push SAN move from book and refresh."""
        try:
            self.board.push_san(san)
        except ValueError:
            return
        self.history.append(san)
        self.render_board()
        self.show_position_book()

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    style.configure("movesofar.TLabel", background="#ffc843", foreground="#222")
    app = OpeningTrainer(root)
    root.mainloop()
