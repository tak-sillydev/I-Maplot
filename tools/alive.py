# -*- coding: utf-8 -*-
# location: /tools

from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM
from socket import error as sockerr

import json
import struct
import argparse

def ConnectwithRetry(host: str, port: int, retries: int=0) -> socket | None:
	for i in range(retries + 1):
		try:
			if i > 0:	print("Retrying...")
			
			sock = socket(AF_INET, SOCK_STREAM)
			sock.connect((host, port))
			return sock
		except sockerr as e:
			print(f"Connection Error: {e}")

	return None

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONF_ENCTYPE = "utf-8"

	parser = argparse.ArgumentParser(description="JMAEQ I-Maplot 生存確認用プログラム")

	try:
		parser.add_argument("-a", "--address", help="コマンド送信宛先アドレス")
		parser.add_argument("-p", "--port", help="コマンド送信宛先ポート")
		args = parser.parse_args()

		with open(CONFIG_PATH, "r", encoding=CONF_ENCTYPE) as f:
			conf = json.load(f)
		
		sockinfo = conf["sockinfo"]
		code = sockinfo["code"]["alive"]
		addr = sockinfo["address"]["request"]

		host = args.address if args.address != None else addr["host"]
		port = args.port if args.port != None else addr["port"]

		setdefaulttimeout(sockinfo["timeout_sec"])
		sock = ConnectwithRetry(host, int(port), sockinfo["retries"])

		if (sock == None):
			print("ERROR: Retries reached max counts.")
			exit()

		bmsg = sockinfo["message"]["request"]["alive"].encode(sockinfo["charset"])
		data = struct.pack("b" + str(len(bmsg)) + "s", code, bmsg)

		sock.send(data)

		data = sock.recv(sockinfo["max_len"])
		code, bmsg = struct.unpack("b" + str(len(data) - 1) + "s", data)
		msg = bmsg.decode(sockinfo["charset"])

		sock.close()

		print(msg)
	except Exception as e:
		print(f"ERROR:{e}")