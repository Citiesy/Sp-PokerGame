from flask import Flask, render_template, jsonify, request
from game_logic import Game, classify_hand
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
games = {}

NAMES = ['玩家', '电脑B', '电脑C', '电脑D']

TYPE_NAMES = {
    'single': '单张',
    'pair': '对子',
    'triple': '三条',
    'triple_two': '三带二',
    'straight': '顺子',
    'consecutive_pairs': '连对',
    'bomb': '炸弹',
    'airplane': '飞机',
    'airplane_pure': '飞机',
}

def print_thinking(player_idx, thinking):
    name = NAMES[player_idx]
    print(f"\n{'='*40}")
    print(f"  {name} 的思考过程")
    print(f"{'='*40}")
    for line in thinking:
        print(f"  > {line}")
    print(f"{'='*40}\n")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/new_game', methods=['POST'])
def new_game():
    game = Game()
    game.deal()
    game_id = os.urandom(8).hex()
    games[game_id] = game

    starter = game.current_player
    print(f"\n{'#'*50}")
    print(f"  新游戏开始! 方块3在 {NAMES[starter]} 手中")
    print(f"{'#'*50}")

    ai_actions = []
    while game.current_player != 0 and game.winner is None:
        thinking, ai_cards = game.ai_play(game.current_player)
        ai_player = game.current_player_before
        print_thinking(ai_player, thinking)
        htype = None
        if ai_cards:
            htype, _ = classify_hand(ai_cards)
        ai_actions.append({
            'player': ai_player,
            'cards': [list(c) for c in ai_cards] if ai_cards else [],
            'action': 'play' if ai_cards else 'pass',
            'hand_type': htype,
            'other_counts': [len(game.players[i]) for i in range(4)]
        })

    state = game.get_state_for_player(0)
    state['game_id'] = game_id
    state['ai_actions'] = ai_actions
    return jsonify(state)

@app.route('/api/play', methods=['POST'])
def play():
    data = request.get_json()
    game_id = data.get('game_id')
    cards = [tuple(c) for c in data.get('cards', [])]

    if game_id not in games:
        return jsonify({'error': '游戏不存在'}), 400
    game = games[game_id]
    if game.current_player != 0:
        return jsonify({'error': '不是你的回合'}), 400

    success, msg = game.play_cards(0, cards)
    if not success:
        return jsonify({'error': msg}), 400

    desc = ' '.join(c[1] for c in cards)
    print(f"\n  [玩家] 出牌: {desc}")

    result = {
        'player_action': {'player': 0, 'cards': [list(c) for c in cards], 'action': 'play'},
        'ai_actions': []
    }

    if game.winner is not None:
        result['winner'] = game.winner
        result['state'] = game.get_state_for_player(0)
        result['state']['game_id'] = game_id
        print(f"\n  *** {NAMES[game.winner]} 获胜! ***\n")
        return jsonify(result)

    while game.current_player != 0 and game.winner is None:
        thinking, ai_cards = game.ai_play(game.current_player)
        ai_player = game.current_player_before
        print_thinking(ai_player, thinking)
        htype = None
        if ai_cards:
            htype, _ = classify_hand(ai_cards)
        result['ai_actions'].append({
            'player': ai_player,
            'cards': [list(c) for c in ai_cards] if ai_cards else [],
            'action': 'play' if ai_cards else 'pass',
            'hand_type': htype,
            'other_counts': [len(game.players[i]) for i in range(4)]
        })
        if game.winner is not None:
            result['winner'] = game.winner
            print(f"\n  *** {NAMES[game.winner]} 获胜! ***\n")
            break

    state = game.get_state_for_player(0)
    state['game_id'] = game_id
    result['state'] = state
    return jsonify(result)

@app.route('/api/pass_turn', methods=['POST'])
def pass_turn():
    data = request.get_json()
    game_id = data.get('game_id')

    if game_id not in games:
        return jsonify({'error': '游戏不存在'}), 400
    game = games[game_id]
    if game.current_player != 0:
        return jsonify({'error': '不是你的回合'}), 400

    success, msg = game.pass_turn(0)
    if not success:
        return jsonify({'error': msg}), 400

    print(f"\n  [玩家] 不出")

    result = {'player_action': {'player': 0, 'cards': [], 'action': 'pass'}, 'ai_actions': []}

    while game.current_player != 0 and game.winner is None:
        thinking, ai_cards = game.ai_play(game.current_player)
        ai_player = game.current_player_before
        print_thinking(ai_player, thinking)
        htype = None
        if ai_cards:
            htype, _ = classify_hand(ai_cards)
        result['ai_actions'].append({
            'player': ai_player,
            'cards': [list(c) for c in ai_cards] if ai_cards else [],
            'action': 'play' if ai_cards else 'pass',
            'hand_type': htype,
            'other_counts': [len(game.players[i]) for i in range(4)]
        })
        if game.winner is not None:
            result['winner'] = game.winner
            print(f"\n  *** {NAMES[game.winner]} 获胜! ***\n")
            break

    state = game.get_state_for_player(0)
    state['game_id'] = game_id
    result['state'] = state
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)