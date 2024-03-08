import tweepy
from twitter_text import parse_tweet

def Adjust_PostLen(post_fmt: str, target: str) -> str:
	target = target[:280]
	text = ""

	for i in range(len(target)):
		text = post_fmt.format(target if i == 0 else (target[:-i] + "…"))
		if parse_tweet(text).valid:
			return text

	return ""

def Post(authdict: dict, text: str, img_path: str) -> None:
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

	#media = api.media_upload(filename=img_path)
	#client.create_tweet(text=text, media_ids=[media.media_id])