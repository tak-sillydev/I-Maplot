from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM
import json

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONF_ENCTYPE = "utf-8"

	try:
		with open(CONFIG_PATH, "r", encoding=CONF_ENCTYPE) as f:
			conf = json.load(f)
		
		req = conf["sockinfo"]["request"]
		reqhost = req["host"]
		reqport = req["port"]
		cmd_exit = req["command"]["exit"]

		setdefaulttimeout(conf["sockinfo"]["timeout_sec"])
		sock = socket(AF_INET, SOCK_STREAM)
		sock.connect((reqhost, reqport))
		sock.send(cmd_exit.encode("utf-8"))
		sock.close()
	except Exception as e:
		print(f"ERROR:{e}")