# -*- coding: utf-8 -*-
import numpy as np
import random
from logging import getLogger

logger = getLogger(__name__)
BLACK_WIN = 1
WHITE_WIN = -1
DRAW = 0


class RandomStack(object):
    def __init__(self, board_size, length=2000):
        self.data = []
        self.board_size = board_size
        self.length = length
        self.white_win = 0
        self.black_win = 0
        self.data_len = []  # 装载每条数据的长度
        self.result = []  # 装载结果

    def isEmpty(self):
        return len(self.data) == 0

    def is_full(self):
        return len(self.data) >= self.length

    def push(self, data: list, result: int):
        data_len = len(data)  # 数据的长度
        # 太短小的数据就舍弃
        if random.random() <= -0.1*data_len + 1.6:
            print("discard an episode for length : ***********************", data_len)
            return False
        self.data.extend(data)  # 数据添加进去
        self.data_len.append(data_len)  # 长度添加进去
        self.result.append(result)  # 结果添加进去
        if result == BLACK_WIN:
            self.black_win += 1
            if random.random() < (self.white_win - self.black_win) / (self.black_win * 1.4):
                print("add a copy for black, ================================================")
                self.data.extend(data)  # 数据添加进去
                self.data_len.append(data_len)  # 长度添加进去
                self.result.append(result)  # 结果添加进去
                self.black_win += 1

        elif result == WHITE_WIN:
            self.white_win += 1
            if random.random() < (self.black_win - self.white_win) / (self.white_win * 1.04):
                print("add a copy for white, ================================================")
                self.data.extend(data)  # 数据添加进去
                self.data_len.append(data_len)  # 长度添加进去
                self.result.append(result)  # 结果添加进去
                self.white_win += 1

        beyond = len(self.data) - self.length
        if beyond > 0:
            self.data = self.data[beyond:]
            while True:
                if beyond >= self.data_len[0]:  # 需要跳出去的数据长度大于第一条数据的长度
                    beyond -= self.data_len[0]
                    self.data_len.pop(0)
                    result = self.result.pop(0)
                    if result == BLACK_WIN:
                        self.black_win -= 1
                    elif result == WHITE_WIN:
                        self.white_win -= 1
                else:
                    self.data_len[0] -= beyond
                    break
        print("black: white = {}: {} in the memory".format(self.black_win, self.white_win))
        return True

    def get_data(self, batch_size=1):
        num = min(batch_size, len(self.data))
        idx = np.random.choice(len(self.data), size=num, replace=False)
        boards = np.empty((num, self.board_size, self.board_size), dtype=np.float32)
        weights = np.empty((num,), dtype=np.float32)
        values = np.empty((num,), dtype=np.float32)
        policies = np.empty((num, self.board_size, self.board_size), dtype=np.float32)
        for i, ix in enumerate(idx):
            state, p, v, w = self.data[ix]
            board = state_to_board(state, self.board_size)
            k = np.random.choice([0, 1, 2, 3])
            board = np.rot90(board, k=k, axes=(0, 1))
            p = np.rot90(p, k=k, axes=(0, 1))
            if random.choice([1, 2]) == 1:
                board = np.flip(board, axis=0)
                p = np.flip(p, axis=0)
            boards[i] = board_to_inputs(board)
            weights[i] = w
            values[i] = v
            policies[i] = p
        policies = policies.reshape((num, self.board_size * self.board_size))
        return boards, weights, values, policies


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


def board_to_inputs2(board: np.ndarray, type_=np.float32):
    # return board.astype(np.float32)
    tmp1 = np.equal(board, 1).astype(type_)
    tmp2 = np.equal(board, -1).astype(type_)
    out = np.stack([tmp1, tmp2])
    return out


def board_to_inputs(board: np.ndarray, type_=np.float32):
    return board.astype(type_)


def step(board: np.ndarray, action: tuple):
    """
    执行动作并翻转棋盘，保持当前选手为1代表的棋局
    :param board:
    :param action:
    :return:
    """
    board[action[0], action[1]] = 1
    return -board


def construct_weights(length: int, gamma=0.95):
    """
    每局游戏大概36回合，64步，0.95^64=0.0375
    :param length:
    :param gamma:
    :return:
    """
    w = np.empty((int(length),), np.float32)
    w[length - 1] = 1.0  # 最靠后的权重最大
    for i in range(length - 2, -1, -1):
        w[i] = w[i + 1] * gamma
    return length * w / np.sum(w)  # 所有元素之和为length