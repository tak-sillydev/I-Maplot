# coding: utf-8
from shapely.geometry import Polygon, MultiPolygon, Point
from pandas import DataFrame

from matplotlib.axes import Axes
import matplotlib.pyplot as plt
import geopandas as gpd
import pickle
import json

def SelectLargestPolygon(geometry: Polygon | MultiPolygon):
	polygon = list(geometry)[0]

	match polygon:
		case Polygon():
			target = polygon
		case MultiPolygon():
			areas = [(p.area, p) for p in polygon.geoms]
			areas = sorted(areas, key=lambda x: x[0], reverse=True)
			target = areas[0][1]
		case _:
			target = Polygon()
	return target

def DrawPrefecture(df: gpd.GeoDataFrame, preflist: list, ax: Axes=None, edgecolor="None", facecolor="None", linewidth=0):
	if ax is None: ax = plt.gca()

	for pl in preflist:
		code = [str(n) for n in range(int(pl["codestart"]), int(pl["codeend"]) + 1)]
		m = df[df["code"].isin(code)]

		if len(m) > 0:
			print(f"  Framing {pl["name"]}, {(m.iloc[0])["name"]} - {(m.iloc[-1])["name"]} ...", end="", flush=True)

			bound = m.dissolve()
			bound["geometry"] = SelectLargestPolygon(bound["geometry"])
			bound.plot(ax=ax, edgecolor=edgecolor, facecolor=facecolor, linewidth=linewidth)
			print("done", flush=True)
	return

def Centroid2Point(geometry: DataFrame) -> Point:
	ctr = list(geometry.centroid.coords)[0]
	return Point(ctr)

def Bound2String(geometry: DataFrame) -> str:
	bounds = geometry.bounds
	return "{},{},{},{}".format(bounds[0], bounds[1], bounds[2], bounds[3])

def AreaCode2RegionName(code, region: list) -> str:
	c = -1 if code is None else int(code)
	for r in region:
		if int(r["codestart"]) <= c <= int(r["codeend"]):
			return r["name"]
	return ""

def MakeAssistantData(row, region):
	return row["name"], AreaCode2RegionName(row["code"], region), \
		Centroid2Point(row["geometry"]), Bound2String(row["geometry"])


if __name__ == "__main__":
	print("Reading Configs...", end="", flush=True)
	try:
		with open("config.json", "r", encoding="utf-8") as f:
			conf = json.load(f)

		# root
		makemap: dict		= conf["makemap"]

		# area map
		areamap: dict			= makemap["areamap"]
		areamap_shape_path: str	= areamap["shapefile"]
		areamap_color_edge: str	= areamap["color"]["edge"]
		areamap_color_face: str	= areamap["color"]["face"]
		areamap_color_back: str	= areamap["color"]["back"]

		# lake data
		lake: dict				= makemap["lake"]
		lake_shape_path: str	= lake["shapefile"]
		lake_color_edge: str	= lake["color"]["edge"]
		lake_color_face: str	= lake["color"]["face"]
		lake_color_back: str	= lake["color"]["back"]

		# output paths
		paths: dict			= conf["paths"]
		areamap_path: str   = paths["areamap"]
		assistant_path: str = paths["assistant"]

		simplify_tolerance: int = makemap["simplify_tolerance"]

		pref: dict   = conf["pref"]
		region: dict = conf["region"]
	except:
		print("\nFAILED: Couldn't read config")
		exit()

	print("done", flush=True)

	print("Reading Shapefiles...", end="", flush=True)
	gpd_map  = gpd.read_file(areamap_shape_path, encoding="utf-8")
	gpd_lake = gpd.read_file(lake_shape_path, encoding="utf-8")
	print("done", flush=True)

	fig = plt.figure()
	ax  = fig.add_subplot()
	ax.set_facecolor(areamap_color_back)


	# 細分区域の描画
	print("Ploting each area...", end="", flush=True)
	gpd_map.plot(ax=ax, edgecolor=areamap_color_edge, facecolor=areamap_color_face, linewidth=0.5)
	print("done", flush=True)


	# 湖沼の描画（面積上位30番目まで）
	# 座標系 JGD2000 (EPSG:4612) -> 正積図法 (EPSG:3410)に変換
	print("Ploting lakes...", end="", flush=True)

	gpd_lake.crs = "epsg:4612"
	eap_lake = gpd_lake.to_crs(epsg=3410)	# Equal Area map Projection

	# ジオメトリから面積を抽出し、面積の大きい順にソートし上位30位までを取得
	eap_lake["area"] = eap_lake["geometry"].apply(lambda x: x.area)
	df = eap_lake.sort_values("area", ascending=False).head(30)

	# 正積図法で絞り込んだデータを元の座標系のデータにも適用し、さらに簡略化してプロット
	gpd_lake = gpd_lake[gpd_lake["W09_001"].isin(list(df["W09_001"]))].simplify(0.005)
	gpd_lake.plot(ax=ax, edgecolor=lake_color_edge, facecolor=lake_color_face, linewidth=0.1)
	print("done", flush=True)


	# 県の枠線描画 (データの簡略化はこの中で行う)
	print("Framing Prefectures...", flush=True)
	DrawPrefecture(
		gpd_map,
		pref,
		ax=ax,
		edgecolor=areamap_color_edge,
		facecolor="None",
		linewidth=1.0,
	)
	print("all done", flush=True)

	# pickle でデータを保存
	print(f"Writing area map to {areamap_path}...", end="", flush=True)
	with open(areamap_path, "wb") as f:
		pickle.dump(fig, f)
	print("done", flush=True)

	print("Extracting assitant data...", end="", flush=True)
	assistant = DataFrame()

	assistant[["name", "region", "centroid", "bounds"]] = \
		gpd_map.apply(MakeAssistantData, region=region, result_type="expand", axis=1)

	# EPSG6668 : JGD2011(世界測地系)緯度経度
	# 気象庁のシェープファイルがおいてあるページに書いてあった。今後変わるかも分からん
	print("done", flush=True)

	print(f"Writing assistant data to {assistant_path}...", end="", flush=True)
	assistant.to_pickle(assistant_path)
	print("done", flush=True)
