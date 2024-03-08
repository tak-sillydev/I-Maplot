# -*- coding: utf-8 -*-
# 特定の関数を定期実行させる

import time
import threading
import log

class Scheduler:
	"""
		Scheduler クラス
		callback に登録した特定の関数を、sec 秒おきに定期実行する。
	"""
	callback_		= None	# callback function
	timer_: threading.Timer = None
	sec_: int		= 0xffffffff
	fexec_: bool	= False
	args_: tuple	= None
	logger_: log.Logger = None

	def __init__(self, sec: int, callback, args: tuple = None) -> None:
		self.sec_ = sec
		self.callback_ = callback
		self.args_ = args
		self.logger_ = log.getLogger(__name__)

	def caller_(self) -> None:
		try:
			base_time = time.time()
			next_time = 0

			if self.timer_ is not None:
				self.timer_.cancel()
				del self.timer_

			if self.fexec_:
				# 負数の余りは正になる
				next_time = ((base_time - time.time()) % self.sec_) or self.sec_
				self.timer_ = threading.Timer(next_time, self.caller_)
				self.timer_.daemon = True
				self.timer_.start()

				if isinstance(self.args_, tuple):
					self.callback_(*self.args_)
				else:
					self.callback_()
		except Exception as e:
			self.logger_.error(e)
	
	def start(self) -> None:
		self.fexec_ = True
		self.timer_ = threading.Timer(self.sec_, self.caller_)
		self.timer_.daemon = True
		self.timer_.start()

		if isinstance(self.args_, tuple):
			self.callback_(*self.args_)
		else:
			self.callback_()

	def stop(self) -> None:
		self.fexec_ = False

		if self.timer_ is not None:
			self.timer_.cancel()
