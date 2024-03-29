# -*- coding: utf-8 -*-
# 簡易ログシステム
# 参照：https://note.com/yucco72/n/n11e9be3cf541

import smtplib
import os
import json

from logging import getLogger, handlers, Formatter, Logger, ERROR
from email.mime.text import MIMEText
from email.utils import formatdate


### class MailHandler BEGIN ###

class MailHandler:
	subject: str = "I-Maplot システム動作通知"

	def __init__(self, config_path: str, conf_enctype: str = "utf-8") -> None:
		with open(config_path, "r", encoding=conf_enctype) as f:
			conf = json.load(f)
			self.server_addr: str	= conf["mailinfo"]["server"]["addr"]
			self.server_port: str	= conf["mailinfo"]["server"]["port"]
			self.addr_to: str	= conf["mailinfo"]["addr_to"]
			self.addr_from: str	= conf["mailinfo"]["addr_from"]
			self.password: str	= conf["mailinfo"]["password"]

	def send(self, body: str) -> None:
		SendMail(
			self.server_addr, self.server_port,
			self.addr_from, self.addr_to,
			self.addr_from, self.password,
			self.subject, body
		)

### class MailHandler END ###


### class TLS_SMTPHandler BEGIN ###

class TLS_SMTPHandler(handlers.SMTPHandler):
	"""
		デフォルトの logging.SMTPHandler は Gmail の SMTP に対応していない（TLS 認証がない）
		なので、クラスを継承、ログ送出関数（emit）をオーバーライド
		参考 : https://qiita.com/ryoheiszk/items/8b072adeb368cc35588d
	"""
	def emit(self, record):
		for toaddr in self.toaddrs:
			SendMail(
				self.mailhost, self.mailport,
				self.fromaddr, toaddr,
				self.username, self.password,
				self.getSubject(record), self.format(record)
			)

### class TLS_SMTPHandler END ###


def SendMail(
		server_addr: str, server_port: int, addr_from: str,
		addr_to: str, cred_addr: str, password: str, subject: str, body: str) -> None:
	"""
		SMTP（TLS対応）を使用してメールを送信する。
		server_addr / server_port: SMTP 取り扱いサーバアドレス及びポート
		addr_from / addr_to:  メール送信元／先アドレス
		cred_addr / password: ログイン用ユーザ名（アドレス）及びパスワード
		subject: メールのタイトル
		body:    本文
	"""
	smtpobj = smtplib.SMTP(server_addr, server_port)
	smtpobj.starttls()
	smtpobj.login(cred_addr, password)

	message = MIMEText(body)
	message["Subject"] = subject
	message["From"] = addr_from
	message["To"] = addr_to
	message["Date"] = formatdate()

	smtpobj.send_message(message)
	smtpobj.close()

def set_logger(level: int, mhd: MailHandler, config: dict) -> None:
	"""
		全体（ルート）のログ設定。
		ファイルに書き出す。ログが 100 KB 溜まったらバックアップにして新しいファイルを作る。
		ERROR 以上のレベルはメールにて送信する。
		level: 出力レベル。DEBUG, INFO, WARNING, ERROR, CRITICAL のいずれか
		mhd:   メール送信ハンドラ。事前に送信先を設定しておく必要あり。
		config: config.json から得た設定情報
	"""
	logdir  = config["paths"]["log"]["dir"]
	logfile = config["paths"]["log"]["file"]
	
	logger_approot = getLogger(config["app_name"])
	logger_approot.setLevel(level)

	# filename, mode, maxBytes, backupCount, encoding
	rotating_handler_args = (os.path.join(logdir, logfile), "a", 100 * 1024, 3, "utf-8")

	try:
		rotating_handler = handlers.RotatingFileHandler(*rotating_handler_args)
	except FileNotFoundError:
		os.mkdir(logdir)
		with open(os.path.join(logdir, logfile), "w"): pass
		rotating_handler = handlers.RotatingFileHandler(*rotating_handler_args)

	# アーカイブ機能付き ファイル ロギングハンドラ
	format = Formatter("%(asctime)s : [%(levelname)s] in %(filename)s - %(message)s")
	rotating_handler.setFormatter(format)
	rotating_handler.setLevel(level)
	logger_approot.addHandler(rotating_handler)

	# メール ロギングハンドラ
	smtp_handler = TLS_SMTPHandler(
		mailhost=(mhd.server_addr, mhd.server_port),
		fromaddr=mhd.addr_from,
		toaddrs=mhd.addr_to,
		subject="I-Maplot ERROR log",
		credentials=(mhd.addr_from, mhd.password)
	)
	format = Formatter("%(asctime)s : [%(levelname)s]\nFrom %(filename)s -\n%(message)s")
	smtp_handler.setLevel(ERROR)
	smtp_handler.setFormatter(format)
	logger_approot.addHandler(smtp_handler)
	return
