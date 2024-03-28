# -*- coding: utf-8 -*-
# 特定の関数を定期実行させる

import time
import threading
import log
import traceback

class Scheduler:
	"""
		Scheduler クラス
		callback に登録した特定の関数を、sec 秒おきに定期実行する。
	"""
	def __init__(self, sec: int, callback, args: tuple = None) -> None:
		self.timer_: threading.Timer	= None
		self.logger_: log.Logger		= log.getLogger(__name__)
		self.callback_		= callback
		self.sec_: int		= sec
		self.args_: tuple	= args
		self.fexec_: bool	= False

	def caller_(self) -> None:
		"""
			スケジューラによって呼び出される実際の関数。
			この関数内で、登録した関数（self.callback_）を呼び出している。
		"""
		try:
			base_time = time.time()
			next_time = 0

			# タイマーは一度破棄しておく（不具合の原因になるとか）
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
		except Exception:
			self.logger_.error(traceback.format_exc())
	
	def start(self) -> None:
		"""
			スケジューラを開始する。
			self.sec_ 秒後に self.caller_ を（別スレッドで）呼び出す。
		"""
		self.fexec_ = True
		self.timer_ = threading.Timer(self.sec_, self.caller_)
		self.timer_.daemon = True
		self.timer_.start()

		if isinstance(self.args_, tuple):
			self.callback_(*self.args_)
		else:
			self.callback_()

	def stop(self) -> None:
		"""
			スケジューラを停止する。
			この関数実行後は self.caller_ は呼び出されない（はず）。
		"""
		self.fexec_ = False

		if self.timer_ is not None:
			self.timer_.cancel()
