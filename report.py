# coding: utf-8
import os
import datetime
import pickle
import cv2
import numpy as np
import json

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from xml.etree import ElementTree
from decimal import Decimal
from collections import Counter
from pandas import read_pickle

from eqinfo import EQInfo


### class EQPlotter BEGIN ###

class EQPlotter:
	"""
		震度地図を描画する。
		I-Maplot の根幹を担う部分
	"""
	def __init__(self, config: dict) -> None:
		"""
			コンストラクタ
			config: config.json に規定された設定情報。LoadConfig 関数にわたす
		"""
		self.eqi_: EQInfo = EQInfo(config)
		self.fhypocenter_: bool = False
		self.assistant_ = None
		self.fig_ = None
		self.ax_ = None
		self.img_base_ = None

		self.LoadConfig(config)
		self._LoadAssistantData()
		self._PrepareFigure()

	def LoadConfig(self, config: dict) -> None:
		"""
			設定情報をメンバ変数に設定する。
			config: config.json に規定された設定情報
		"""
		self.assistant_path_: str = config["paths"]["assistant"]
		self.areamap_path_: str = config["paths"]["areamap"]
		self.images_path_: str = config["paths"]["images"]
		self.output_path_: str = config["paths"]["output"]
		self.ns_: dict = config["xmlfeed"]["xml_ns"]["report"]

	def ParseXML(self, xml: str):
		"""
			地震に関する情報（XML 電文）を解析してメンバ変数に格納する。
			xml: XML 電文の文字列
		"""
		ns_report = self.ns_["report"]
		ns_head = self.ns_["head"]
		ns_body = self.ns_["body"]

		# 電文は Control, Head, Body 部からなる
		root = ElementTree.fromstring(xml)
		Ctrl = root.find("atom:Control", ns_report)
		Head = root.find("atom:Head", ns_head)
		Body = root.find("atom:Body", ns_body)

		# 「震度速報」／「震源・震度に関する情報」を判別する
		Title = Ctrl.find("atom:Title", ns_report)
		self.fhypocenter_ = True if "震源" in Title.text else False

		OriginTime = Body.find(".//atom:OriginTime", ns_body)

		# （推定）地震発生時刻の取り出し
		if OriginTime is None:
			TargetTime = Head.find(".//atom:TargetDateTime", ns_head)
			self.eqi_.origin_dt = datetime.datetime.fromisoformat(TargetTime.text)
		else:
			self.eqi_.origin_dt = datetime.datetime.fromisoformat(OriginTime.text)

		# 固定付加文の取得。文はパターン化されておりコードで識別することができる
		ForecastComment = Body.findall(".//atom:ForecastComment[@codeType='固定付加文']", ns_body)
		for c in ForecastComment:
			Code = c.find(".//atom:Code", ns_body)
			if Code is not None:
				self.eqi_.code = Code.text.split()
		
		# 震源情報がある場合、その座標や深さ、マグニチュードを取得する
		if self.fhypocenter_:
			Coordinate = Body.find(".//jmx_eb:Coordinate", ns_body)
			Hypocenter = Body.find(".//atom:Hypocenter/atom:Area/atom:Name", ns_body)
			self.eqi_.ParseHypocenter(Coordinate.text)
			self.eqi_.hypocenter = Hypocenter.text

			Magnitude = Body.find(".//jmx_eb:Magnitude", ns_body)
			self.eqi_.magnitude = float(Magnitude.text)

		# 震度情報リストの取得
		Intensity = Body.find(".//atom:Intensity/atom:Observation", ns_body)
		CodeType = Intensity.findall(".//atom:CodeDefine/atom:Type", ns_body)

		# 震度情報を１つずつ解析してクラスに格納していく
		for n in CodeType:
			xpath = n.attrib['xpath']
			path_split = xpath.split('/')
			path_split.pop()
			split_new = ["atom:" + x for x in path_split]
			newpath = "/".join(split_new)

			Area = Intensity.findall(newpath, ns_body)
			lsint = []

			for a in Area:
				name = a.find("atom:Name", ns_body)
				maxint = a.find("atom:MaxInt", ns_body)
				if maxint is not None:
					lsint.append((name.text, maxint.text))
			
			if   "都道府県" in n.text:
				self.eqi_.intensity_pref.AddIntensity(lsint)
			elif "細分区域" in n.text:
				self.eqi_.intensity_area.AddIntensity(lsint)
			elif   "市町村" in n.text:
				self.eqi_.intensity_city.AddIntensity(lsint)

	def _PrepareFigure(self) -> None:
		""" ベース地図を読み込む """
		with open(self.areamap_path_, "rb") as f:
			self.fig_ = pickle.load(f)
			self.ax_ = self.fig_.gca()

		self.fig_.set_size_inches(16, 9)

	def _LoadAssistantData(self) -> None:
		""" 補助情報（区域の重心、上下左右端座標等）を読み込む """
		self.assistant_ = read_pickle(self.assistant_path_)

	def GetMessage(self) -> str:
		"""
			メンバ変数に格納された情報から地震情報文を作成する。
		"""
		dt  = self.eqi_.origin_dt
		fdt = True if dt.hour < 12 else False
		rets = ""

		if self.fhypocenter_:
			# 震源・震度に関する情報
			rets += f"\n午{"前" if fdt else "後"}{dt.hour if fdt else dt.hour - 12}時{dt.minute}分ごろ地震がありました"

			if "0215" in self.eqi_.code:
				rets += f"\nこの地震による津波の心配はありません"
			
			rets += f"\n震源は{self.eqi_.hypocenter}"
			rets += f"\n深さ{self.eqi_.PrintDepth()}　マグニチュード{self.eqi_.magnitude}"
			rets += self.eqi_.intensity_city.PrintIntensity()
		else:
			# 震度速報
			rets += f"\n午{"前" if fdt else "後"}{dt.hour if fdt else dt.hour - 12}時{dt.minute}分ごろ"
			rets += f"\n{self.PrintRegion()}{self.eqi_.intensity_pref.PrintEQLevel()}地震がありました"
			
			if self.eqi_.intensity_pref.eqlevel > 1:
				rets += f"\n揺れが強かった沿岸部では念のため津波に注意してください"
			
			rets += self.eqi_.intensity_area.PrintIntensity()
		return rets

	def PrintRegion(self) -> str:
		"""
			（震度速報時に）地震のあった地方名を出力する。
		"""
		intensity = self.eqi_.intensity_area
		max_area = intensity.intensity[intensity.intensity_max]

		df = self.assistant_[self.assistant_["name"].isin(max_area)]
		c = Counter(df["region"].iloc)
		region = c.most_common()[0][0]

		return region + ("で" if len(region) > 0 else "")

	def DrawMap(self, bound_level: str="1") -> str:
		"""
			震度地図を描画する。
			bound_level: 描画に際して必ず含める震度
		"""
		self.ax_.axis("tight")
		self.ax_.axis("off")
		self.ax_.set_aspect("equal")

		# [min_x, min_y, max_x, max_y]
		max_bound = [0xffff, 0xffff, -0xffff, -0xffff]

		if self.fhypocenter_:
			max_bound = ExpandBound(max_bound, self.eqi_.longitude, self.eqi_.latitude, self.eqi_.longitude, self.eqi_.latitude)

		self.eqi_.intensity_area.bound_level = bound_level
		fbound = True

		for k, v in self.eqi_.intensity_area.intensity.items():
			if len(v) == 0: continue

			m = self.assistant_[self.assistant_["name"].isin(v)]

			# m["bounds"] 各行は csv 形式のテキスト
			# csv2tuple で tuple に変換して list にして格納
			# tuple -> (min_x, min_y, max_x, max_y)
			if fbound:
				bounds = np.array(list(map(lambda b: csv2tuple(b), m["bounds"]))).T
				max_bound = ExpandBound(max_bound, bounds[0].min(), bounds[1].min(), bounds[2].max(), bounds[3].max())
			
			if k == self.eqi_.intensity_area.bound_level: fbound = False

		# 16 : 9 に合わせて領域の切り取りが必要
		max_bound[0] -= 0.5
		max_bound[1] -= 0.5
		max_bound[2] += 0.5
		max_bound[3] += 0.5
		xdiff = max_bound[2] - max_bound[0]
		ydiff = max_bound[3] - max_bound[1]
		
		if ydiff > xdiff * 0.5625:
			# Y の大きさが 16:9 より大きいので、Y を基準に X を 16 に合うように拡張
			xdiff = ydiff * 1.7778 - xdiff
			max_bound[0] -= xdiff / 2
			max_bound[2] += xdiff / 2
		else:
			# Y の大きさが 16:9 より小さいので、X を基準に Y を 9 に合うように拡張
			ydiff = xdiff * 0.5625 - ydiff
			max_bound[1] -= ydiff / 2
			max_bound[3] += ydiff / 2

		self.ax_.set_xlim(max_bound[0], max_bound[2])
		self.ax_.set_ylim(max_bound[1], max_bound[3])

		# 一度地図を画像として出力し、震源と震度を乗せる
		tmppath = f"./{self.eqi_.origin_dt.strftime("%Y%m%d_%H%M%S")}_tmp.png"
		self.fig_.savefig(
			tmppath,
			facecolor="cornflowerblue",
			bbox_inches="tight",
			pad_inches=0,
			dpi=300
		)
		self.img_base_ = cv2.imread(tmppath)
		plt.close(self.fig_)

		# 震源の描画
		self.PlotHypocenter(self.eqi_.longitude, self.eqi_.latitude, tuple(max_bound), 0.45)
		# 震度の描画
		for k, v in self.eqi_.intensity_area.intensity.items():
			if len(v) == 0: continue

			m = self.assistant_[self.assistant_["name"].isin(v)]
			coords = list(map(lambda g: (g.x, g.y), m["centroid"]))
			self.PlotIntensity(coords, tuple(max_bound), k, 0.25)

		outpath = os.path.join(self.output_path_, f"{self.eqi_.origin_dt.strftime("%Y%m%d_%H%M%S")}.png")
		cv2.imwrite(outpath, self.img_base_)
		os.remove(tmppath)
		return outpath

	# x, y は画像としての座標 (px)
	def PlotImage(self, px: list, img_add) -> None:
		"""
			ベース地図に png 画像を重ね合わせる。
			px: 座標 (x, y) のリスト。同じ画像をまとめて描画可能
			img_add: 地図に重ねる画像 
		"""
		if (self.img_base_ is None) or (img_add is None): return

		bseh, bsew = self.img_base_.shape[:2]
		addh, addw = img_add.shape[:2]
		
		px = [(x, y) for x, y in px \
				if not(x + addw < 0 or y + addh < 0 or x > bsew or y > bseh)]
		for x, y in px:
			alpha_blend(self.img_base_, img_add, x, y)

	# x, y は地図としての座標 (lon, lat)
	def PlotHypocenter(self, lon, lat, bound: tuple, zoom=1.0) -> None:
		"""
			ベース地図に震源画像を描画する。
			lon: 経度
			lat: 緯度
			bound: 地図における上下左右端の緯度経度
			zoom: 画像を重ね合わせる際の倍率
		"""
		img_add = cv2.imread(os.path.join(self.images_path_, "hypocenter.png"), cv2.IMREAD_UNCHANGED)
		img_add = cv2.resize(img_add, dsize=None, fx=zoom, fy=zoom, interpolation=cv2.INTER_LINEAR)
		
		x, y = self.GeoCoord2Pixel(bound, lon, lat)
		cx, cy = GetCenterPixel(img_add)
		self.PlotImage([(x - cx, y - cy)], img_add)

	# x, y は地図としての座標 (lon, lat)
	def PlotIntensity(self, coords: list, bound: tuple, intensity: str, zoom=1.0) -> None:
		"""
			ベース地図に震度画像を描画する。
			coords: 緯度経度のリスト
			bound: 地図における上下左右端の緯度経度
			intensity: 描画する震度
			zoom: 画像を重ね合わせる際の倍率
		"""
		img_add = cv2.imread(os.path.join(self.images_path_, intensity+".png"), cv2.IMREAD_UNCHANGED)
		img_add = cv2.resize(img_add, dsize=None, fx=zoom, fy=zoom, interpolation=cv2.INTER_LINEAR)

		px = [self.GeoCoord2Pixel(bound, lon, lat) for lon, lat in coords]
		cx, cy = GetCenterPixel(img_add)
		self.PlotImage([(x - cx, y - cy) for x, y in px], img_add)
	
	def GeoCoord2Pixel(self, bound: tuple, lon: float, lat: float) -> tuple:
		"""
			緯度経度からピクセル座標に変換する。lon, lat を x, y のタプルにして返す。
			bound: 地図における上下左右端の緯度経度
			lon: 経度
			lat: 緯度
		"""
		if self.img_base_ is None: return (0, 0)

		lpx, lpy = GetLatLonperPixel(bound, self.img_base_)
		x = int(Decimal(str((lon - bound[0]) / lpx)).quantize(Decimal("0")))
		y = int(Decimal(str((bound[3] - lat) / lpy)).quantize(Decimal("0")))

		return (x, y)

### class EQPlotter END ###


### funcdef BEGIN ###

def GetLatLonperPixel(bound: tuple, img) -> tuple:
	"""
		1 ピクセルあたりの緯度経度の変化を計算する。1 ピクセルあたりの度数の変化量を x, y のタプルにして返す。
		bound: 地図における上下左右端の緯度経度
		img: 画像化されたベース地図
	"""
	if img is None: return (0, 0)

	hpx, wpx = img.shape[:2]
	hlt, wln = bound[3] - bound[1], bound[2] - bound[0]

	return (wln / wpx, hlt / hpx)

def GetCenterPixel(img) -> tuple:
	"""
		画像の中央座標を取得する
		img: 画像
	"""
	if img is None: return (0, 0)

	cx = int(Decimal(str(img.shape[1] / 2)).quantize(Decimal("0")))
	cy = int(Decimal(str(img.shape[0] / 2)).quantize(Decimal("0")))
	return (cx, cy)

def alpha_blend(img_base, img_add, x: int, y: int) -> None:
	"""
		参考 : https://qiita.com/smatsumt/items/923aefb052f217f2f3c5
		画像を重ね合わせる（アルファブレンド）。
		img_base: ベース画像
		img_add: 重ねる画像。アルファチャンネルを持っていなければならない
		x, y: 重ね合わせ位置。重ねる画像の左上端にここが来る 
	"""
	h, w = img_add.shape[:2]
	x0, y0 = max(x, 0), max(y, 0)
	x1, y1 = min(x + w, img_base.shape[1]), min(y + h, img_base.shape[0])
	ax0, ay0 = x0 - x, y0 - y
	ax1, ay1 = ax0 + x1 - x0, ay0 + y1 - y0

	img_base[y0:y1, x0:x1] = \
		img_base[y0:y1, x0:x1] * (1 - img_add[ay0:ay1, ax0:ax1, 3:] / 255) + \
		img_add[ay0:ay1, ax0:ax1, :3] * (img_add[ay0:ay1, ax0:ax1, 3:] / 255)

def csv2tuple(csv: str) -> tuple:
	return tuple(map(float, csv.split(",")))

# max_bound: [min_x, min_y, max_x, max_y]
def ExpandBound(max_bound: list, min_x: float, min_y: float, max_x: float, max_y: float) -> list:
	"""
		矩形と座標を比較し、矩形が拡大するように更新する。
		max_bound: 更新される図形
		min_x: 左
		min_y: 上
		max_x: 右
		max_y: 下
	"""
	max_bound[0] = min(min_x, max_bound[0])	# min_x
	max_bound[1] = min(min_y, max_bound[1])	# min_y
	max_bound[2] = max(max_x, max_bound[2])	# max_x
	max_bound[3] = max(max_y, max_bound[3])	# max_y
	return max_bound

### funcdef END ###

from sys import argv 

if __name__ == "__main__":
	if len(argv) >= 2:
		path = argv[1]

		with open("./config.json", "r", encoding="utf-8") as f:
			conf = json.load(f)
		
		with open(path, "r", encoding="utf-8") as f:
			xml = f.read()
		
		output_path = conf["paths"]["output"]

		if not os.path.isdir(output_path):
			print(f"{output_path} is not found. Now Making...")
			os.mkdir(output_path)
		
		eqp = EQPlotter(conf)
		eqp.ParseXML(xml)

		eqlevel = conf["eqlevel"]
		imax = eqp.eqi_.intensity_area.intensity_max
		eqp.DrawMap("3" if eqlevel[imax] >= 3 else "1")
		print(eqp.GetMessage())
	else:
		print("USAGE>python report.py [path_to_xml]")