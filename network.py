# -*- coding: utf-8 -*-
import tensorflow as tf
from functools import reduce
DATA_FORMAT = "channels_first"


class ResNet(object):
    """
    输入是落子前的局面，输出policy是在每个地方落子的会获胜的概率，输出value是基于当前落子的选手的价值。
    黑子是先手，落子1，白字是后手，落子-1，局面是state。
    假设现在轮到黑子下，player=1，输入是state，网络预测的则是棋子1的价值；
    若现在轮到白字下，player=-1，输入则是-state，网络预测的依然是棋子1的价值。

    只对初始局面评估，不对最终局面评估
    """
    def __init__(self, board_size):
        self.board_size = board_size
        self.inputs = tf.placeholder(dtype=tf.float32, shape=[None, 2, board_size, board_size])
        self.winner = tf.placeholder(dtype=tf.float32, shape=[None])
        self.distrib = tf.placeholder(dtype=tf.float32, shape=[None, board_size*board_size])
        self.value = None
        self.policy = None
        self.network()
        self.sess = tf.Session()
        self.sess.run(tf.global_variables_initializer())
        self.saver = tf.train.Saver(max_to_keep=100)

    def network(self):
        f = self.inputs
        with tf.variable_scope("bone"):
            f = tf.layers.conv2d(f, 32, 3, padding="SAME", data_format=DATA_FORMAT, name="conv1", activation=tf.nn.elu)
            f = tf.layers.conv2d(f, 64, 3, padding="SAME", data_format=DATA_FORMAT, name="conv2", activation=tf.nn.elu)
            f = tf.layers.conv2d(f, 128, 3, padding="SAME", data_format=DATA_FORMAT, name="conv3", activation=tf.nn.elu)

        with tf.variable_scope("value"):
            v = tf.layers.conv2d(f, 32, 1, padding="VALID", data_format=DATA_FORMAT, name="conv1", activation=tf.nn.elu)
            last_dim = reduce(lambda x, y: x*y, v.get_shape().as_list()[1:])
            v = tf.reshape(v, (-1, last_dim))
            v = tf.layers.dense(v, 256, activation=tf.nn.elu, name="fc1")
            v = tf.layers.dense(v, 64, activation=tf.nn.elu, name="fc2")
            self.value = tf.layers.dense(v, 1, activation=tf.nn.tanh, name="fc3")

        with tf.variable_scope("policy"):
            p = tf.layers.conv2d(f, 32, 1, padding="VALID", data_format=DATA_FORMAT, name="conv1", activation=tf.nn.elu)
            last_dim = reduce(lambda x, y: x * y, p.get_shape().as_list()[1:])
            p = tf.reshape(p, (-1, last_dim))
            self.policy = tf.layers.dense(p, self.board_size*self.board_size, activation=None, name="fc1")

    def eval(self, inputs):
        prob = tf.nn.softmax(self.policy, axis=1)
        prob_, value_ = self.sess.run([prob, self.value], feed_dict={self.inputs: inputs})
        return prob_, value_


