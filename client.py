import socket
import sys
from time import sleep

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

s.connect(('localhost', 6667))

s.send("hello worlddd ".encode())
print(s.recv(1024).decode())

s.close()
