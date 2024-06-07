# -*- coding: utf-8 -*-
import json
import datetime

from feedctl import FeedControl

if __name__ == "__main__":
	CONFIG_PATH = "./config.json"
	CONFIG_ENCTYPE = "utf-8"

	with open(CONFIG_PATH, "r", encoding=CONFIG_ENCTYPE) as f:
		conf = json.load(f)
	
	fc = FeedControl(conf["paths"]["feedctl"])
	fc.last_eq		= datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
	fc.last_update	= datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
	fc.last_msg		= "ダミーデータです。地震情報はありません"
	fc.PickleMyself()
