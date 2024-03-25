# coding: utf-8
import datetime
import requests
import struct
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
from socket import socket, setdefaulttimeout, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

from interval import Scheduler
from report import EQPlotter
import log

#################################
### !!! DEBUG OR RELEASE? !!! ###
fDebug = True
#################################

### class EntryData BEGIN ###

class EntryData:
	"""
		気象庁から取得した XML フィード（目次にあたる）の各項目の情報をオブジェクトにして保存する。
		地震情報の判断、解析の入口として使用する。
	"""
	def __init__(self, title: str = "", link: str = "", content: str = "",
			  		id: str = "", updated_time: datetime.datetime = None) -> None:
		self.SetEntry(title, link, content, id, updated_time)
		pass

	def SetEntry(self, title: str = "", link: str = "", content: str = "",
			  		id: str = "", updated_time: datetime.datetime = None) -> None:
		self.updated_time: str	= updated_time
		self.title: str		= title
		self.link: str		= link
		self.content: str	= content
		self.id: str		= id

### class EntryData END ###


### class FeedControl BEGIN ###

class FeedControl:
	"""
		I-Maplot を動かすにあたり必要な情報、特に地震情報の更新に関する情報を保存しておく。
		逐次インスタンスを pickle 化することにより、次回起動時に前回の情報を引き継ぐ事ができる。
		これにより、同じ地震の情報を複数回送出してしまう事態を防止できる。
	"""
	def __init__(self, pickle_path: str = "") -> None:
		self.last_eq: datetime.datetime		= \
			datetime.datetime.now(datetime.timezone.utc)
		self.last_update: datetime.datetime	= \
			datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
		self.reqerr_count: int	= 0
		self.pkl_path: str		= pickle_path
		self.xmlid: str			= ""
		
	def PickleMyself(self):
		with open(self.pkl_path, "wb") as f:
			pickle.dump(self, f)

### class FeedControl END ###


def GetEntryList(root: Element, ns: dict) -> list:
	"""
		XML フィードから各項目情報を取得し、リストにまとめて返す。
		root: XML 全体を示すオブジェクト
		ns: XML 名前空間。config.json により規定される
	"""
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
	"""
		FeedControl に記録された XML の ID と 取得した XML フィードの ID を比較する。
		渡された XML の ID の方が新しければ FeedControl を更新して True を返す。
		root: XML 全体を示すオブジェクト
		feedctl: FeedControl クラス。 XML の ID 比較用
		ns: XML 名前空間。config.json により規定される
	"""
	current = root.find("atom:id", ns).text
	ret = True if current == feedctl.xmlid else False

	feedctl.xmlid = current
	return ret

def OnRequestException(feedctl: FeedControl, config: dict, logger: log.Logger, e: Exception) -> None:
	"""
		気象庁 XML の取得に何らかの理由により失敗した場合に呼び出される。
		feedctl: FeedControl クラス。連続エラー回数を記録するために使用
		config: config.json からの設定情報
		logger: ロギングハンドラ
		e: 発生した例外に関する情報
	"""
	logger.warning("地震情報の取得に失敗しました")
	logger.warning(e)
	feedctl.reqerr_count += 1

	if feedctl.reqerr_count % config["xmlfeed"]["request"]["error_count"] == 0:
		logger.error(f"地震情報の取得に{feedctl.reqerr_count}回連続で失敗しました。ログを確認してください。")

def GetJMAXMLFeed_Eqvol(feedctl: FeedControl, ns: dict, config: dict, logger: log.Logger) -> None:
	"""
		気象庁 XML フィードから地震火山情報を取得し、地震に関する情報を抜き出す。
		抜き出したエントリは EQPlotter クラスに渡され震度地図を描画、返された地図をポストする。
		I-Maplot の中枢を担う部分。
		feedctl: FeedControl クラス。フィードの取得により適宜更新されていく
		ns: XML 名前空間。XML からの情報取得に使用
		config: config.json からの設定情報
		logger: ロギングハンドラ
	"""
	try:
		# 最終更新時刻以降の情報を（あれば）返すよう HTTP ヘッダに記載する。
		# 更新がない場合、HTTP 304 と共に長さ 0 のデータが返るので無駄なダウンロードを節約することができる。
		header = { "If-Modified-Since": feedctl.last_update.strftime("%a, %d %b %Y %H:%M:%S GMT") }
		response = requests.get(config["xmlfeed"]["request"]["address"], headers=header)
		response.raise_for_status()
	except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
		OnRequestException(feedctl, config, logger, e)
	else:
		# 更新がない場合（HTTP 304）は読み飛ばす
		print(response.status_code, feedctl.last_update)
		if response.status_code == 200:
			feedctl.reqerr_count = 0
			response.encoding = response.apparent_encoding
			xml = ElementTree.fromstring(response.text)

			# XML フィードの最終更新時刻を更新する
			# 時刻情報は JST で記載されているので UTC（GMT）に変換する。
			updated = xml.find("atom:updated", ns)
			dt = datetime.datetime.fromisoformat(updated.text)
			feedctl.last_update = dt.astimezone(datetime.timezone.utc)
			
			if CheckId(xml, feedctl, ns) is not True:
				# 「震度に関する情報」と「震源・震度に関する情報」を抜き出す
				# 「震源に関する情報」は、直後に震度と一緒に情報が再送されるため無視する
				lsentry = GetEntryList(xml, ns)
				lsentry = sorted(
					[l for l in lsentry if "震度" in l.title and l.updated_time > feedctl.last_eq],
					key=lambda x: x.updated_time
				)
				if len(lsentry) > 0:
					feedctl.last_eq = max(lsentry, key=lambda x: x.updated_time).updated_time

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
					
					collect()
			else:
				logger.debug("地震情報：新しい地震の情報はありません")
		else:
			logger.debug("地震情報：新しい地震の情報はありません")
	finally:
		feedctl.PickleMyself()

def SendMail_SystemStop(mhd: log.MailHandler) -> None:
	"""
		システム終了時にメールを送信する。
		mhd: メールによるロギング ハンドラー
	"""
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

		interval_sec: int = conf["interval_sec"]
		feedctl_path: str = conf["paths"]["feedctl"]
		output_path: str  = conf["paths"]["output"]
		ns: dict	= conf["xmlfeed"]["xml_ns"]["feed"]

		# ソケット（exit, alive）関連情報
		sockinfo: dict	= conf["sockinfo"]
		codeinfo: dict	= sockinfo["code"]
		req: dict	= sockinfo["request"]
		ans: dict	= sockinfo["answer"]

		# FeedControl の読み込み
		try:
			with open(feedctl_path, "rb") as f:
				feedctl = pickle.load(f)
				feedctl.pkl_path = feedctl_path
		except FileNotFoundError:
			logger.warning("FeedControl が見つかりませんでした。作成します。")
			feedctl = FeedControl(feedctl_path)
		
		# 画像出力先の存在確認（存在しない場合は作成）
		if not os.path.isdir(output_path):
			logger.warning(f"画像出力先 {output_path} が見つかりませんでした。作成します。")
			os.mkdir(output_path)

		# デフォルトのタイムアウト時間を設定
		setdefaulttimeout(conf["sockinfo"]["timeout_sec"])

		# このコマンド受付ソケットだけは無限に待ち受け状態（ブロッキング状態、タイムアウトなし）
		sock_req = socket(AF_INET, SOCK_STREAM)
		sock_req.settimeout(None)
		sock_req.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		sock_req.bind((req["host"], req["port"]))
		sock_req.listen()

		# interval_sec 秒おきに GetJMAXMLFeed_Eqvol 関数を実行
		sched = Scheduler(
			interval_sec,
			GetJMAXMLFeed_Eqvol,
			(feedctl, ns, conf, logger)	# 実行する関数に渡す引数のリスト
		)
		sched.start()

		while True:
			try:
				# exit, alive からの接続を受け付ける
				conn, _ = sock_req.accept()
				data = conn.recv(sockinfo["max_len"])
				conn.close()

				# メッセージ種別、メッセージ内容を解析
				code, bmsg = struct.unpack("b" + str(len(data) - 1) + "s", data)
				msg = bmsg.decode(sockinfo["charset"])

				# alive -> 生存の表示としてメッセージを送り返す
				if code == codeinfo["alive"]:
					time.sleep(0.5)	# alive 側の受信ソケット準備が完了するまでのパディングを入れてみた
					sock_ans = socket(AF_INET, SOCK_STREAM)
					sock_ans.connect((ans["host"], ans["port"]))

					msg = ans["default_msg"]["alive"].encode(sockinfo["charset"])
					data = struct.pack("b" + str(len(msg)) + "s", code, msg)

					sock_ans.send(data)
					sock_ans.close()

				# exit -> プログラム終了
				elif code == codeinfo["exit"]:
					if len(msg) > 0:
						logger.error(msg + " - message on EXIT")
					break
	
			except struct.error as e:
				logger.info(e)
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