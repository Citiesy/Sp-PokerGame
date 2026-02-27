import secrets
from ai_player import AIPlayer

SUITS = ['diamond', 'club', 'heart', 'spade']
RANKS = ['3','4','5','6','7','8','9','10','J','Q','K','A','2']
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}


def rank_value(r):
    return RANK_ORDER[r]

def card_sort_key(c):
    return (RANK_ORDER[c[1]], SUITS.index(c[0]))

def classify_hand(cards):
    if not cards:
        return None, -1
    n = len(cards)
    ranks = [c[1] for c in cards]
    values = sorted([rank_value(r) for r in ranks])

    if n == 1:
        return 'single', values[0]
    if n == 2 and ranks[0] == ranks[1]:
        return 'pair', values[0]

    if n == 4 and len(set(ranks)) == 1:
        return 'bomb', values[0]

    if n >= 3 and _is_straight(values):
        return 'straight', max(values)

    if n >= 4 and n % 2 == 0 and _is_consecutive_pairs(cards):
        return 'consecutive_pairs', max(values)

    if n == 3 and len(set(ranks)) == 1:
        return 'triple', values[0]

    if n == 5:
        rc = {}
        for r in ranks:
            rc[r] = rc.get(r, 0) + 1
        counts = sorted(rc.values(), reverse=True)
        if counts[0] >= 3:
            triple_rank = [r for r, c in rc.items() if c >= 3][0]
            return 'triple_two', rank_value(triple_rank)

    ap = _check_airplane(cards)
    if ap:
        return ap

    return None, -1

def _is_straight(values):
    s = sorted(set(values))
    if len(s) != len(values):
        return False
    if len(s) < 3:
        return False
    return s[-1] - s[0] == len(s) - 1

def _is_consecutive_pairs(cards):
    rc = {}
    for s, r in cards:
        rc[r] = rc.get(r, 0) + 1
    if len(rc) < 2:
        return False
    if not all(c == 2 for c in rc.values()):
        return False
    vals = sorted([rank_value(r) for r in rc])
    return vals[-1] - vals[0] == len(vals) - 1

def _check_airplane(cards):
    rc = {}
    for s, r in cards:
        rc[r] = rc.get(r, 0) + 1
    triples = sorted([r for r, c in rc.items() if c >= 3], key=lambda x: rank_value(x))
    if len(triples) < 2:
        return None
    for length in range(len(triples), 1, -1):
        for start in range(len(triples) - length + 1):
            group = triples[start:start+length]
            vals = [rank_value(r) for r in group]
            if max(vals) - min(vals) == length - 1:
                used = sum(3 for _ in group)
                remaining = len(cards) - used
                if remaining == 0:
                    return 'airplane_pure', max(vals)
                if remaining == length * 2:
                    return 'airplane', max(vals)
    return None

def can_beat(last_type, last_value, last_count, new_type, new_value, new_count):
    if new_type == 'bomb':
        if last_type == 'bomb':
            return new_value > last_value
        return True
    if last_type == 'bomb':
        return False
    if new_type != last_type:
        return False
    if new_count != last_count:
        return False
    return new_value > last_value


class Game:
    def __init__(self):
        self.players = [[] for _ in range(4)]
        self.current_player = 0
        self.current_player_before = 0
        self.last_play = None
        self.last_play_player = None
        self.last_play_type = None
        self.last_play_value = -1
        self.last_play_count = 0
        self.pass_count = 0
        self.winner = None
        self.ai = AIPlayer()
        self.history = []
        self.first_turn = True

    def deal(self):
        deck = [(s, r) for s in SUITS for r in RANKS]

        # 使用系统随机源进行多轮 Fisher-Yates 洗牌
        for _ in range(4):
            for i in range(len(deck) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                deck[i], deck[j] = deck[j], deck[i]

        # 随机切牌 + 随机翻转，进一步打散位置相关性
        cut = secrets.randbelow(len(deck))
        deck = deck[cut:] + deck[:cut]
        if secrets.randbelow(2) == 1:
            deck.reverse()

        # 再执行少量随机互换，降低残余结构
        for _ in range(12):
            a = secrets.randbelow(len(deck))
            b = secrets.randbelow(len(deck))
            deck[a], deck[b] = deck[b], deck[a]

        for i in range(4):
            self.players[i] = sorted(deck[i*13:(i+1)*13], key=card_sort_key)
        for i in range(4):
            if ('diamond', '3') in self.players[i]:
                self.current_player = i
                break
        self.first_turn = True

    def get_state_for_player(self, pid):
        return {
            'hand': [list(c) for c in self.players[pid]],
            'current_player': self.current_player,
            'last_play': [list(c) for c in self.last_play] if self.last_play else None,
            'last_play_player': self.last_play_player,
            'other_counts': [len(self.players[i]) for i in range(4)],
            'winner': self.winner,
            'history': self.history[-20:],
            'is_free': self.last_play_player is None or self.last_play_player == self.current_player,
            'first_turn': self.first_turn
        }

    def play_cards(self, pid, cards):
        if self.winner is not None:
            return False, '游戏已结束'
        if pid != self.current_player:
            return False, '不是你的回合'
        if not cards:
            return self.pass_turn(pid)

        if self.first_turn:
            if not any(c[0]=='diamond' and c[1]=='3' for c in cards):
                return False, '第一手必须包含方块3'

        for card in cards:
            if tuple(card) not in self.players[pid]:
                return False, '你没有这些牌'

        htype, hvalue = classify_hand(cards)
        if htype is None:
            return False, '无效的牌型'

        is_free = self.last_play_player is None or self.last_play_player == pid
        if not is_free:
            if not can_beat(self.last_play_type, self.last_play_value, self.last_play_count, htype, hvalue, len(cards)):
                return False, '出牌不够大'

        for card in cards:
            self.players[pid].remove(tuple(card))

        self.last_play = list(cards)
        self.last_play_player = pid
        self.last_play_type = htype
        self.last_play_value = hvalue
        self.last_play_count = len(cards)
        self.pass_count = 0
        self.first_turn = False
        self.history.append({'player': pid, 'cards': [list(c) for c in cards], 'action': 'play'})

        # 先记录当前玩家，再检查胜利，修复赢家显示错位Bug
        self.current_player_before = self.current_player

        if not self.players[pid]:
            self.winner = pid
            return True, 'ok'

        self.current_player = (self.current_player + 1) % 4
        return True, 'ok'

    def pass_turn(self, pid):
        if self.winner is not None:
            return False, '游戏已结束'
        if pid != self.current_player:
            return False, '不是你的回合'
        is_free = self.last_play_player is None or self.last_play_player == pid
        if is_free:
            return False, '自由出牌必须出'
        if self.first_turn:
            return False, '第一手必须出牌'

        self.pass_count += 1
        self.history.append({'player': pid, 'cards': [], 'action': 'pass'})
        self.current_player_before = self.current_player
        self.current_player = (self.current_player + 1) % 4

        if self.pass_count >= 3:
            self.last_play = None
            self.last_play_player = None
            self.last_play_type = None
            self.last_play_value = -1
            self.last_play_count = 0
            self.pass_count = 0
        return True, 'ok'

    def ai_play(self, pid):
        is_free = self.last_play_player is None or self.last_play_player == pid
        thinking, cards = self.ai.decide(
            hand=self.players[pid],
            last_type=self.last_play_type,
            last_value=self.last_play_value,
            last_count=self.last_play_count,
            is_free=is_free,
            first_turn=self.first_turn,
            other_counts=[len(self.players[i]) for i in range(4)],
            player_idx=pid,
            history=self.history
        )
        if cards:
            self.play_cards(pid, [tuple(c) for c in cards])
        else:
            self.pass_turn(pid)
        return thinking, cards