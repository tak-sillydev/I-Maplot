from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM
import json
import struct
import sys

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONF_ENCTYPE = "utf-8"

	try:
		with open(CONFIG_PATH, "r", encoding=CONF_ENCTYPE) as f:
			conf = json.load(f)
		
		sockinfo = conf["sockinfo"]
		code = sockinfo["code"]["exit"]
		req = sockinfo["request"]


		msg  = sys.argv[1] if len(sys.argv) >= 2 else req["default_msg"]["exit"]
		bmsg = msg.encode(sockinfo["charset"])
		data = struct.pack("b" + str(len(bmsg)) + "s", code, bmsg)

		setdefaulttimeout(sockinfo["timeout_sec"])
		sock = socket(AF_INET, SOCK_STREAM)
		sock.connect((req["host"], req["port"]))
		sock.send(data)
		sock.close()
	except Exception as e:
		print(f"ERROR:{e}")