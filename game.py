import random
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from database import Database
from config import Config

@dataclass
class Card:
    suit: str
    rank: str
    value: int

    def __str__(self):
        suit_symbols = {'hearts': '♥️', 'diamonds': '♦️', 'clubs': '♣️', 'spades': '♠️'}
        return f"{self.rank}{suit_symbols[self.suit]}"

class Deck:
    def __init__(self):
        self.cards: List[Card] = []
        self._create_deck()
        self.shuffle()

    def _create_deck(self):
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}
        for suit in suits:
            for rank, value in ranks.items():
                self.cards.append(Card(suit, rank, value))

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            raise ValueError("Deck is empty")
        return self.cards.pop()


@dataclass
class Player:
    user_id: int
    username: str
    cards: List[Card] = field(default_factory=list)
    score: int = 0
    status: str = 'active' 
    balance: int = 0
    bet: int = 0
    has_hit: bool = False

    def add_card(self, card: Card):
        self.cards.append(card)
        self._calculate_score()

    def initialize_balance(self, db: 'Database'):
        if self.balance == 0:
            self.balance = db.get_user_balance(self.user_id)

    def place_bet(self, amount: int) -> bool:
        if amount < 10 or amount > self.balance:
            return False
        self.bet = amount
        self.balance -= amount
        return True

    def adjust_bet(self, new_amount: int) -> bool:
        if new_amount < 10 or new_amount > (self.balance + self.bet):
            return False
        difference = new_amount - self.bet
        self.balance -= difference
        self.bet = new_amount
        return True

    def clear_bet(self):
        self.bet = 0

    def add_winnings(self, amount: int):
        self.balance += amount

    def _calculate_score(self):
        self.score = 0
        aces = 0
        for card in self.cards:
            if card.rank == 'A':
                aces += 1
                self.score += 11
            else:
                self.score += card.value

        while self.score > 21 and aces:
            self.score -= 10
            aces -= 1

        if self.score > 21:
            self.status = 'bust'

    def __str__(self):
        cards_str = ' '.join(str(card) for card in self.cards)
        return f"@{self.username} — [{cards_str}] — {self.score} (Баланс: {self.balance} 💰, Ставка: {self.bet})"

class Game:
    def __init__(self, creator_id: int, chat_id: int):
        self.game_id = str(uuid.uuid4())
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.players: List[Player] = []
        self.dealer = Player(-1, 'Dealer')
        self.deck = Deck()
        self.current_player_index = 0
        self.status = 'waiting' 
        self.current_betting_player_index = 0
        self.message_id: Optional[int] = None

    def add_player(self, user_id: int, username: str, db: 'Database') -> bool:
        if len(self.players) >= Config.MAX_PLAYERS:
            return False
        if any(p.user_id == user_id for p in self.players):
            return False
        player = Player(user_id, username)
        player.initialize_balance(db)
        db.save_username(user_id, username)
        self.players.append(player)
        return True

    def start_game(self, db: 'Database') -> bool:
        if len(self.players) < 2 or self.creator_id != self.players[0].user_id:
            return False
        self.status = 'betting'
        self.current_betting_player_index = 0
        for player in self.players:
            player.initialize_balance(db)
            player.adjust_bet(10) 
        return True

    def place_bet(self, user_id: int, amount: int) -> bool:
        if self.status != 'betting':
            return False
        if self.current_betting_player_index >= len(self.players):
            return False
        player = self.players[self.current_betting_player_index]
        if player.user_id != user_id:
            return False
        if amount < 10 or amount > player.balance:
            return False
        player.place_bet(amount)
        self.current_betting_player_index += 1
        if self.current_betting_player_index >= len(self.players):
            self._deal_cards()
        return True

    def _deal_cards(self):
        self.status = 'playing'
        self.current_player_index = 0
        self.deck = Deck()
        for player in self.players:
            player.cards.clear()
            player.score = 0
            player.status = 'active'
            player.has_hit = False
        self.dealer = Player(-1, 'Dealer')
        for _ in range(2):
            for player in self.players:
                player.add_card(self.deck.draw())
        self.dealer.add_card(self.deck.draw())
        self.dealer.add_card(self.deck.draw())

    def player_hit(self, user_id: int) -> bool:
        if self.status != 'playing':
            return False
        player = self._get_current_player()
        if player.user_id != user_id:
            return False
        player.has_hit = True
        player.add_card(self.deck.draw())
        if player.status == 'bust':
            self._next_player()
        return True

    def player_stand(self, user_id: int) -> bool:
        if self.status != 'playing':
            return False
        player = self._get_current_player()
        if player.user_id != user_id:
            return False
        player.status = 'stand'
        self._next_player()
        return True

    def _next_player(self):
        self.current_player_index += 1
        if self.current_player_index >= len(self.players):
            self._dealer_turn()

    def _dealer_turn(self):
        self.dealer._calculate_score()
        while self.dealer.score < 17:
            self.dealer.add_card(self.deck.draw())
        self._end_game()

    def _end_game(self):
        self.status = 'finished'
        dealer_score = self.dealer.score
        total_losing_bets = sum(p.bet for p in self.players if p.status in ['lose', 'bust'])
        for player in self.players:
            if player.score > 21:
                player.status = 'lose'
            elif dealer_score > 21:
                player.status = 'win'
            elif player.score > dealer_score:
                player.status = 'win'
            elif player.score == dealer_score:
                player.status = 'tie'
            else:
                player.status = 'lose'

        for player in self.players:
            if player.status == 'win':
                winnings = player.bet * 2
                winnings += int(total_losing_bets * 0.2)
                player.add_winnings(winnings)
            elif player.status in ['lose', 'bust']:
                pass
            elif player.status == 'tie':
                player.add_winnings(player.bet)


    def _get_current_player(self) -> Player:
        if self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        return self.players[-1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'game_id': self.game_id,
            'chat_id': self.chat_id,
            'creator_id': self.creator_id,
            'players': [{'user_id': p.user_id, 'username': p.username, 'cards': [(c.suit, c.rank, c.value) for c in p.cards], 'score': p.score, 'status': p.status, 'balance': p.balance, 'bet': p.bet, 'has_hit': p.has_hit} for p in self.players],
            'dealer_cards': [(c.suit, c.rank, c.value) for c in self.dealer.cards],
            'dealer_score': self.dealer.score,
            'current_player_index': self.current_player_index,
            'current_betting_player_index': self.current_betting_player_index,
            'status': self.status,
            'message_id': self.message_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Game':
        game = cls(data['creator_id'], data['chat_id'])
        game.game_id = data['game_id']
        game.players = [Player(p['user_id'], p['username']) for p in data['players']]
        for i, p_data in enumerate(data['players']):
            game.players[i].cards = [Card(c[0], c[1], c[2]) for c in p_data['cards']]
            game.players[i].score = p_data['score']
            game.players[i].status = p_data['status']
            game.players[i].balance = p_data.get('balance', 0)
            game.players[i].bet = p_data.get('bet', 0)
            game.players[i].has_hit = p_data.get('has_hit', False)
        game.dealer.cards = [Card(c[0], c[1], c[2]) for c in data['dealer_cards']]
        game.dealer.score = data['dealer_score']
        game.current_player_index = data['current_player_index']
        game.current_betting_player_index = data.get('current_betting_player_index', 0)
        game.status = data['status']
        game.message_id = data.get('message_id')
        return game

class GameManager:
    def __init__(self):
        self.db = Database()
        self.active_games: Dict[str, Game] = {}

    def create_game(self, creator_id: int, chat_id: int) -> Game:
        game = Game(creator_id, chat_id)
        self.active_games[game.game_id] = game
        self.db.save_game(game.game_id, chat_id, creator_id, game.to_dict())
        return game

    def add_player_to_game(self, game_id: str, user_id: int, username: str) -> bool:
        game = self.get_game(game_id)
        if not game:
            return False
        success = game.add_player(user_id, username, self.db)
        if success:
            self.save_game(game)
        return success

    def start_game(self, game_id: str) -> bool:
        game = self.get_game(game_id)
        if not game:
            return False
        success = game.start_game(self.db)
        if success:
            self.save_game(game)
        return success

    def get_game(self, game_id: str) -> Optional[Game]:
        if game_id in self.active_games:
            return self.active_games[game_id]
        game_data = self.db.load_game(game_id)
        if game_data:
            game = Game.from_dict(game_data)
            self.active_games[game_id] = game
            return game
        return None

    def save_game(self, game: Game):
        self.db.save_game(game.game_id, game.chat_id, game.creator_id, game.to_dict())

    def delete_game(self, game_id: str):
        if game_id in self.active_games:
            del self.active_games[game_id]
        self.db.delete_game(game_id)

    def save_balances_after_game(self, game: Game):
        for player in game.players:
            self.db.save_user_balance(player.user_id, player.balance)
            stats = self.db.get_user_stats(player.user_id)
            total_wins = stats['total_wins']
            max_bet = stats['max_bet']
            max_consecutive_wins = stats['max_consecutive_wins']
            current_consecutive_wins = stats['current_consecutive_wins']
            if player.status == 'win':
                total_wins += 1
                current_consecutive_wins += 1
                if current_consecutive_wins > max_consecutive_wins:
                    max_consecutive_wins = current_consecutive_wins
            else:
                current_consecutive_wins = 0
            if player.bet > max_bet:
                max_bet = player.bet
            self.db.save_user_stats(player.user_id, total_wins, max_bet, max_consecutive_wins, current_consecutive_wins)

    def get_games_in_chat(self, chat_id: int) -> List[Game]:
        game_ids = self.db.get_games_by_chat(chat_id)
        games = []
        for game_id in game_ids:
            game = self.get_game(game_id)
            if game:
                games.append(game)
        return games

    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        return self.db.get_user_stats(user_id)
