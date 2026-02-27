"""
智能AI扑克玩家
策略:
  1. 手牌拆解: 将手牌分解为最优组合(少拆对/三条)
  2. 出牌选择: 优先出长牌型消耗手牌，保留炸弹做关键压制
  3. 对手感知: 根据对手剩余牌数动态调整攻防
  4. 单牌不拆对: 出单张时优先出孤张，不拆对子
  5. 尾牌加速: 手牌少时主动出大牌抢控制权
"""

SUITS = ['diamond', 'club', 'heart', 'spade']
RANKS = ['3','4','5','6','7','8','9','10','J','Q','K','A','2']
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}

def rv(rank):
    return RANK_ORDER[rank]

def ck(c):
    return (RANK_ORDER[c[1]], SUITS.index(c[0]))


class AIPlayer:

    def decide(self, hand, last_type, last_value, last_count, is_free, first_turn, other_counts, player_idx):
        log = []
        hand = sorted(hand, key=ck)
        groups = self._group(hand)
        log.append(f"手牌({len(hand)}): {' '.join(c[1] for c in hand)}")

        min_enemy = min(other_counts[i] for i in range(4) if i != player_idx)
        log.append(f"对手最少牌数: {min_enemy}")

        if is_free:
            result = self._free_play(hand, groups, first_turn, min_enemy, log)
        else:
            result = self._response_play(hand, groups, last_type, last_value, last_count, min_enemy, log)

        if result:
            log.append(f"决策 -> 出: {' '.join(c[1] for c in result)}")
        else:
            log.append(f"决策 -> 不出")
        return log, result

    # ========== 自由出牌 ==========

    def _free_play(self, hand, groups, first_turn, min_enemy, log):
        if first_turn:
            return self._first_turn_play(hand, groups, log)

        decomp = self._decompose(hand, groups, log)
        urgent = min_enemy <= 2

        kill_shot = self._find_kill_shot(hand)
        if kill_shot:
            log.append("发现一手出完机会")
            return kill_shot

        # 手牌<=2张直接全出(如果合法)
        if len(hand) <= 2:
            from game_logic import classify_hand
            t, v = classify_hand(hand)
            if t:
                log.append("手牌很少，直接全出")
                return list(hand)

        # 紧急: 对手快赢了，出炸弹或最大的牌抢控制
        if urgent:
            log.append("对手快赢了! 紧急出牌")
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("用炸弹压制")
                return list(bombs[-1])

        # 手牌结构过碎时，优先减少孤张，避免后续被卡单
        if decomp['singles'] >= 4 and decomp['pairs'] <= 1:
            singles = self._get_smart_singles(hand, groups)
            if singles:
                log.append(f"手牌偏碎，先走单张{singles[0][1]}")
                return [singles[0]]

        # 策略优先级: 飞机 > 顺子 > 连对 > 三带二 > 对子 > 单张
        # 优先出张数多的组合来快速减手牌

        # 飞机
        air = self._find_airplanes(hand)
        if air:
            air.sort(key=lambda a: -len(a))
            log.append("出飞机(大组合优先)")
            return list(air[0])

        # 顺子
        straights = self._find_straights(hand)
        if straights:
            straights.sort(key=lambda s: (-len(s), min(rv(c[1]) for c in s)))
            log.append("出顺子(最长优先)")
            return list(straights[0])

        # 连对
        cp = self._find_consecutive_pairs(hand)
        if cp:
            cp.sort(key=lambda x: -len(x))
            log.append("出连对")
            return list(cp[0])

        # 三带二
        t2 = self._find_triple_twos(hand, groups)
        if t2:
            # 出最小的三条
            t2.sort(key=lambda t: self._triple_rank(t))
            log.append("出三带二(最小三条)")
            return list(t2[0])

        # 对子 - 出最小的
        pairs = self._find_pairs_no_break(groups)
        if pairs:
            pairs.sort(key=lambda p: rv(p[0][1]))
            # 不出对2除非快赢了
            for p in pairs:
                if rv(p[0][1]) < 12 or len(hand) <= 4:
                    log.append(f"出对子{p[0][1]}")
                    return list(p)
            log.append(f"出对子{pairs[0][0][1]}")
            return list(pairs[0])

        # 单张 - 出孤张最小的，不拆对
        singles = self._get_smart_singles(hand, groups)
        if singles:
            log.append(f"出单张{singles[0][1]}(不拆对)")
            return [singles[0]]

        # 兜底
        log.append("兜底出最小牌")
        return [hand[0]]

    def _first_turn_play(self, hand, groups, log):
        d3 = ('diamond', '3')
        log.append("首轮必须含方块3")

        # 尝试顺子含d3
        for s in self._find_straights(hand):
            if d3 in s:
                log.append(f"顺子含方块3, 长度{len(s)}")
                return list(s)

        # 连对含d3
        for cp in self._find_consecutive_pairs(hand):
            if d3 in cp:
                log.append("连对含方块3")
                return list(cp)

        # 三带二含d3
        for t in self._find_triple_twos(hand, groups):
            if d3 in t:
                log.append("三带二含方块3")
                return list(t)

        # 对子含d3
        if '3' in groups and len(groups['3']) >= 2:
            log.append("对3含方块3")
            return list(groups['3'][:2])

        log.append("只出方块3")
        return [d3]

    # ========== 跟牌 ==========

    def _response_play(self, hand, groups, lt, lv, lc, min_enemy, log):
        urgent = min_enemy <= 2
        my_count = len(hand)

        # 如果我也快赢了，激进出
        aggressive = my_count <= 4

        if lt == 'single':
            return self._resp_single(hand, groups, lv, urgent, aggressive, log)
        elif lt == 'pair':
            return self._resp_pair(hand, groups, lv, urgent, aggressive, log)
        elif lt == 'triple':
            return self._resp_triple(hand, groups, lv, urgent, log)
        elif lt == 'triple_two':
            return self._resp_triple_two(hand, groups, lv, urgent, log)
        elif lt == 'straight':
            return self._resp_straight(hand, lv, lc, urgent, log)
        elif lt == 'consecutive_pairs':
            return self._resp_consec_pairs(hand, lv, lc, urgent, log)
        elif lt == 'bomb':
            return self._resp_bomb(hand, lv, urgent, log)
        elif lt in ('airplane', 'airplane_pure'):
            return self._resp_airplane(hand, lv, lc, urgent, log)

        # 兜底: 炸弹
        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("紧急炸弹")
                return list(bombs[0])
        return None

    def _resp_single(self, hand, groups, lv, urgent, aggressive, log):
        # 优先用孤张压(不拆对子/三条)
        singles = self._get_smart_singles(hand, groups)
        cands = [c for c in singles if rv(c[1]) > lv]

        win_play = self._find_finishing_play(hand, [[c] for c in cands])
        if win_play:
            log.append(f"压单并做收尾: {win_play[0][1]}")
            return list(win_play)

        if cands:
            if urgent or aggressive:
                log.append("紧急/快赢, 出最小能压的单张")
                return [cands[0]]

            # 正常: 不浪费A和2，除非没别的选择
            safe = [c for c in cands if rv(c[1]) <= 10]  # <=K
            if safe:
                log.append(f"出孤张{safe[0][1]}(保留大牌)")
                return [safe[0]]

            # 中等大牌也可以出
            mid = [c for c in cands if rv(c[1]) <= 11]  # <=A
            if mid:
                log.append(f"出{mid[0][1]}")
                return [mid[0]]

            # 只剩2了
            if len(hand) <= 6 or urgent:
                log.append(f"牌不多了, 出{cands[0][1]}")
                return [cands[0]]

            log.append("大牌太贵, 考虑不出")
            # 但如果手牌很多还是得出
            if len(hand) >= 10:
                return [cands[0]]
            return None

        # 孤张压不了, 考虑拆对
        all_cands = sorted([c for c in hand if rv(c[1]) > lv], key=lambda c: rv(c[1]))
        if all_cands and (urgent or aggressive):
            log.append(f"拆牌出{all_cands[0][1]}(紧急)")
            return [all_cands[0]]

        # 炸弹
        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("炸弹压单张")
                return list(bombs[0])

        log.append("压不了单张")
        return None

    def _resp_pair(self, hand, groups, lv, urgent, aggressive, log):
        pairs = self._find_pairs_no_break(groups)
        cands = sorted([p for p in pairs if rv(p[0][1]) > lv], key=lambda p: rv(p[0][1]))

        win_play = self._find_finishing_play(hand, cands)
        if win_play:
            log.append(f"压对并做收尾: {win_play[0][1]}")
            return list(win_play)

        if cands:
            if urgent or aggressive:
                log.append(f"出对{cands[0][0][1]}")
                return list(cands[0])
            # 不浪费对2
            safe = [p for p in cands if rv(p[0][1]) < 12]
            if safe:
                log.append(f"出对{safe[0][0][1]}")
                return list(safe[0])
            if len(hand) <= 6:
                log.append(f"牌少, 出对{cands[0][0][1]}")
                return list(cands[0])
            log.append("对子太大, 不出")
            return None

        # 拆三条出对
        if urgent or aggressive:
            for r in sorted(groups, key=rv):
                if len(groups[r]) >= 3 and rv(r) > lv:
                    log.append(f"拆三条{r}出对(紧急)")
                    return list(groups[r][:2])

        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("炸弹压对子")
                return list(bombs[0])

        log.append("压不了对子")
        return None

    def _resp_triple(self, hand, groups, lv, urgent, log):
        triples = sorted(
            [r for r, cs in groups.items() if len(cs) >= 3 and rv(r) > lv],
            key=rv
        )
        triple_plays = [tuple(groups[r][:3]) for r in triples]
        win_play = self._find_finishing_play(hand, triple_plays)
        if win_play:
            log.append(f"压三条并做收尾: {win_play[0][1]}")
            return list(win_play)

        if triples:
            r = triples[0]
            log.append(f"出三条{r}")
            return list(groups[r][:3])

        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("炸弹压三条")
                return list(bombs[0])
        return None

    def _resp_triple_two(self, hand, groups, lv, urgent, log):
        combos = self._find_triple_twos(hand, groups)
        valid = []
        for combo in combos:
            tr = self._triple_rank(combo)
            if tr > lv:
                valid.append((tr, combo))
        valid.sort(key=lambda x: x[0])

        if valid:
            log.append(f"出三带二")
            return list(valid[0][1])

        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("炸弹压三带二")
                return list(bombs[0])
        return None

    def _resp_straight(self, hand, lv, lc, urgent, log):
        straights = self._find_straights(hand, length=lc)
        cands = sorted(
            [s for s in straights if len(s) == lc and max(rv(c[1]) for c in s) > lv],
            key=lambda s: max(rv(c[1]) for c in s)
        )
        if cands:
            log.append(f"压顺子")
            return list(cands[0])

        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("炸弹压顺子")
                return list(bombs[0])
        return None

    def _resp_consec_pairs(self, hand, lv, lc, urgent, log):
        needed = lc // 2
        cps = self._find_consecutive_pairs(hand, count=needed)
        cands = sorted(
            [cp for cp in cps if len(cp) == lc and max(rv(c[1]) for c in cp) > lv],
            key=lambda s: max(rv(c[1]) for c in s)
        )
        if cands:
            log.append("压连对")
            return list(cands[0])

        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("炸弹压连对")
                return list(bombs[0])
        return None

    def _resp_bomb(self, hand, lv, urgent, log):
        bombs = sorted(self._find_bombs(hand), key=lambda b: rv(b[0][1]))
        cands = [b for b in bombs if rv(b[0][1]) > lv]
        if cands:
            log.append("大炸弹压小炸弹")
            return list(cands[0])
        return None

    def _resp_airplane(self, hand, lv, lc, urgent, log):
        airs = self._find_airplanes(hand)
        for a in airs:
            if len(a) == lc:
                rc = {}
                for c in a:
                    rc[c[1]] = rc.get(c[1], 0) + 1
                trs = [r for r, cnt in rc.items() if cnt >= 3]
                mv = max(rv(r) for r in trs) if trs else -1
                if mv > lv:
                    log.append("压飞机")
                    return list(a)

        if urgent:
            bombs = self._find_bombs(hand)
            if bombs:
                log.append("炸弹压飞机")
                return list(bombs[0])
        return None

    # ========== 手牌分析 ==========

    def _decompose(self, hand, groups, log):
        """分析手牌结构"""
        bombs = sum(1 for r, cs in groups.items() if len(cs) == 4)
        triples = sum(1 for r, cs in groups.items() if len(cs) == 3)
        pairs = sum(1 for r, cs in groups.items() if len(cs) == 2)
        singles = sum(1 for r, cs in groups.items() if len(cs) == 1)
        log.append(f"结构: 炸弹{bombs} 三条{triples} 对子{pairs} 单张{singles}")
        return {'bombs': bombs, 'triples': triples, 'pairs': pairs, 'singles': singles}

    def _get_smart_singles(self, hand, groups):
        """获取孤张(不属于对子/三条/炸弹的牌), 从小到大排序"""
        singles = []
        for r, cs in groups.items():
            if len(cs) == 1:
                singles.append(cs[0])
        singles.sort(key=ck)
        return singles

    def _find_pairs_no_break(self, groups):
        """只找自然对子(不从三条/炸弹拆)"""
        result = []
        for r, cs in groups.items():
            if len(cs) == 2:
                result.append(tuple(cs))
        return result

    def _triple_rank(self, combo):
        rc = {}
        for c in combo:
            rc[c[1]] = rc.get(c[1], 0) + 1
        for r, cnt in rc.items():
            if cnt >= 3:
                return rv(r)
        return -1

    # ========== 牌型查找 ==========

    def _group(self, hand):
        rc = {}
        for card in hand:
            r = card[1]
            if r not in rc:
                rc[r] = []
            rc[r].append(card)
        return rc

    def _find_bombs(self, hand):
        g = self._group(hand)
        bombs = [tuple(cs) for r, cs in g.items() if len(cs) == 4]
        bombs.sort(key=lambda b: rv(b[0][1]))
        return bombs

    def _find_triple_twos(self, hand, groups):
        """三带任意两张(不拆炸弹带)"""
        triples = [(r, cs[:3]) for r, cs in groups.items() if len(cs) >= 3]
        results = []
        for tr, tcards in triples:
            remaining = [c for c in hand if c not in tcards]
            if len(remaining) < 2:
                continue
            remaining.sort(key=ck)
            # 优先带孤张, 减少手牌碎片
            lonely = [c for c in remaining if len(groups.get(c[1], [])) == 1]
            if len(lonely) >= 2:
                results.append(tuple(tcards + lonely[:2]))
            elif len(lonely) == 1:
                others = [c for c in remaining if c != lonely[0]]
                results.append(tuple(tcards + [lonely[0]] + others[:1]))
            else:
                # 带最小的两张(尽量不拆炸弹)
                safe = [c for c in remaining if len(groups.get(c[1], [])) < 4]
                if len(safe) >= 2:
                    results.append(tuple(tcards + safe[:2]))
                else:
                    results.append(tuple(tcards + remaining[:2]))
        return results

    def _find_pairs(self, hand):
        g = self._group(hand)
        return [tuple(cs[:2]) for r, cs in g.items() if len(cs) >= 2]

    def _find_straights(self, hand, length=None):
        g = self._group(hand)
        available = sorted([r for r in RANKS if r in g], key=lambda x: rv(x))
        results = []
        min_l = length or 3
        max_l = length or len(available)
        for l in range(min_l, max_l + 1):
            for start in range(len(available) - l + 1):
                grp = available[start:start+l]
                vals = [rv(r) for r in grp]
                if vals[-1] - vals[0] == l - 1 and len(set(vals)) == l:
                    results.append(tuple(g[r][0] for r in grp))
        return results

    def _find_consecutive_pairs(self, hand, count=None):
        g = self._group(hand)
        available = sorted([r for r in RANKS if r in g and len(g[r]) >= 2], key=lambda x: rv(x))
        results = []
        min_c = count or 2
        max_c = count or len(available)
        for l in range(min_c, max_c + 1):
            for start in range(len(available) - l + 1):
                grp = available[start:start+l]
                vals = [rv(r) for r in grp]
                if vals[-1] - vals[0] == l - 1 and len(set(vals)) == l:
                    cards = []
                    for r in grp:
                        cards.extend(g[r][:2])
                    results.append(tuple(cards))
        return results

    def _find_airplanes(self, hand):
        g = self._group(hand)
        triple_ranks = sorted([r for r in RANKS if r in g and len(g[r]) >= 3], key=lambda x: rv(x))
        results = []
        for l in range(2, len(triple_ranks) + 1):
            for start in range(len(triple_ranks) - l + 1):
                grp = triple_ranks[start:start+l]
                vals = [rv(r) for r in grp]
                if max(vals) - min(vals) == l - 1:
                    tcards = []
                    for r in grp:
                        tcards.extend(g[r][:3])
                    results.append(tuple(tcards))
                    remaining = sorted([c for c in hand if c not in tcards], key=ck)
                    if len(remaining) >= l * 2:
                        results.append(tuple(tcards + remaining[:l*2]))
        return results

    def _find_kill_shot(self, hand):
        """如果整手牌本身是合法牌型，直接一手走完。"""
        from game_logic import classify_hand
        htype, _ = classify_hand(hand)
        if htype:
            return list(hand)
        return None

    def _find_finishing_play(self, hand, candidates):
        """优先选择出牌后能在下一次自由回合一手走完的候选。"""
        from game_logic import classify_hand
        for cand in candidates:
            remaining = list(hand)
            ok = True
            for card in cand:
                if card in remaining:
                    remaining.remove(card)
                else:
                    ok = False
                    break
            if not ok or not remaining:
                continue
            htype, _ = classify_hand(remaining)
            if htype:
                return cand
        return None
