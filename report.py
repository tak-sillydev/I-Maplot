# coding: utf-8
import os
import datetime
import pickle
import cv2
import numpy as np
import json

from matplotlib.figure import Figure
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
plt.switch_backend("Agg")

from xml.etree import ElementTree as ET
from decimal import Decimal
from collections import Counter
from pandas import read_pickle, DataFrame

from eqinfo import IntensityHolder, HypocenterHolder

### class EQPlotter BEGIN ###

class EQPlotterBase:
	"""
		震度地図の描画機能のみを提供する。
		XMLの解析等はサブクラスにて担当し、このクラスではすでに整理された情報のみを受け取る。
		I-Maplot の根幹を担う部分
	"""
	def __init__(self, config: dict) -> None:
		"""
			コンストラクタ
			config: config.json に規定された設定情報。LoadConfig 関数にわたす
		"""
		# 設定情報の読み込み
		self.LoadConfig(config)

		self.__img_base: cv2.typing.MatLike  = None
		self.__raster_img_path: str = ""
		self.__bound: list = [0xffff, 0xffff, -0xffff, -0xffff]

		# 地図データ（Created by makemap.py）の読み込み
		with open(config["paths"]["areamap"], "rb") as f:
			self.__fig: Figure = pickle.load(f)
		
		self.__ax: Axes = self.__fig.gca()
		self.__ax.axis("tight")				# よくわからん
		self.__ax.axis("off")				# 軸の表示を行わない
		self.__ax.set_aspect("equal")		# 縦横軸の比率が等しくなるように
		self.__fig.set_size_inches(16, 9)	# キャンバス比率を 16:9 に

		# 地図描画補助情報の読み込み
		self.assistant: DataFrame = read_pickle(config["paths"]["assistant"])

	def LoadConfig(self, config: dict) -> None:
		"""
			設定情報をメンバ変数に設定する。
			config: config.json に規定された設定情報
		"""
		self.__output_path: str    = config["paths"]["output"]
		self.images_path: str    = config["paths"]["images"]
		self.backcolor: str = config["makemap"]["areamap"]["color"]["back"]
		self.ns: dict      = config["xmlfeed"]["xml_ns"]["report"]

	def XMLSplitRoot(self, xml: str) -> tuple[ET.Element | None, ET.Element | None, ET.Element | None]:
		root = ET.fromstring(xml)
		ctrl = root.find("atom:Control", self.ns["report"])
		head = root.find("atom:Head", self.ns["head"])
		body = root.find("atom:Body", self.ns["body"])
		return (ctrl, head, body)

	def Rasterize(self) -> str:
		if self.__img_base is not None:	return

		# 16 : 9 に合わせて領域の切り取りが必要
		self.__bound[0] -= 0.5
		self.__bound[1] -= 0.5
		self.__bound[2] += 0.5
		self.__bound[3] += 0.5
		xdiff = self.__bound[2] - self.__bound[0]
		ydiff = self.__bound[3] - self.__bound[1]
		
		if ydiff > xdiff * 0.5625:
			# Y の大きさが 16:9 より大きいので、Y を基準に X を 16 に合うように拡張
			xdiff = ydiff * 1.7778 - xdiff
			self.__bound[0] -= xdiff / 2
			self.__bound[2] += xdiff / 2
		else:
			# Y の大きさが 16:9 より小さいので、X を基準に Y を 9 に合うように拡張
			ydiff = xdiff * 0.5625 - ydiff
			self.__bound[1] -= ydiff / 2
			self.__bound[3] += ydiff / 2

		self.__ax.set_xlim(self.__bound[0], self.__bound[2])
		self.__ax.set_ylim(self.__bound[1], self.__bound[3])

		self.__raster_img_path = "./temporary.png"
		self.__fig.savefig(
			self.__raster_img_path,
			facecolor=self.backcolor,
			bbox_inches="tight",
			pad_inches=0,
			dpi=300
		)
		self.__img_base = cv2.imread(self.__raster_img_path)
		plt.close(self.__fig)

		return self.__raster_img_path

	# x, y は画像としての座標 (px)
	def PlotImage(self, px: list, img_add: cv2.typing.MatLike) -> None:
		"""
			ベース地図に png 画像を重ね合わせる。
			px: 座標 (x, y) のリスト。同じ画像をまとめて描画可能
			img_add: 地図に重ねる画像 
		"""
		if (self.__img_base is None) or (img_add is None): return

		bseh, bsew = self.__img_base.shape[:2]
		addh, addw = img_add.shape[:2]
		
		px = [(x, y) for x, y in px \
				if not(x + addw < 0 or y + addh < 0 or x > bsew or y > bseh)]
		for x, y in px:
			alpha_blend(self.__img_base, img_add, x, y)
	
	def OutputImage(self, eq_time: datetime.datetime) -> str:
		""" 画像をファイルに出力する """
		outpath = os.path.join(self.__output_path, f"{eq_time.strftime("%Y%m%d_%H%M%S")}.png")
		cv2.imwrite(outpath, self.__img_base)
		os.remove(self.__raster_img_path)
		return outpath
	
	# max_bound: [min_x, min_y, max_x, max_y]
	def ExpandMapBound(self, min_x: float, min_y: float, max_x: float, max_y: float) -> list:
		"""
			地図の描画矩形と座標を比較し、矩形が拡大するように更新する。
			min_x: 左
			min_y: 上
			max_x: 右
			max_y: 下
		"""
		self.__bound[0] = min(min_x, self.__bound[0])	# min_x
		self.__bound[1] = min(min_y, self.__bound[1])	# min_y
		self.__bound[2] = max(max_x, self.__bound[2])	# max_x
		self.__bound[3] = max(max_y, self.__bound[3])	# max_y
		return self.__bound

	def GeoCoord2Pixel(self, lon: float, lat: float) -> tuple:
		"""
			地図データ上の緯度経度をラスタ画像上のピクセル座標に変換する。lon, lat を x, y のタプルにして返す。
			lon: 経度
			lat: 緯度
		"""
		if self.__img_base is None: return (0, 0)

		lpx, lpy = GetLatLonperPixel(self.__bound, self.__img_base)
		x = int(Decimal(str((lon - self.__bound[0]) / lpx)).quantize(Decimal("0")))
		y = int(Decimal(str((self.__bound[3] - lat) / lpy)).quantize(Decimal("0")))

		return (x, y)

### class EQPlotterBase END ###

### class Hypocenter_Plotter BEGIN ###

class Hypocenter_Plotter(EQPlotterBase):
	"""
		震源の描画機能を提供するクラス。
	"""
	def __init__(self, config: dict) -> None:
		super().__init__(config)
		self.hypocenter = HypocenterHolder(config)

	def SetMapBounds(self):
		""" 地図の描画範囲を決定する。 """
		lon = self.hypocenter.longitude
		lat = self.hypocenter.latitude
		self.ExpandMapBound(lon, lat, lon, lat)
	
	# x, y は地図としての座標 (lon, lat)
	def PlotHypocenter(self, zoom: float=1.0) -> None:
		"""
			ベース地図に震源画像を描画する。
			zoom: 画像を重ね合わせる際の倍率
		"""
		# Matplotlib 形式の地図を画像化してから画像を載せる
		self.Rasterize()
		
		img_add = cv2.imread(os.path.join(self.images_path, "hypocenter.png"), cv2.IMREAD_UNCHANGED)
		img_add = cv2.resize(img_add, dsize=None, fx=zoom, fy=zoom, interpolation=cv2.INTER_LINEAR)
		longitude = self.hypocenter.longitude
		latitude  = self.hypocenter.latitude
		
		if not(longitude is None or latitude is None):
			x, y = self.GeoCoord2Pixel(longitude, latitude)
			cx, cy = GetCenterPixel(img_add)
			self.PlotImage([(x - cx, y - cy)], img_add)

### class Hypocenter_Plotter END ###

### class Intensity_Plotter BEGIN ###

class Intensity_Plotter(EQPlotterBase):
	"""
		震度の描画機能を提供するクラス。
	"""
	def __init__(self, config: dict) -> None:
		super().__init__(config)
		self.intensity = IntensityHolder(config)

	def SetMapBounds(self, plot_level: str):
		""" 地図の描画範囲を決定する。 """
		fbound = True
		for k, v in self.intensity.intensity.items():
			if len(v) == 0: continue

			m = self.assistant[self.assistant["name"].isin(v)]

			# m["bounds"] 各行は csv 形式のテキスト
			# csv2tuple で tuple に変換して list にして格納
			# tuple -> (min_x, min_y, max_x, max_y)
			if fbound:
				bounds = np.array(list(map(lambda b: csv2tuple(b), m["bounds"]))).T
				self.bound = self.ExpandMapBound(bounds[0].min(), bounds[1].min(), bounds[2].max(), bounds[3].max())
			
			if k == plot_level: fbound = False

	def PlotIntensity(self):
		""" IntensityHolder から震度情報を取り出して描画する。 """
		self.Rasterize()

		for k, v in self.intensity.intensity.items():
			if len(v) == 0: continue

			m = self.assistant[self.assistant["name"].isin(v)]
			coords = list(map(lambda g: (g.x, g.y), m["centroid"]))
			self.PlotIntensity2(coords, k, 0.25)
		
	# x, y は地図としての座標 (lon, lat)
	def PlotIntensity2(self, coords: list[tuple[float, float]], intensity: str, zoom: float=1.0) -> None:
		"""
			ベース地図に指定した震度の震度画像を描画する。
			coords: 緯度経度のリスト
			intensity: 描画する震度
			zoom: 画像を重ね合わせる際の倍率
		"""
		img_add = cv2.imread(os.path.join(self.images_path, intensity+".png"), cv2.IMREAD_UNCHANGED)
		img_add = cv2.resize(img_add, dsize=None, fx=zoom, fy=zoom, interpolation=cv2.INTER_LINEAR)

		# 緯度経度のリストをピクセル座標のリストに変換する
		px = [self.GeoCoord2Pixel(lon, lat) for lon, lat in coords]
		cx, cy = GetCenterPixel(img_add)
		self.PlotImage([(x - cx, y - cy) for x, y in px], img_add)
		return

### class Intensity_Plotter END ###

### class EQPlotter_VXSE51 BEGIN ###

class EQPlotter_VXSE51(Intensity_Plotter):
	""" VXSE51（震度速報）用の電文解析・地図描画クラス """
	def __init__(self, config) -> None:
		super().__init__(config)
		self.eq_time: datetime.datetime = None
		self.max_int: str = "-"
		self.streqlv: str = config["level_str"]
		self.eqlevel: dict = config["eqlevel"]
	
	def PrintRegion(self) -> str:
		""" 地震のあった地方名を出力する。 """
		max_area: list = self.intensity.intensity[self.max_int]

		df = self.assistant[self.assistant["name"].isin(max_area)]
		c = Counter(df["region"].iloc)
		region = c.most_common()[0][0]

		return region + ("で" if len(region) > 0 else "")
	
	def GetMessage(self) -> str:
		""" 震度速報文の出力 """
		dt   = self.eq_time
		fdt	 = True if dt.hour < 12 else False
		rets = ""

		rets += f"\n午{"前" if fdt else "後"}{dt.hour if fdt else dt.hour - 12}時{dt.minute}分ごろ"
		rets += f"\n{self.PrintRegion()}{self.streqlv[self.eqlevel[self.max_int]]}地震がありました"
		
		if self.eqlevel[self.max_int] > 1:
			rets += f"\n揺れが強かった沿岸部では念のため津波に注意してください"
		
		rets += self.intensity.PrintIntensity()
		return rets
	
	def ParseXML(self, xml: str) -> None:
		""" XML (VXSE51) の解析を行う """
		# xml_ の接頭辞がついている変数は XML の要素を扱うものであるとみなす
		xml_ctrl, xml_head, xml_body = self.XMLSplitRoot(xml)

		# XMLが正常にパースできない場合は終了
		if xml_ctrl is None or xml_head is None or xml_body is None:
			return

		# InfoKind が「震度速報」でない場合は終了
		xml_infokind = xml_head.find(".//atom:InfoKind", self.ns["head"])
		if xml_infokind.text != "震度速報": return

		# 地震発生時刻の取得
		xml_target_time = xml_head.find(".//atom:TargetDateTime", self.ns["head"])
		self.eq_time = datetime.datetime.fromisoformat(xml_target_time.text)

		# 観測最大震度の取得
		xml_observation = xml_body.find(".//atom:Intensity/atom:Observation", self.ns["body"])
		xml_max_int = xml_observation.find("./atom:MaxInt", self.ns["body"])
		self.max_int = xml_max_int.text

		# 震度情報（細分区域）の取得
		xml_arealist = xml_observation.findall("./atom:Pref/atom:Area", self.ns["body"])
		for xml_area in xml_arealist:
			xml_areaname  = xml_area.find("./atom:Name",   self.ns["body"])
			xml_intensity = xml_area.find("./atom:MaxInt", self.ns["body"])
			self.intensity.AddIntensity(xml_intensity.text, xml_areaname.text)

	def DrawMap(self, plot_level: str="1") -> str:
		""" 震度地図の描画 """
		self.SetMapBounds(plot_level)
		self.PlotIntensity()
		outpath = self.OutputImage(self.eq_time)
		return outpath
	
### class EQPlotter_VXSE51 END ###

### class EQPlotter_VXSE53 BEGIN ###

class EQPlotter_VXSE53(Hypocenter_Plotter, Intensity_Plotter):
	""" VXSE53（震源・震度に関する情報）用の電文解析・地図描画クラス """
	def __init__(self, config: dict) -> None:
		super().__init__(config)
		self.eq_time: datetime.datetime = None
		self.intensity_city = IntensityHolder(config)
		self.codelist: list[str] = []
		self.max_int: str = "-"

	def GetMessage(self) -> str:
		"""
			メンバ変数に格納された情報から地震情報文を作成する。
		"""
		dt  = self.eq_time
		fdt = True if dt.hour < 12 else False

		rets = f"\n午{"前" if fdt else "後"}{dt.hour if fdt else dt.hour - 12}時{dt.minute}分ごろ地震がありました"

		if "0215" in self.codelist:
			rets += f"\nこの地震による津波の心配はありません"
		elif "0211" in self.codelist:
			rets += f"\nこの地震により、津波警報／注意報が発表されています"
		
		rets += f"\n震源は{self.hypocenter.name}"
		rets += f"\n深さ{self.hypocenter.PrintDepth()}　マグニチュード{self.hypocenter.magnitude or "不明"}"
		rets += self.intensity_city.PrintIntensity()
		return rets
	
	def ParseXML(self, xml: str) -> None:
		""" XML (VXSE53) の解析を行う """
		# xml_ の接頭辞がついている変数は XML の要素を扱うものであるとみなす
		xml_ctrl, xml_head, xml_body = self.XMLSplitRoot(xml)

		# XMLが正常にパースできない場合は終了
		if xml_ctrl is None or xml_head is None or xml_body is None:
			return

		# InfoKind が「地震情報」でない場合は終了
		xml_infokind = xml_head.find(".//atom:InfoKind", self.ns["head"])
		if xml_infokind.text != "地震情報": return

		xml_earthquake = xml_body.find("./atom:Earthquake", self.ns["body"])
		xml_intensity  = xml_body.find("./atom:Intensity",  self.ns["body"])

		# 地震発生時刻の取得
		xml_origin_time = xml_body.find(".//atom:OriginTime", self.ns["body"])
		self.eq_time = datetime.datetime.fromisoformat(xml_origin_time.text)

		# 震源情報の取得
		# 震源域名
		xml_hypocenter = xml_earthquake.find("./atom:Hypocenter/atom:Area", self.ns["body"])
		self.hypocenter.name = xml_hypocenter.find("./atom:Name", self.ns["body"]).text

		# 震源位置（緯度・経度・深さ）
		xml_coordinate = xml_hypocenter.find("./jmx_eb:Coordinate", self.ns["body"])
		self.hypocenter.ParseHypocenter(xml_coordinate.text)

		# マグニチュード
		xml_magnitude = xml_earthquake.find("./jmx_eb:Magnitude", self.ns["body"])
		self.hypocenter.magnitude = float(xml_magnitude.text)

		# 観測最大震度の取得
		xml_observation = xml_body.find(".//atom:Intensity/atom:Observation", self.ns["body"])
		xml_maxint = xml_observation.find("./atom:MaxInt", self.ns["body"])
		self.max_int = xml_maxint.text

		# 震度情報（細分区域）の取得
		xml_arealist = xml_observation.findall("./atom:Pref/atom:Area", self.ns["body"])
		for xml_area in xml_arealist:
			xml_areaname = xml_area.find("./atom:Name",   self.ns["body"])
			xml_maxint   = xml_area.find("./atom:MaxInt", self.ns["body"])
			self.intensity.AddIntensity(xml_maxint.text, xml_areaname.text)	# in Intensity_Plotter

		# 震度情報（市町村等）の取得
		xml_citylist = xml_observation.findall("./atom:Pref/atom:Area/atom:City", self.ns["body"])
		for xml_city in xml_citylist:
			xml_cityname = xml_city.find("./atom:Name",   self.ns["body"])
			xml_maxint   = xml_city.find("./atom:MaxInt", self.ns["body"])
			self.intensity_city.AddIntensity(xml_maxint.text, xml_cityname.text)

		# 固定付加文の取得。文はパターン化されておりコードで識別することができる
		xml_forecast_comment = xml_body.findall(".//atom:ForecastComment[@codeType='固定付加文']", self.ns["body"])
		for c in xml_forecast_comment:
			xml_code = c.find(".//atom:Code", self.ns["body"])
			if xml_code is not None:
				self.codelist = xml_code.text.split()
		
	def DrawMap(self, plot_level: str="1") -> str:
		""" 震源・震度地図の描画 """
		Hypocenter_Plotter.SetMapBounds(self)
		Intensity_Plotter.SetMapBounds(self, plot_level)
		self.PlotHypocenter(0.4)
		self.PlotIntensity()
		outpath = self.OutputImage(self.eq_time)
		return outpath

### funcdef BEGIN ###

def GetLatLonperPixel(bound: tuple, img: cv2.typing.MatLike) -> tuple:
	"""
		1 ピクセルあたりの緯度経度の変化を計算する。1 ピクセルあたりの度数の変化量を x, y のタプルにして返す。
		bound: 地図における上下左右端の緯度経度
		img: 画像化されたベース地図
	"""
	if img is None: return (0, 0)

	hpx, wpx = img.shape[:2]
	hlt, wln = bound[3] - bound[1], bound[2] - bound[0]

	return (wln / wpx, hlt / hpx)

def GetCenterPixel(img: cv2.typing.MatLike) -> tuple:
	"""
		画像の中央座標を取得する
		img: 画像
	"""
	if img is None: return (0, 0)

	cx = int(Decimal(str(img.shape[1] / 2)).quantize(Decimal("0")))
	cy = int(Decimal(str(img.shape[0] / 2)).quantize(Decimal("0")))
	return (cx, cy)

def alpha_blend(img_base: cv2.typing.MatLike, img_add: cv2.typing.MatLike, x: int, y: int) -> None:
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
		
		eqp = EQPlotter_VXSE53(conf)
		eqp.ParseXML(xml)
		print(eqp.GetMessage())
		eqp.DrawMap("3" if conf["eqlevel"][eqp.max_int] >= 3 else 1)
	else:
		print("USAGE>python report.py [path_to_xml]")
