# coding: utf-8
from shapely.geometry import Polygon, MultiPolygon, Point
from pandas import DataFrame

import matplotlib.pyplot as plt
import geopandas as gpd
import pickle
import json

def SelectLargestPolygon(geometry):
	polygon = list(geometry)[0]

	if isinstance(polygon, Polygon):
		target = polygon
	elif isinstance(polygon, MultiPolygon):
		areas = [(p.area, p) for p in polygon.geoms]
		areas = sorted(areas, key=lambda x: x[0], reverse=True)
		target = areas[0][1]
	else:
		target = Polygon()
	return target

def DrawPrefecture(df: gpd.GeoDataFrame, preflist: list, ax=None, 
				   edgecolor="None", facecolor="None", linewidth=0, simplify_tolerance=0.001):
	if ax is None: ax = plt.gca()

	for pl in preflist:
		code = [str(n) for n in range(int(pl["codestart"]), int(pl["codeend"]) + 1)]
		m = df[df["code"].isin(code)]

		if len(m) > 0:
			print(f"  Framing {pl["name"]}, {(m.iloc[0])["name"]} - {(m.iloc[-1])["name"]} ...", end="", flush=True)
			bound = m.dissolve()
			bound["geometry"] = SelectLargestPolygon(bound["geometry"]).simplify(simplify_tolerance)
			bound.plot(ax=ax, edgecolor=edgecolor, facecolor=facecolor, linewidth=linewidth)
			print("done", flush=True)
	return

def Centroid2Point(geometry) -> Point:
	ctr = list(geometry.centroid.coords)[0]
	return Point(ctr)

def Bound2String(geometry) -> str:
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
	file = open("config.json", "r", encoding="utf-8")
	conf = json.load(file)
	file.close()
	try:
		paths = conf["paths"]
		shape_path = paths["shapefile"]
		areamap_path = paths["areamap"]
		assistant_path = paths["assistant"]

		simplify_tolerance = conf["simplify_tolerance"]

		pref = conf["pref"]
		region = conf["region"]
	except:
		print("\nFAILED: Couldn't read config")
		exit()

	print("done", flush=True)

	print("Reading Shapefile...", end="", flush=True)
	gpd_map = gpd.read_file(shape_path, encoding="utf-8")
	print("done", flush=True)

	fig = plt.figure()
	ax  = fig.add_subplot()
	ax.set_facecolor("cornflowerblue")

	# データの簡略化
	print("Simplifying maps...", end="", flush=True)
	smp_map = gpd_map.copy()
	smp_map["geometry"] = smp_map["geometry"].simplify(simplify_tolerance)
	print("done", flush=True)

	# 細分区域の描画
	print("Ploting each area...", end="", flush=True)
	smp_map.plot(ax=ax, edgecolor="silver", facecolor="wheat", linewidth=0.5)
	print("done", flush=True)

	# 県の枠線描画 (データの簡略化はこの中で行う)
	print("Framing Prefectures...", flush=True)
	DrawPrefecture(
		gpd_map,
		pref,
		ax=ax,
		edgecolor="darkgray",
		facecolor="None",
		linewidth=1.0,
		simplify_tolerance=simplify_tolerance
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
