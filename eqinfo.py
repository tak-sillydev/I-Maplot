# -*- coding: utf-8 -*-
# Python >= v3.7
import re
import log

from datetime import datetime

# 2  -> 強い地震
# 1  -> やや強い地震
# 0  -> 通常の地震
# -1 -> 使われない（番兵）

class IntensityHolder: 
	def __init__(self, config: dict) -> None:
		self.intensity: dict = {
			"7" : [],
			"6+": [],
			"6-": [],
			"5+": [],
			"5-": [],
			"4" : [],
			"3" : [],
			"2" : [],
			"1" : [],
			"-" : [], # intensity_max 用の番兵
		}
		self.intensity_max: str	= "-"
		self.bound_level: str	= "1"
		self.eqlevel: int		= -1
		self.eqlevel_config: dict	= config["eqlevel"]
		self.eqlevel_str: list		= config["level_str"]
	
	# list of tuple (name, intensity) 
	def AddIntensity(self, lsint: list) -> None:
		"""
			震度を self.intensity に追加する。
			lsint: （地域名, 震度）のタプルを要素として持つリスト
		"""
		if len(lsint) == 0: return

		for l in lsint:
			fmax = False	# fmax : intensity_max より小さい震度で最大震度が更新されてしまうことを防ぐ
			for k in self.intensity.keys():
				if self.intensity_max == k: fmax = True
				if l[1] == k:
					self.intensity[k].append(l[0])
					if not fmax:
						self.intensity_max = k
						self.eqlevel = self.eqlevel_config[k]
					break

	def PrintIntensity(self) -> str:
		"""
			self.intensity をもとに、震度情報文を出力する。
		"""
		f = True
		rets = ""

		for k, v in self.intensity.items():
			if len(v) == 0: continue
			if self.eqlevel >= 1 and self.eqlevel_config[k] == 0:	# v1.2 で削除予定
				continue

			k = k.replace("+", "強")
			k = k.replace("-", "弱")
			f = False
			rets += f'\n[震度{k}]　{" ".join(v)}'
		if f:
			rets += f"\n震度情報はありません"
		elif self.eqlevel >= 1:
			rets += f"\n震度3以上の地域についてお伝えしています。"
		return rets
	
	# "強い" / "やや強い" / ""
	def PrintEQLevel(self) -> str:
		""" 震度速報時に、最大震度からおおよその地震の大きさを出力する。 """
		return self.eqlevel_str[self.eqlevel]

class EQInfo:
	def __init__(self, config: dict) -> None:
		self.origin_dt: datetime	= None
		self.logger: log.Logger		= log.getLogger("{}.{}".format(config["app_name"], __name__))
		self.code: list	= None
		self.id: str	= ""

		# 震源に関する情報
		self.hypocenter: str	= ""
		self.latitude: float	= None
		self.longitude: float	= None
		self.magnitude: float	= None
		self.depth: int			= None

		# 震度に関する情報
		self.intensity_pref: IntensityHolder = IntensityHolder(config)
		self.intensity_area: IntensityHolder = IntensityHolder(config)
		self.intensity_city: IntensityHolder = IntensityHolder(config)

	def ParseHypocenter(self, s: str):
		"""
			震源の緯度経度、深さを解析する。
			s: 解析する文字列（Coordinate タグ）
		"""
		ls = re.findall("[+-][0-9.]+", s)
		try:
			self.latitude  = float(ls[0])
			self.longitude = float(ls[1])
			self.depth = int(ls[2]) / -1000
		except IndexError:
			self.logger.warning(f"Coordinate's length too fewer: {len(ls)}")

	def PrintDepth(self) -> str:
		"""
			震源の深さを出力する。
		"""
		if self.depth is None:
			return "不明"
		elif self.depth < 10:
			return "ごく浅い"
		elif self.depth >= 700:
			return str(int(self.depth)) + "キロ以上"
		else:
			return str(int(self.depth)) + "キロ"
