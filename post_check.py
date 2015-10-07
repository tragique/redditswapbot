#!/usr/bin/python

import sys, os
from ConfigParser import SafeConfigParser
import logging
import praw
import re
import mySQLHandler
from datetime import datetime, timedelta
from time import sleep, time
from pprint import pprint

# load config file
containing_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
cfg_file = SafeConfigParser()
path_to_cfg = os.path.join(containing_dir, 'config.cfg')
cfg_file.read(path_to_cfg)
username = cfg_file.get('reddit', 'username')
password = cfg_file.get('reddit', 'password')
subreddit = cfg_file.get('reddit', 'subreddit')
multiprocess = cfg_file.get('reddit', 'multiprocess')

logging_dest = cfg_file.get('logging','dest')

mysql_hostname = cfg_file.get('mysql', 'hostname')
mysql_username = cfg_file.get('mysql', 'username')
mysql_password = cfg_file.get('mysql', 'password')
mysql_database = cfg_file.get('mysql', 'database')

#configure logging
logger = logging.getLogger('post_check')
logger.setLevel(logging.INFO)

if logging_dest == 'mysql':
	db = {'host':mysql_hostname, 'port':3306, 'dbuser':mysql_username, 'dbpassword':mysql_password, 'dbname':mysql_database}

	sqlh = mySQLHandler.mySQLHandler(db)
	logger.addHandler(sqlh)
else:
	fileh = logging.FileHandler('actions.log')
	fileh.setFormatter(logging.Formatter('%(asctime)s - %(module)s - %(message)s'))
	logger.addHandler(fileh)

requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

def main():
	while True:
		try:
			logger.info('Logging in as /u/'+username)
			if multiprocess == 'true':
				handler = MultiprocessHandler()
				r = praw.Reddit(user_agent=username, handler=handler)
			else:
				r = praw.Reddit(user_agent=username)
			r.login(username, password)

			already_done = []
	
			while True:
				data = r.get_subreddit(subreddit).get_new(limit=2)
				for post in data:
					if post.id not in already_done:
						already_done.append(post.id)
						matchObj = re.search("(\[[A-Z]{2,}.*\].*\[H\].*\[W\].*)|(\[META\].*)|(\[GB\].*)|(\[IC\].*)|(\[Artisan\].*)", post.title)
						match2Obj = re.search("(\[[s,S]elling\])|(\[[b,B]uying\])", post.title)
						if (not matchObj or match2Obj) and not post.distinguished:
							if post.author.name != username:
								logger.warn('Removed post: '+post.title+' by '+post.author.name)
								if not post.approved_by:
									post.report()
									post.add_comment('REMOVED: Please read the [wiki](/r/mechmarket/wiki/rules/rules) for posting rules').distinguish()
									post.remove()
								else:
									logger.warn('Bad post approved by: '+post.approved_by.name)
						else:
							buyingMatch = re.search("\[H\].*(cash|paypal|\$|google|ltc|btc|money).*\[W\]", post.title, re.IGNORECASE)
							sellingMatch = re.search("\[W\].*(cash|paypal|\$|google|ltc|btc|money).*", post.title, re.IGNORECASE)
							metaMatch = re.search("\[META\].*", post.title)
							icMatch = re.search("\[IC\].*", post.title)
							gbMatch = re.search("\[GB\].*", post.title)
							artisanMatch = re.search("\[Artisan\].*", post.title)
							if not post.link_flair_text:
								if not post.distinguished:
									if sellingMatch:
										r.set_flair(subreddit, post, 'Selling', 'selling')
										logger.info("SELL: "+post.title)
									elif buyingMatch:
										r.set_flair(subreddit, post, 'Buying', 'buying')
										logger.info("BUY: "+post.title)
									elif metaMatch:
										r.set_flair(subreddit, post, 'META', 'meta')
										logger.info("META: "+post.title)
									elif icMatch:
										r.set_flair(subreddit, post, 'Interest Check', 'interestcheck')
										logger.info("IC: "+post.title)
									elif gbMatch:
										r.set_flair(subreddit, post, 'Group Buy', 'groupbuy')
										logger.info("GB: "+post.title)
									elif artisanMatch:
										r.set_flair(subreddit, post, 'Artisan', 'artisan')
										logger.info("Artisan: "+post.title)
									else:
										r.set_flair(subreddit, post, 'Trading', 'trading')
										logger.info("TRADE: "+post.title)
							else:
								logger.info("OTHER: "+post.title)
							#check comments for info from bot
							if not post.distinguished:
								post.replace_more_comments(limit=None, threshold=0)
								flat_comments = list(praw.helpers.flatten_tree(post.comments))
								botcomment = 0
								for comment in flat_comments:
									if hasattr(comment.author, 'name'):
										if comment.author.name == username:
											botcomment = 1
								#otherwise spit out user information
								if botcomment == 0 and ( not metaMatch or post.link_flair_css_class != "meta" ):
									age = str(datetime.utcfromtimestamp(post.author.created_utc))
									if str(post.author_flair_text) == "None":
										heatware = "None"
									else:
										heatware = "[" + str(post.author_flair_text) + "](" + str(post.author_flair_text) +")"
									post.add_comment('* Username: ' + str(post.author.name) + '\n* Join date: ' + age + '\n* Link karma: ' + str(post.author.link_karma) + '\n* Comment karma: ' + str(post.author.comment_karma) + '\n* Confirmed trades: ' + str(post.author_flair_css_class).translate(None, 'i-') + '\n* Heatware: ' + heatware + '\n\n^^This ^^information ^^does ^^not ^^guarantee ^^a ^^successful ^^swap. ^^It ^^is ^^being ^^provided ^^to ^^help ^^potential ^^trade ^^partners ^^have ^^more ^^immediate ^^background ^^information ^^about ^^with ^^whom ^^they ^^are ^^swapping. ^^Please ^^be ^^sure ^^to ^^familiarize ^^yourself ^^with ^^the ^^[RULES](https://www.reddit.com/r/mechmarket/wiki/rules/rules) ^^and ^^other ^^guides ^^on ^^the ^^[WIKI](https://www.reddit.com/r/mechmarket/wiki/index)')
	
				logging.debug('Sleeping for 2 minutes')
				sleep(120)
		except Exception as e:
			logger.error(e)

if __name__ == '__main__':
	main()