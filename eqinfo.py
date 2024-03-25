# -*- coding: utf-8 -*-
# Python >= v3.7
import re

from datetime import datetime

# 2  -> 強い地震
# 1  -> やや強い地震
# 0  -> 通常の地震
# -1 -> 使われない（番兵）

class IntensityHolder:
	intensity_max: str	= "-"
	intensity: dict		= None
	bound_level: str	= "1"
	eqlevel: int		= -1

	eqlevel_config: dict	= None
	eqlevel_str: list	= None
 
	def __init__(self, config: dict) -> None:
		self.intensity = {
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
		self.eqlevel_config = config["eqlevel"]
		self.eqlevel_str = config["level_str"]
	
	# list of tuple (name, intensity) 
	def AddIntensity(self, lsint: list) -> None:
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
		f = True
		rets = ""

		for k, v in self.intensity.items():
			if len(v) == 0: continue
			if self.eqlevel >= 1 and self.eqlevel_config[k] == 0:
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
		return self.eqlevel_str[self.eqlevel]

class EQInfo:
	id: str		= ""
	code: list	= None
	origin_dt: datetime	= None

	# 震源に関する情報
	hypocenter: str		= ""
	latitude: float		= None
	longitude: float	= None
	magnitude: float	= None
	depth: int	= None

	# 震度に関する情報
	intensity_pref: IntensityHolder = None
	intensity_area: IntensityHolder = None
	intensity_city: IntensityHolder = None

	def __init__(self, config: dict) -> None:
		self.intensity_pref = IntensityHolder(config)
		self.intensity_area = IntensityHolder(config)
		self.intensity_city = IntensityHolder(config)

	def ParseHypocenter(self, s: str):
		ls = re.findall("[+-][0-9.]+", s)
		try:
			self.latitude  = float(ls[0])
			self.longitude = float(ls[1])
			self.depth = int(ls[2]) / -1000
		except IndexError:
			pass

	def PrintDepth(self) -> str:
		if self.depth is None:
			return "不明"
		elif self.depth < 10:
			return "ごく浅い"
		elif self.depth >= 700:
			return str(int(self.depth)) + "キロ以上"
		else:
			return str(int(self.depth)) + "キロ"
