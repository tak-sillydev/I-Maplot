from socket import socket, AF_INET, SOCK_STREAM
import json

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONF_ENCTYPE = "utf-8"

	try:
		with open(CONFIG_PATH, "r", encoding=CONF_ENCTYPE) as f:
			conf = json.load(f)
			schost = conf["exitinfo"]["host"]
			scport = conf["exitinfo"]["port"]
			command = conf["exitinfo"]["command"]

		sock = socket(AF_INET, SOCK_STREAM)
		sock.connect((schost, scport))
		sock.send(command.encode("utf-8"))
		sock.close()
	except Exception as e:
		print(f"ERROR:{e}")