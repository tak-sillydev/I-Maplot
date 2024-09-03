# -*- coding: utf-8 -*-
# Python >= v3.7
import re
import log

# 2  -> 強い地震
# 1  -> やや強い地震
# 0  -> 通常の地震
# -1 -> 使われない（番兵）

class IntensityHolder:
	""" 震度情報を格納する """
	def __init__(self, config: dict) -> None:
		self.intensity: dict = {
			"7" : [],	"6+": [],	"6-": [],	"5+": [],	"5-": [],
			"4" : [],	"3" : [],	"2" : [],	"1" : [],	"-" : [], # intensity_max 用の番兵
		}
	
	def AddIntensity(self, intensity: str, name: str):
		self.intensity[intensity].append(name)

	def PrintIntensity(self) -> str:
		""" self.intensity をもとに、震度情報文を出力する。 """
		f = True
		rets = ""

		for k, v in self.intensity.items():
			if len(v) == 0: continue

			k = k.replace("+", "強")
			k = k.replace("-", "弱")
			f = False
			rets += f'\n[震度{k}]　{" ".join(v)}'
		if f:
			rets += f"\n震度情報はありません"
		return rets

class HypocenterHolder:
	""" 震源情報を格納する """
	def __init__(self, config: dict) -> None:
		self.logger: log.Logger	= log.getLogger("{}.{}".format(config["app_name"], __name__))

		# 震源に関する情報
		self.name: str			= ""
		self.depth: int			= None
		self.latitude: float	= None
		self.longitude: float	= None
		self.magnitude: float	= None

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
		""" 震源の深さを出力する。 """
		if self.depth is None:	return "不明"
		elif self.depth < 10:	return "ごく浅い"
		elif self.depth >= 700:	return str(int(self.depth)) + "キロ以上"
		else:					return str(int(self.depth)) + "キロ"
