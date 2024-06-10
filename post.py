import tweepy
from twitter_text import parse_tweet

import debugdef

def Adjust_PostLen(post_fmt: str, target: str) -> str:
	"""
		投稿時の文字列長を、X 側が受け入れ可能な長さまで切り詰めて調節する。
		post_fmt: 投稿フォーマット。ここに target を差し込んだ文を計算に用いる。
		target:   フォーマットに差し込む（可変）文
	"""
	# 半角 280 字以上は受け付けられないので処理軽減のために先に切っておく
	target = target[:280]
	text = ""

	for i in range(len(target)):
		text = post_fmt.format(target if i == 0 else (target[:-i] + "…"))
		if parse_tweet(text).valid:
			return text

	return ""

def Post(authdict: dict, text: str, img_path: str) -> None:
	"""
		文章と画像を X に投稿する。
		authdict: X API 認証用の鍵の詰め合わせ
		text:     投稿する文章
		img_path: 投稿する画像へのファイルパス
	"""
	auth = tweepy.OAuthHandler(
		consumer_key=authdict["api_key"],
		consumer_secret=authdict["api_secret"],
		access_token=authdict["access_token"],
		access_token_secret=authdict["access_secret"]
	)
	client = tweepy.Client(
		bearer_token=authdict["bearer_token"],
		consumer_key=authdict["api_key"],
		consumer_secret=authdict["api_secret"],
		access_token=authdict["access_token"],
		access_token_secret=authdict["access_secret"]
	)
	api = tweepy.API(auth)

	# デバッグ時、投稿は封じられる
	if debugdef.fDebug != True:
		media = api.media_upload(filename=img_path)
		client.create_tweet(text=text, media_ids=[media.media_id])
