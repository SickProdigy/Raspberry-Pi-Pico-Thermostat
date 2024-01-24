import network
import urequests as requests #dependency faked as another dependency ig

url = "https://discord.com/api/webhooks/1199545130378608650/UyJj0e-YuSlmVZD87zaHitXZLC55RP6LVBUv3nt9ZWr6d4AGzSGKZ-zI6V_VwA6I4qSq" #webhook url, from here: https://i.imgur.com/f9XnAew.png

#for all params, see https://discordapp.com/developers/docs/resources/webhook#execute-webhook
data = {
    "content" : "Testing",
    "username" : "Captain Hook"
}

#leave this out if you dont want an embed
#for all params, see https://discordapp.com/developers/docs/resources/channel#embed-object
data["embeds"] = [
    {
        "description" : "Testing for temps",
        "title" : "Tent Temp=5000c"
    }
]

result = requests.post(url, json = data)

try:
    result.raise_for_status()
except requests.exceptions.HTTPError as err:
    print(err)
else:
    print("Payload delivered successfully, code {}.".format(result.status_code))

#result: https://i.imgur.com/DRqXQzA.png