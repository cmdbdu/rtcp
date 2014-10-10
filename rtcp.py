# -*- coding: utf-8 -*-

'''
filename:rtcp.py
@desc:
利用python的socket端口转发，用于远程维护
如果连接不到远程，会sleep 36s，最多尝试200(即两小时)

@usage:
./rtcp.py stream1 stream2
stream为：l:port或c:host:port
l:port表示监听指定的本地端口
c:host:port表示监听远程指定的端口

@author: watercloud, zd, knownsec team
@web: www.knownsec.com, blog.knownsec.com
@date: 2009-7
'''

from __future__ import print_function

import socket
import sys
import os
import threading
import time

streams = [None, None]  # 存放需要进行数据转发的两个数据流（都是SocketObj对象）
debug = 1  # 调试状态 0 or 1

# define in socket.h
SO_BINDTODEVICE = 25
SO_REUSEADDR = 2


def _usage():
    print('Usage: ./rtcp.py stream1 stream2\nstream : l:port  or c:host:port')


def _get_another_stream(num):
    '''
    从streams获取另外一个流对象，如果当前为空，则等待
    '''
    if num == 0:
        num = 1
    elif num == 1:
        num = 0
    else:
        raise "ERROR"

    while True:
        if streams[num] == 'quit':
            print("can't connect to the target, quit now!")
            sys.exit(1)

        if streams[num] is not None:
            return streams[num]
        else:
            time.sleep(1)


def _xstream(num, s1, s2):
    '''
    交换两个流的数据
    num为当前流编号,主要用于调试目的，区分两个回路状态用。
    '''
    try:
        while True:
            # 注意，recv函数会阻塞，直到对端完全关闭（close后还需要一定时间才能关闭，最快关闭方法是shutdow）
            buff = s1.recv(1024)
            if debug > 0:
                print("stream[%d] recv" % num)
            if len(buff) == 0:  # 对端关闭连接，读不到数据
                print("stream[%d] one closed" % num)
                break
            s2.sendall(buff)
            if debug > 0:
                print("stream[%d] sendall" % num)
    except:
        print("stream[%d] one closed by except!" % num)

    try:
        s1.shutdown(socket.SHUT_RDWR)
        s1.close()
    except:
        pass

    try:
        s2.shutdown(socket.SHUT_RDWR)
        s2.close()
    except:
        pass

    streams[0] = None
    streams[1] = None
    print("stream all closed")
    return


def _server(port, num, interface=None):
    '''
    处理服务情况,num为流编号（第0号还是第1号）
    '''
    bind_ip = '0.0.0.0'
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 允许端口重用避免 TIME_WAIT 导致bind 失败
    srv.setsockopt(socket.SOL_SOCKET, SO_REUSEADDR, 1)

    if interface:  # 安全性考虑允许选择绑定的网卡
        srv.setsockopt(socket.SOL_SOCKET, 25, interface)

    srv.bind((bind_ip, port))
    srv.listen(1)
    print('stream[%d] listen [%s:%d] wait .' % (num, bind_ip, port))
    while True:
        conn, addr = srv.accept()
        print("stream[%d] connected from:%s" % (num, addr))
        streams[num] = conn  # 放入本端流对象
        s2 = _get_another_stream(num)  # 获取另一端流对象
        _xstream(num, conn, s2)


def _connect(host, port, num):
    '''	处理连接，num为流编号（第0号还是第1号）

    @note: 如果连接不到远程，会sleep 36s，最多尝试200(即两小时)
    '''
    not_connet_time = 0
    wait_time = 36
    try_cnt = 199
    while True:
        if not_connet_time > try_cnt:
            streams[num] = 'quit'
            print('not connected')
            return None

        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn.connect((host, port))
        except Exception:
            print ('can not connect %s:%s!' % (host, port))
            not_connet_time += 1
            time.sleep(wait_time)
            continue

        print("connected to %s:%i" % (host, port))
        streams[num] = conn  # 放入本端流对象
        s2 = _get_another_stream(num)  # 获取另一端流对象
        _xstream(num, conn, s2)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        _usage()
        sys.exit(1)
    tlist = []  # 线程列表，最终存放两个线程对象
    socket.setdefaulttimeout(600)  # 十分钟超时
    targv = [sys.argv[1], sys.argv[2]]
    for i in [0, 1]:
        s = targv[i]  # stream描述 c:ip:port 或 l:port
        sl = s.split(':')
        if len(sl) >= 2 and (sl[0] == 'l' or sl[0] == 'L'):  # l:port
            interface = None
            if len(sl) == 3:
                if os.getuid() == 0:
                    interface = sl[2]
                else:
                    print('WARN: Require root privileges.')
            t = threading.Thread(target=_server,
                                 args=(int(sl[1]), i, interface))
            tlist.append(t)
        elif len(sl) == 3 and (sl[0] == 'c' or sl[0] == 'C'):  # c:host:port
            t = threading.Thread(target=_connect,
                                 args=(sl[1], int(sl[2]), i))
            tlist.append(t)
        else:
            _usage()
            sys.exit(1)

    for t in tlist:
        t.start()
    for t in tlist:
        t.join()
    sys.exit(0)
