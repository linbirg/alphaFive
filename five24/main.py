# -*- coding: utf-8 -*-
import time
import utils
from genData.network import ResNet as model
import tensorflow as tf
import os
import config
import numpy as np
from concurrent.futures import ProcessPoolExecutor, wait, ALL_COMPLETED
from threading import Lock, Thread
from genData.player import Player
from multiprocessing import Manager, Process, Queue
# from queue import Queue  #  这个只能在多线程之间使用，即同一个进程内部使用，不能跨进程通信
from multiprocessing.managers import BaseManager
from utils import RandomStack
import gc

# global只能在父子进程中共享只读变量

cur_dir = os.path.dirname(__file__)
os.chdir(cur_dir)
PURE_MCST = 1
AI = 2
# job_lock = Lock()


def main(restore=False):
    stack = RandomStack(board_size=config.board_size, length=config.buffer_size)
    net = model(config.board_size)
    if restore:
        net.restore(config.ckpt_path)
        # net.load_pretrained()
        # stack.load()
    with net.graph.as_default():
        episode_length = tf.placeholder(tf.float32, (), "episode_length")
        total_loss, cross_entropy, value_loss, entropy = net.total_loss, net.cross_entropy_loss, net.value_loss, net.entropy
        lr = tf.get_variable("learning_rate", dtype=tf.float32, initializer=1e-3)
        opt = tf.train.AdamOptimizer(lr).minimize(total_loss)
        net.sess.run(tf.global_variables_initializer())
        tf.summary.scalar("x_entropy_loss", cross_entropy)
        tf.summary.scalar("value_loss", value_loss)
        tf.summary.scalar("total_loss", total_loss)
        tf.summary.scalar("entropy", entropy)
        tf.summary.scalar('episode_len', episode_length)
        log_dir = os.path.join("summary", "log_" + time.strftime("%Y%m%d_%H_%M_%S", time.localtime()))
        # log_dir = "E:\\alphaFive\\five22\summary\log_20200303_20_11_49"
        journalist = tf.summary.FileWriter(log_dir, flush_secs=10)
        summury_op = tf.summary.merge_all()
    step = 1
    # k = (config.final_eps - config.noise_eps) / config.total_step
    # executor = ProcessPoolExecutor(max_workers=config.max_processes)  # 定义一个进程池，max_workers是最大进程个数
    # 定义列表，每个进程给一个管道,把管道放在Manager里面是为了实现子进程和父进程变量共享。global方式在多进程中也只能读不能写
    # cur_pipes = Manager().list([net.get_pipes(config) for _ in range(config.max_processes)])  # 进程池必须要用Manager()
    cur_pipes = [net.get_pipes(config) for _ in range(config.max_processes)]  # 手动创建进程不需要Manager()
    # job_lock.acquire(True)
    # q = Manager().Queue(50)  # 最多放置50个item, 进程池必须使用Manager()进行数据通信
    # 当需要频繁地创建进程的时候，才使用进程池进行管理。手动固定地创建max_processes个进程的话，不需要进程池
    # 进程池的开销比手动创建进程的开销要大一丢丢
    q = Queue(50)  # 用Process手动创建的进程可以使用这个Queue
    # procs = []
    for i in range(config.max_processes):
        proc = Process(target=gen_data, args=(cur_pipes[i], q))
        proc.daemon = True  # 父进程结束以后，子进程就自动结束
        proc.start()
        # executor.submit(gen_data, cur_pipes, q)  # 进程池的开销比较大，只是适用于创建大量进程，难以手动管理的情形

    while step < config.total_step:
        net.sess.run(tf.assign(lr, config.get_lr(step)))
        data_record, result = q.get(block=True)  # 获取一个item，没有则阻塞
        stack.push(data_record, result)
        if len(stack.data) > 4000:
            for _ in range(4):
                boards, weights, values, policies = stack.get_data(batch_size=config.batch_size)
                xcro_loss, mse_, entropy_, _, sum_res = net.sess.run(
                    [cross_entropy, value_loss, entropy, opt, summury_op],
                    feed_dict={net.inputs: boards, net.distrib: policies,
                               net.winner: values, net.weights: weights, episode_length: len(data_record)})
            step += 1
            journalist.add_summary(sum_res, step)
            print(" ")
            print("step: %d, xcross_loss: %0.3f, mse: %0.3f, entropy: %0.3f" % (step, xcro_loss, mse_, entropy_))
            if step % 60 == 0:
                net.saver.save(net.sess, save_path=os.path.join(config.ckpt_path, "alphaFive"), global_step=step)
                stack.save()
                print("save ckpt and data successfully")
    net.saver.save(net.sess, save_path=os.path.join(config.ckpt_path, "alphaFive"), global_step=step)

    stack.save()
    # executor.shutdown(False)
    net.close()


def gen_data(pipe, q):
    player = Player(config, training=True, pipe=pipe)
    k = (config.final_eps - config.noise_eps) / config.total_step
    step = 1
    while True:
        e = k*step + config.noise_eps
        game_record = player.run(e)
        value = game_record[-1][-2]
        game_length = len(game_record)
        if value == 0.0:
            result = utils.DRAW
        elif game_length % 2 == 1:
            result = utils.BLACK_WIN
        else:
            result = utils.WHITE_WIN
        q.put((game_record, result), block=True)  # block=True满了则阻塞
        step += config.max_processes


def next_unused_name(name):
    save_name = name
    iteration = 0
    while os.path.exists(save_name):
        save_name = name + '-' + str(iteration)
        iteration += 1
    return save_name


if __name__ == '__main__':
    main(restore=False)