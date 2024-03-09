from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM
import json

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONF_ENCTYPE = "utf-8"
	TIMEOUT_SEC = 10.0

	try:
		with open(CONFIG_PATH, "r", encoding=CONF_ENCTYPE) as f:
			conf = json.load(f)
		
		req = conf["sockinfo"]["request"]
		ans = conf["sockinfo"]["answer"]

		reqhost = req["host"]
		reqport = req["port"]
		anshost = ans["host"]
		ansport = ans["port"]

		setdefaulttimeout(conf["sockinfo"]["timeout_sec"])
		sock_req = socket(AF_INET, SOCK_STREAM)
		sock_ans = socket(AF_INET, SOCK_STREAM)

		sock_ans.bind((anshost, ansport))
		sock_ans.listen()

		sock_req.connect((reqhost, reqport))
		sock_req.send(req["command"]["alive"].encode("utf-8"))

		conn, _ = sock_ans.accept()
		message = conn.recv(conf["sockinfo"]["max_len"]).decode("utf-8")
		conn.close()

		sock_req.close()
		sock_ans.close()

		print(message)
	except Exception as e:
		print(f"ERROR:{e}")