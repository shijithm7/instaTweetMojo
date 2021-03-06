import json
import logging
import requests
import re
import os
import urllib2

from config import *
from sys import argv
from requests_oauthlib import OAuth1

class tweetMojo():
    twitter_user = None

    twitter_oauth = None
    mojo_token = None

    def __init__(self):
        """
        Authorize the app on twitter.
        """
        oauth = OAuth1(CONSUMER_KEY, client_secret=CONSUMER_SECRET, resource_owner_key=TWITTER_TOKEN, resource_owner_secret=TWITTER_TOKEN_SECRET)
        self.twitter_oauth = oauth

    def new_twitter_user(self, twitter_user):
        """
        Assign a new twitter user.
        """
        self.twitter_user = twitter_user

    def get_n_tweets(self, username, last_n_tweets=1):
        """
        Get the latest n tweets posted by the user.
        """
        req = requests.get(url="https://api.twitter.com/1.1/statuses/user_timeline.json?screen_name=%s&count=%d" % (username, last_n_tweets), auth=self.twitter_oauth)
        return [tweet['text'] for tweet in req.json()]

    def check_tweet_is_instamoffer(self, tweet):
        """
        Check is tweet is an instamojo offer. Assumes that a tweet starting with instamoffer is an instamojo offer.
        """
        return tweet.lower().startswith("instamoffer")

    def check_offer_parameters(self, offer_key_value):
        """
        Check if an instamojo tweet is valid and can be used to generate an offer or not.
        """
        return "title" in offer_key_value and "desc" in offer_key_value and "file" in offer_key_value and "currency" in offer_key_value and "base" in offer_key_value

    def parse_tweet_for_instamojo_offer(self, tweet):
        """
        Parse the tweet to an actual python dictionary which can be used to create an instamojo offer.
        """
        offer_key_value = dict(re.findall(r'(\S+)=(".*?"|\S+)', tweet[1:]))
        return offer_key_value

    def instamojo_api_request(self, method, path, **kwargs):
        """
        Handles POST/GET requests made to the instamojo api.
        """
        headers = {'X-App-Id': MOJO_APPID}
        if self.mojo_token:
            headers["X-Auth-Token"] = self.mojo_token
        api_path = 'https://www.instamojo.com/api/1/' + path
        if method == 'GET':
            req = requests.get(api_path, data=kwargs, headers=headers)
        elif method == 'POST':
            req = requests.post(api_path, data=kwargs, headers=headers)
        else:
            raise Exception("Unable to make instamojo API call")
        try:
            return json.loads(req.text)
        except:
            raise Exception('Unable to decode response.')

    def instamojo_auth(self, username, password):
        """
        Authenticate instamojo username and password.
        """
        res = self.instamojo_api_request(method='POST', path='auth/', username=username, password=password)
        if res['success']:
            self.mojo_token = res['token']
        return res

    def get_file_upload_url(self):
        """
        Get a file upload url from the instamojo REST Api.
        """
        res = self.instamojo_api_request(method='GET', path='offer/get_file_upload_url/')
        return res

    def upload_file_from_url(self, file_upload_url, file_url):
        """
        Upload a file from the url to the instamojo api.
        """
        rec_src = urllib2.urlopen(file_url)
        filename = os.path.basename(rec_src.geturl())   # Getting redirected URL.
        rec_dest = requests.post(file_upload_url, files={'fileUpload': (filename, rec_src)})
        return rec_dest.text

    def instamojo_create_offer(self, **kwargs):
        """
        Create an instamojo offer.
        """
        if not self.mojo_token:
            return Exception('Cannot create offer without token')
        res = self.instamojo_api_request(method='POST', path='offer/', **kwargs)
        return res

if __name__ == '__main__':
    logging.basicConfig(filename='debug.log', level=logging.DEBUG)
    try:
        username = argv[1]
    except IndexError:
        raise Exception("Please mention the username.")

    logging.info('username: %s' % username)
    my_mojo = tweetMojo()
    my_mojo.new_twitter_user(username)
    latest_tweet = my_mojo.get_n_tweets(username)[0]

    if my_mojo.check_tweet_is_instamoffer(latest_tweet):
        offer_details = my_mojo.parse_tweet_for_instamojo_offer(latest_tweet)
        if my_mojo.check_offer_parameters(offer_details):
            my_mojo.instamojo_auth(MOJO_USERNAME, MOJO_PASSWORD)
            formdata = {}
            formdata["title"] = offer_details["title"][1:-1].capitalize()
            formdata["description"] = offer_details["desc"][1:-1].capitalize()
            formdata["currency"] = offer_details["currency"]
            formdata["base_price"] = offer_details["base"]
            if 'cover' in offer_details:
                cover_file_upload_url = my_mojo.get_file_upload_url()
                if cover_file_upload_url["success"]:
                    cover_file_upload_url = cover_file_upload_url["upload_url"]
                else:
                    raise Exception("Unable to get file upload URL for cover image.")
            file_upload_url = my_mojo.get_file_upload_url()
            if file_upload_url["success"]:
                file_upload_url = file_upload_url["upload_url"]
            else:
                raise Exception("Unable to get file upload URL for main file.")

            file_upload_json = my_mojo.upload_file_from_url(file_upload_url, offer_details['file'])
            formdata['file_upload_json'] = file_upload_json
            
            cover_file_upload_json = my_mojo.upload_file_from_url(cover_file_upload_url, offer_details['cover'])
            formdata['cover_image_json'] = cover_file_upload_json

            print formdata
            print my_mojo.instamojo_create_offer(**formdata)
        else:
            raise Exception("The tweet format does not match the specified format.")
    else:
        raise Exception("The tweet is not about an instamojo offer.")

