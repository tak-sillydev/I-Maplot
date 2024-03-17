from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM
import json
import struct

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONF_ENCTYPE = "utf-8"

	try:
		with open(CONFIG_PATH, "r", encoding=CONF_ENCTYPE) as f:
			conf = json.load(f)
		
		sockinfo = conf["sockinfo"]
		code = sockinfo["code"]["alive"]
		req = sockinfo["request"]
		ans = sockinfo["answer"]

		setdefaulttimeout(sockinfo["timeout_sec"])
		sock_req = socket(AF_INET, SOCK_STREAM)
		sock_ans = socket(AF_INET, SOCK_STREAM)

		sock_ans.bind((ans["host"], ans["port"]))
		sock_ans.listen()

		sock_req.connect((req["host"], req["port"]))

		bmsg = req["default_msg"]["alive"].encode(sockinfo["charset"])
		data = struct.pack("b" + str(len(bmsg)) + "s", code, bmsg)

		sock_req.send(data)

		conn, _ = sock_ans.accept()

		data = conn.recv(sockinfo["max_len"])
		code, bmsg = struct.unpack("b" + str(len(data) - 1) + "s", data)
		msg = bmsg.decode(sockinfo["charset"])

		conn.close()

		sock_req.close()
		sock_ans.close()

		print(msg)
	except Exception as e:
		print(f"ERROR:{e}")