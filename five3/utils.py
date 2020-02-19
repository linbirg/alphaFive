# -*- coding: utf-8 -*-
import numpy as np
import pickle


def trans_to_input(state: np.ndarray, player, last_action, type_=np.float32):
    """
    本来只需要return state.astype(np.float32)就可以了。这里加上tmp3有助于加快收敛，加上tmp4更加收敛
    :param state:
    :param player:
    :param last_action:
    :param type_:
    :return:
    """
    # return state.astype(np.float32)
    tmp1 = np.equal(state, 1).astype(type_)
    tmp2 = np.equal(state, -1).astype(type_)
    tmp3 = np.zeros(state.shape, dtype=type_) + player
    tmp4 = np.zeros(state.shape, dtype=type_)
    if last_action is not None:
        tmp4[last_action[0], last_action[1]] = 1
    out = np.stack([tmp1, tmp2, tmp3, tmp4])
    return out


def valid_move(state: np.ndarray):
    return [(int(index[0]), int(index[1])) for index in np.argwhere(state == 0)]


def write_file(objects, file_name):
    filewriter = open(file_name, 'wb')
    pickle.dump(objects, filewriter)
    filewriter.close()


def generate_training_data(game_record, board_size, discount=1.0):
    """
    :param game_record: game_record.append({"distribution": distribution, "action": action})
    :param board_size:
    :return:
    """
    board = np.zeros([board_size, board_size], dtype=np.int8)
    data = []
    player = 1
    last_action = None
    if game_record[-1]:
        winner = 0
    elif len(game_record) % 2 == 0:  # 先手（黑手）赢了
        winner = 1
    else:
        winner = -1  # 后手（白手）赢了
    for i in range(len(game_record) - 1):
        state = trans_to_input(board * player, player=player, last_action=last_action, type_=np.int8)
        data.append({"state": state, "distribution": game_record[i]['distribution'], "value": winner})
        action = game_record[i]['action']
        board[action[0], action[1]] = player  # 执行动作
        last_action = action
        player, winner = -player, -winner
    return data


class RandomStack(object):
    def __init__(self, board_size, dim=4, length=1000):
        self.state = np.empty(shape=(length, dim, board_size, board_size), dtype=np.int8)
        self.distrib = np.empty(shape=(length, board_size * board_size), dtype=np.float32)
        self.winner = np.empty(shape=(length,), dtype=np.int8)
        self.length = length
        self.board_size = board_size
        self.idx = 0
        self.is_full = False

    def isEmpty(self):
        pass

    def push(self, data: list):
        for item in data:
            self.state[self.idx] = item["state"]
            self.distrib[self.idx] = item["distribution"]
            self.winner[self.idx] = item["value"]
            self.idx += 1
            if self.idx >= self.length:
                self.idx = 0
                self.is_full = True

    def push2(self, data: list):
        """
        :param data: 一个list，每个元素是一个dict，有键"state"，"distribution", "value"
        :return:
        """
        for item in data:
            for i in [0, 1, 2, 3]:  # 旋转和翻转
                # from IPython import embed; embed()
                self.state[self.idx] = np.rot90(item["state"], k=i, axes=(1, 2))  # 并非原地翻转
                self.distrib[self.idx] = np.rot90(item["distribution"].reshape((self.board_size, self.board_size)),
                                                  k=i).reshape((-1,))
                self.winner[self.idx] = item["value"]
                self.idx += 1
                if self.idx >= self.length:
                    self.idx = 0
                    self.is_full = True

                self.state[self.idx] = np.flip(np.rot90(item["state"], k=i, axes=(1, 2)), axis=1)  # 并非原地翻转
                self.distrib[self.idx] = np.flip(
                    np.rot90(item["distribution"].reshape((self.board_size, self.board_size)),
                             k=i), axis=0).reshape((-1,))
                self.winner[self.idx] = item["value"]
                self.idx += 1
                if self.idx >= self.length:
                    self.idx = 0
                    self.is_full = True

                # self.state[self.idx] = np.flip(np.rot90(item["state"], k=i, axes=(1, 2)), axis=2)  # 并非原地翻转
                # self.distrib[self.idx] = np.flip(
                #     np.rot90(item["distribution"].reshape((self.board_size, self.board_size)),
                #              k=i), axis=1).reshape((-1,))
                # self.winner[self.idx] = item["value"]
                # self.idx += 1
                # if self.idx >= self.length:
                #     self.idx = 0
                #     self.is_full = True

    def get_data(self, batch_size=1):
        if self.is_full:  # 满了，随便挑选
            idx = np.random.choice(self.length, size=batch_size, replace=False)
            state = [self.state[i] for i in idx]
            distrib = [self.distrib[i] for i in idx]
            winner = [self.winner[i] for i in idx]
            return np.stack(state).astype(np.float32), np.stack(distrib).astype(np.float32), np.stack(
                winner).astype(np.float32)
        elif self.idx > batch_size:  # 没满，则在指定范围挑选
            idx = np.random.choice(self.idx, size=batch_size, replace=False)
            state = [self.state[i] for i in idx]
            distrib = [self.distrib[i] for i in idx]
            winner = [self.winner[i] for i in idx]
            return np.stack(state).astype(np.float32), np.stack(distrib).astype(np.float32), np.stack(
                winner).astype(np.float32)
        else:
            return self.state[:self.idx].astype(np.float32), self.distrib[:self.idx].astype(
                np.float32), self.winner[:self.idx].astype(np.float32)


def softmax(x):
    max_value = np.max(x)
    probs = np.exp(x - max_value)
    probs /= np.sum(probs)
    return probs


def board_to_state(board: np.ndarray) -> str:
    fen = ""
    h, w = board.shape
    for i in range(h):
        c = 0
        for j in range(w):
            if board[i, j] == 0:
                c += 1
            else:
                fen += chr(ord('a') + c) if c > 0 else ''
                fen += str(board[i, j] + 2)
                c = 0
        fen += chr(ord('a') + c) if c > 0 else ''
        fen += '/'
    return fen


def state_to_board(state: str, board_size: int):
    """
    根据字符串表示的state转换为棋盘。字符串中，黑子用1表示，红子用3表示
    :param state:
    :param board_size:
    :return:
    """
    board = np.zeros((board_size, board_size), np.int8)
    i = j = 0
    for ch in state:
        if ch == '/':
            i += 1
            j = 0
        elif ch.isalpha():
            j += ord(ch) - ord('a')
        else:
            board[i][j] = int(ch) - 2
            j += 1
    return board


def is_game_over(board: np.ndarray, goal: int) -> tuple:
    """
    基于黑子(1)落子前，判断当前局面是否结束，一般来说若结束且非和棋都会返回-1.0，
    因为现在轮到黑子（1）落子了，但是游戏却已经结束了，结束前的最后一步一定是白子(-1)落子的，白子赢了，则返回-1
    :param board:
    :param goal:五子棋，goal就等于五
    :return:
    """
    h, w = board.shape
    for i in range(h):
        for j in range(w):
            hang = sum(board[i: min(i + goal, w), j])
            if hang == goal:
                return True, 1.0
            elif hang == -goal:
                return True, -1.0
            lie = sum(board[i, j: min(j + goal, h)])
            if lie == goal:
                return True, 1.0
            elif lie == -goal:
                return True, -1.0
            # 斜线有点麻烦
            if i <= h - goal and j <= w - goal:
                xie = sum([board[i + k, j + k] for k in range(goal)])
                if xie == goal:
                    return True, 1.0
                elif xie == -goal:
                    return True, -1.0
            if i >= goal - 1 and j <= w - goal:
                xie = sum([board[i - k, j + k] for k in range(goal)])
                if xie == goal:
                    return True, 1.0
                elif xie == -goal:
                    return True, -1.0
    if np.where(board == 0)[0].shape[0] == 0:  # 棋盘满了，和棋
        return True, 0.0
    return False, 0.0


def get_legal_moves(board: np.ndarray):
    zeros = np.where(board == 0)
    return [(int(i), int(j)) for i, j in zip(*zeros)]


def board_to_inputs(board: np.ndarray, type_=np.float32):
    # return board.astype(np.float32)
    tmp1 = np.equal(board, 1).astype(type_)
    tmp2 = np.equal(board, -1).astype(type_)
    out = np.stack([tmp1, tmp2])
    return out


def step(board: np.ndarray, action: tuple):
    """
    执行动作并翻转棋盘，保持当前选手为1代表的棋局
    :param board:
    :param action:
    :return:
    """
    board[action[0], action[1]] = 1
    return -board

def construct_weights(length:int, gamma=0.95):
    """
    每局游戏大概36回合，64步，0.95^64=0.0375
    :param length:
    :param gamma:
    :return:
    """
    w = np.empty((int(length),), np.float32)
    w[length-1] = 1.0  # 最靠后的权重最大
    for i in range(length-2, -1, -1):
        w[i] = w[i+1]*gamma
    return length*w/np.sum(w)  # 所有元素之和为length