import datetime
import pickle

class FeedControl:
	"""
		I-Maplot を動かすにあたり必要な情報、特に地震情報の更新に関する情報を保存しておく。
		逐次インスタンスを pickle 化することにより、次回起動時に前回の情報を引き継ぐ事ができる。
		これにより、同じ地震の情報を複数回送出してしまう事態を防止できる。
	"""
	def __init__(self, pickle_path: str = "") -> None:
		self.system_start: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
		self.last_eq: datetime.datetime		 = datetime.datetime.now(datetime.timezone.utc)
		self.last_access: datetime.datetime	 = datetime.datetime.now(datetime.timezone.utc)
		self.last_update: datetime.datetime	 = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
		
		self.reqerr_count: int	= 0
		self.pkl_path: str		= pickle_path
		self.xmlid: str			= ""
		self.last_msg: str		= "地震情報はありません"
		
	def PickleMyself(self):
		with open(self.pkl_path, "wb") as f:
			pickle.dump(self, f)
