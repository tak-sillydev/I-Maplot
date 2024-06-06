# -*- coding: utf-8 -*- 
# Location: /tools

from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM
from socket import error as sockerr

import json
import struct
import sys
import argparse

def ConnectwithRetry(host: str, port: int, retries: int=0) -> socket | None:
	for i in range(retries + 1):
		try:
			sock = socket(AF_INET, SOCK_STREAM)
			sock.connect((host, port))
			return sock
		except sockerr as e:
			print(f"Connection Error: {e}")
			print("Retrying...")

	return None

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONF_ENCTYPE = "utf-8"

	parser = argparse.ArgumentParser(description="JMAEQ I-Maplot 終了用プログラム")

	try:
		parser.add_argument("-a", "--address", help="コマンド送信宛先アドレス")
		parser.add_argument("-p", "--port", help="コマンド送信宛先ポート")
		parser.add_argument("-m", "--message", help="システムに送信するメッセージ")
		args = parser.parse_args()

		with open(CONFIG_PATH, "r", encoding=CONF_ENCTYPE) as f:
			conf = json.load(f)
		
		sockinfo = conf["sockinfo"]
		code = sockinfo["code"]["exit"]
		addr = sockinfo["address"]["request"]

		host = args.address if args.address != None else addr["host"]
		port = args.port if args.port != None else addr["port"]
		msg  = args.message if args.message != None else sockinfo["message"]["request"]["exit"]

		bmsg = msg.encode(sockinfo["charset"])
		data = struct.pack("b" + str(len(bmsg)) + "s", code, bmsg)

		setdefaulttimeout(sockinfo["timeout_sec"])
		
		sock = ConnectwithRetry(host, int(port), sockinfo["retries"])

		if (sock == None):
			print("ERROR: Retries reached max counts.")
			exit()

		sock.send(data)

		data = sock.recv(sockinfo["max_len"])
		code, bmsg = struct.unpack("b" + str(len(data) - 1) + "s", data)
		msg = bmsg.decode(sockinfo["charset"])

		sock.close()
		print(msg)

	except Exception as e:
		print(f"ERROR:{e}")