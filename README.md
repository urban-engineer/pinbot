Post messages from one channel to others in Discord, to avoid the 50 pin limit

Built this because we pinned too many messages in one channel, and we wanted to keep pinning good posts.

So this simple bot just posts from one channel to another, if any user reacts with the pushpin emoji (📌).

To set it up yourself:
* Clone the repo
* Copy `secrets.json.example` to `secrets.json`, and put your bot token in there. 
* Run with python (dev/tested on 3.8.8).

Or just build an image with the dockerfile.

`docker build -t <you>/pinbot . && docker run -d --name PinBot -v /path/to/secrets.json:/pinbot/config/secrets.json -v /path/to/pinbot/pinbot.db:/pinbot/pinbot.db <you>/pinbot`
