# coding: utf-8
import datetime
import requests
import json
import post
import pickle
import time
import os

from logging import INFO, DEBUG, WARNING, ERROR, CRITICAL
from gc import collect
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from finalizer import Finalizer
from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM

from interval import Scheduler
from report import EQPlotter
import log

#################################
### !!! DEBUG OR RELEASE? !!! ###
fDebug = True
#################################

### class EntryData BEGIN ###

class EntryData:
	title = ""
	link = ""
	content = ""
	id = ""
	updated_time = None

	def __init__(self, title="", link="", content="", id="", updated_time=None) -> None:
		self.SetEntry(title, link, content, id, updated_time)
		pass

	def SetEntry(self, title="", link="", content="", id="", updated_time=None) -> None:
		self.title = title
		self.link = link
		self.content = content
		self.id = id
		self.updated_time = updated_time

### class EntryData END ###


### class FeedControl BEGIN ###

class FeedControl:
	xmlid: str = ""
	last_time: datetime.datetime = None
	pkl_path: str = ""
	proc_id: int = 0 

	def __init__(self, pickle_path: str = "") -> None:
		self.last_time = \
			datetime.datetime.now(datetime.timezone.utc)
		self.pkl_path = pickle_path
		self.proc_id = os.getpid()
		
	def PickleMyself(self):
		with open(self.pkl_path, "wb") as f:
			pickle.dump(self, f)

### class FeedControl END ###

def GetEntryList(root: Element, ns: dict) -> list:
	lsentry = []
	node = root.findall("atom:entry", ns)

	for n in node:
		title = n.find("atom:title", ns).text
		link = n.find("atom:link", ns).get("href")
		content = n.find("atom:content", ns).text
		id = n.find("atom:id", ns).text
		updated = n.find("atom:updated", ns)
		dt = datetime.datetime.fromisoformat(updated.text)

		lsentry.append(EntryData(title, link, content, id, dt))

	return lsentry

def CheckId(root: Element, feedctl: FeedControl, ns: dict) -> bool:
	current = root.find("atom:id", ns).text
	ret = True if current == feedctl.xmlid else False

	feedctl.xmlid = current
	return ret

def GetJMAXMLFeed_Eqvol(feedctl: FeedControl, ns: dict, config: dict, logger: log.Logger) -> None:
	try:
		response = requests.get(config["xmlfeed"]["request_addr"])
		response.raise_for_status()
	except requests.exceptions.ConnectionError:
		logger.warning("地震情報の取得に失敗しました")
	except requests.exceptions.RequestException:
		logger.warning("地震情報の取得に失敗しました")
		logger.warning(f"HTTP Status {response.status_code}")
	else:
		response.encoding = response.apparent_encoding
		xml = ElementTree.fromstring(response.text)
		
		if CheckId(xml, feedctl, ns) is not True:
			# 「震度に関する情報」と「震源・震度に関する情報」を抜き出す
			# 「震源に関する情報」は、直後に震度と一緒に情報が再送されるため無視する
			lsentry = GetEntryList(xml, ns)
			lsentry = sorted(
				[l for l in lsentry if "震度" in l.title and l.updated_time > feedctl.last_time],
				key=lambda x: x.updated_time
			)
			if len(lsentry) > 0:
				feedctl.last_time = max(lsentry, key=lambda x: x.updated_time).updated_time

				for l in lsentry:
					response = requests.get(l.link)
					response.encoding = response.apparent_encoding

					eqp = EQPlotter(config)
					eqp.ParseXML(response.text)

					level = eqp.eqi_.intensity_area.eqlevel
					imgpath = eqp.DrawMap("3" if level >= 3 else "1")
					message = eqp.GetMessage()
					
					updated_tmz = l.updated_time.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
					post_fmt = "【" +\
						("震度速報" if "震度速報" in l.title else "震源・震度情報") +\
						updated_tmz.strftime(" %Y-%m-%d %H:%M ") + "気象庁発表】{}"
					
					logger.info("地震情報：\n" + post_fmt.format(message))
					message = post.Adjust_PostLen(post_fmt, message)
					post.Post(config["postauth"], message, imgpath)
					del eqp
				
				feedctl.PickleMyself()
				collect()
				return
		else:
			logger.info("地震情報：新しい地震の情報はありません")

def SendMail_SystemStop(mhd: log.MailHandler) -> None:
	global fDebug

	mhd.send(
		f"{datetime.datetime.now()}\n" +\
		f"==== これはデバッグ環境からの通知です ====\n" if fDebug else "" +\
		"I-Maplot は動作を停止・終了しました。ログを確認してください。"
	)

def main(mhd: log.MailHandler, config_path: str, conf_enctype: str = "utf-8"):
	try:
		log.set_logger(INFO, mhd, CONFIG_PATH, CONFIG_ENCTYPE)
		logger = log.getLogger(__name__)
		logger.info("JMAEQ I-Maplot システム開始")

		with open(CONFIG_PATH, "r", encoding=CONFIG_ENCTYPE) as f:
			conf = json.load(f)

		interval_sec = conf["interval_sec"]
		feedctl_path = conf["paths"]["feedctl"]
		output_path  = conf["paths"]["output"]
		req = conf["sockinfo"]["request"]
		ans = conf["sockinfo"]["answer"]
		ns = conf["xmlfeed"]["xml_ns"]["feed"]

		try:
			with open(feedctl_path, "rb") as f:
				feedctl = pickle.load(f)
				feedctl.pkl_path = feedctl_path
		except FileNotFoundError:
			logger.warning("FeedControl が見つかりませんでした。作成します。")
			feedctl = FeedControl(feedctl_path)
		
		if not os.path.isdir(output_path):
			logger.warning(f"画像出力先 {output_path} が見つかりませんでした。作成します。")
			os.mkdir(output_path)

		setdefaulttimeout(conf["sockinfo"]["timeout_sec"])
		sock_req = socket(AF_INET, SOCK_STREAM)
		sock_req.bind((req["host"], req["port"]))
		sock_req.listen()

		sched = Scheduler(
			interval_sec,
			GetJMAXMLFeed_Eqvol,
			(feedctl, ns, conf, logger)
		)
		sched.start()

		while True:
			try:
				conn, _ = sock_req.accept()
				message = conn.recv(conf["sockinfo"]["max_len"]).decode("utf-8")
				conn.close()

				if message == req["command"]["alive"]:
					time.sleep(0.5)
					sock_ans = socket(AF_INET, SOCK_STREAM)
					sock_ans.connect((ans["host"], ans["port"]))
					sock_ans.send(ans["command"]["alive"].encode("utf-8"))
					sock_ans.close()
				elif message == req["command"]["exit"]:
					break
	
			except Exception as e:
				logger.error(e)

		sched.stop()
		feedctl.PickleMyself()
	except Exception as e:
		logger.error(e)
	else:
		logger.info("システムは正常に終了しました")
	finally:
		sock_req.close()

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONFIG_ENCTYPE = "utf-8"

	print("Starting JMAEQ I-Maplot...")
	mhd = log.MailHandler(CONFIG_PATH, CONFIG_ENCTYPE)

	with Finalizer(SendMail_SystemStop, mhd):
		main(mhd, CONFIG_PATH, CONFIG_ENCTYPE)
	
	print("Exiting...")

#### post 封じられてる（コメントアウト）ので注意
#### デバッグモード。本番環境に移す前にfDebugをFalseに。