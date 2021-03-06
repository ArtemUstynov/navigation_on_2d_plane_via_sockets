import os
import socket
from time import sleep
from queue import *

SERVER_KEY = 54621
CLIENT_KEY = 45328
SYNTAX_ERROR = "Invalid Syntax"
TIMEOUT_ERROR = "Server Timeout"
LOGIN_ERROR = "Failed to login"
LOGIC_ERROR = "Unexpected message"


class SyntaxException(Exception):
    pass


class LoginException(Exception):
    pass


class TimeoutException(Exception):
    pass


class LogicException(Exception):
    pass


def recharge(conn):
    try:
        if get_msg(conn, 12, 5) != "FULL POWER":
            raise LogicException(LOGIC_ERROR)
    except socket.timeout:
        raise TimeoutException(TIMEOUT_ERROR)


def syntax_error(conn):
    conn.send("301 SYNTAX ERROR\a\b".encode())
    conn.close()
    return


def raw_to_text(raw):
    result = ""
    for ch in raw[:-2]:
        result += chr(ch)
    return result


def get_raw_msg(conn, size, timeout):
    msg = []
    conn.settimeout(timeout)
    recharging = [82, 69, 67, 72, 65, 82, 71]
    try:
        while True:
            while len(msg) < size:

                msg += conn.recv(1)

                if len(msg) > size:
                    return 1
                if len(msg) == size and (msg[-2] != 7 or msg[-1] != 8):
                    if msg == recharging:
                        size = 12
                        continue
                    raise SyntaxException(SYNTAX_ERROR)
                if len(msg) < 2:
                    continue
                str_msg = ""
                for ch in msg:
                    str_msg += chr(ch)

                pos = str_msg.find("\a\b")
                if pos != -1:
                    return msg[:pos + 2]
    except socket.timeout:
        raise TimeoutException(TIMEOUT_ERROR)


def auth(conn):
    expected_client_hash = 0
    for i in range(2):
        msg_size = 7
        if i == 0:
            msg_size = 12

        login_name = get_raw_msg(conn, msg_size, 1)

        if raw_to_text(login_name) == "RECHARGING":
            recharge(conn)
            login_name = get_raw_msg(conn, msg_size, 1)

        if login_name[-2] == 7 and login_name[-1] == 8:
            if i == 0:
                name_hash = 0
                for ch in login_name[:-2]:
                    name_hash += ch
                name_hash = (name_hash * 1000) % 65536
                expected_client_hash = (name_hash + CLIENT_KEY) % 65536
                name_hash = (name_hash + SERVER_KEY) % 65536

                conn.send((str(name_hash) + "\a\b").encode())
            else:
                client_hash = ""
                for ch in login_name[:-2]:
                    client_hash += chr(ch)
                if int(client_hash) == expected_client_hash:
                    c.send((str(200) + " OK\a\b").encode())
                    return True
                else:
                    raise LoginException(LOGIN_ERROR)
        else:
            return


def get_msg(conn, size, timeout):
    msg = get_raw_msg(conn, size, timeout)
    result = raw_to_text(msg)

    if len(msg) <= 2:
        return ""
    if result[len(result) - 1].isspace():
        raise SyntaxException(SYNTAX_ERROR)
    if result == "RECHARGING":
        recharge(conn)
        return get_msg(conn, size, timeout)
    return result


def get_coor(msg):
    if str(msg).startswith("OK"):
        coor = msg.split()
        try:
            coor[1] = int(coor[1])
            coor[2] = int(coor[2])
        except:
            raise SyntaxException(SYNTAX_ERROR)
        return coor[1:3]
    else:
        raise SyntaxException(SYNTAX_ERROR)


def rotate(conn, direct, dest):
    directions = {"L": 0, "U": 1, "R": 2, "D": 3}
    curr = directions[direct]
    final = directions[dest]
    if curr == final:
        return dest
    dif = final - curr
    for r in range(abs(dif)):
        if curr < final:
            conn.send("104 TURN RIGHT\a\b".encode())
        else:
            conn.send("103 TURN LEFT\a\b".encode())
        get_msg(conn, 12, 1)
    return dest


def get_direction(conn):
    while True:
        conn.send("102 MOVE\a\b".encode())
        pos1 = get_coor(get_msg(conn, 12, 1))

        conn.send("102 MOVE\a\b".encode())
        pos2 = get_coor(get_msg(conn, 12, 1))
        if pos1 != pos2:
            break
    direct = "U"
    if pos1[0] > pos2[0]:
        direct = "U"
    if pos1[0] < pos2[0]:
        direct = "D"
    if pos1[1] > pos2[1]:
        direct = "L"
    if pos1[1] < pos2[1]:
        direct = "R"
    return pos2, direct


def move_one(conn):
    conn.send("102 MOVE\a\b".encode())
    msg = get_msg(conn, 12, 1)
    if msg == "RECHARGING":
        msg = get_msg(conn, 12, 1)
    return get_coor(msg)


# coor = 0 = x, coor = 1 = y
def go_straight(conn, pos, coor, goal):
    while pos[coor] != goal:
        pos = move_one(conn)
    return pos


def do_spiral(conn, direct):
    rotate(conn, direct, "U")
    for k in range(4):
        for i in range(4):
            conn.send("103 TURN LEFT\a\b".encode())
            get_msg(conn, 12, 1)
            for c in range(4 - k):
                msg = "OK"
                while msg.startswith("OK"):
                    conn.send("105 GET MESSAGE\a\b".encode())
                    msg = get_msg(conn, 100, 1)
                if msg != "":
                    return msg
                move_one(conn)


def move(conn, pos, direct):
    # conn.send("103 TURN LEFT\a\b".encode())
    if pos[0] > -2:
        direct = rotate(conn, direct, "U")
        pos = go_straight(conn, pos, 0, -2)
    if pos[0] < -2:
        direct = rotate(conn, direct, "D")
        pos = go_straight(conn, pos, 0, -2)
    if pos[1] > 2:
        direct = rotate(conn, direct, "L")
        pos = go_straight(conn, pos, 1, 2)
    if pos[1] < 2:
        direct = rotate(conn, direct, "R")
        go_straight(conn, pos, 1, 2)
    print(do_spiral(conn, direct))
    conn.send("106 LOGOUT\a\b".encode())


soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # socket creation: ip/tcp
soc.bind(('localhost', 6666))  # binding the socket to this device, port number 6666
soc.listen(10)  # number of clients

while True:
    c, address = soc.accept()  # accept returns newly created socket and address of the client
    child_pid = os.fork()  # fork returns process id of the child - stored in the parent
    if child_pid != 0:  # we are in the parent thread
        c.close()
        continue

    soc.close()

    c.settimeout(10)
    try:
        try:
            auth(c)
            direction = get_direction(c)
            move(c, direction[0], direction[1])
        except LoginException:
            c.send("300 LOGIN FAILED\a\b".encode())
            c.close()
            break
        except SyntaxException:
            syntax_error(c)
            break
        except TimeoutException:
            c.close()
            break
        except LogicException:
            c.send("302 LOGIC ERROR\a\b".encode())
            c.close()

        c.close()
        break  # child executes only one cycle

    except socket.timeout as e:  # if timeout occurs
        print("Timeout!")
        c.close()
