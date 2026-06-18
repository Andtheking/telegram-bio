from telegram.ext import Application
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram import Message

import html
import asyncio

from utils.jsonUtils import load_configs
from jobs.logs import logEnqueue
import time

import pylast
from urllib.parse import quote_plus
import traceback 

load_configs()['token']
LASTFM_API_KEY = load_configs()['LAST_FM_API']['API_KEY']
LASTFM_API_SECRET = load_configs()['LAST_FM_API']['API_SECRET']

CANALE_LOG = -1001741378490
CANALE_BIO = -1001730850939
MSG = 7

application = Application.builder().token(load_configs()['token']).build()

#region Last fm configuration
network = pylast.LastFMNetwork(
    api_key=LASTFM_API_KEY,
    api_secret=LASTFM_API_SECRET
)

UTENTE_LASTFM = network.get_user(load_configs()['last_fm_username'])
#endregion

#region Last fm on channel


class Timer:
    def __init__(self, timeout: int, callback, loop: asyncio.BaseEventLoop = None):
        self.timeout = timeout
        self._callback = callback
        self.loop = loop
        if loop == None:
            self._task = asyncio.create_task(self._job())
        else:
            self._task = loop.create_task(self._job())

    async def _job(self):
        await asyncio.sleep(self.timeout)
        await self._callback(self)

    def cancel(self):
        self._task.cancel()

richieste_a_last_fm = 0
now = time.time()

async def timer_callback(caller: Timer):
    global richieste_a_last_fm
    global now
    
    print(f"Effettuate {richieste_a_last_fm} richieste a last_fm in {time.time() - now}")
    richieste_a_last_fm = 0
    
    now = time.time()
    Timer(60, timer_callback, caller.loop)

MESSAGE_TEMPLATE = '''
<b>Now playing:</b> 
<a href="{album_cover}">\u200B</a>
{track_icon} <b>{titolo}</b> {times}
🎤 <i>{artista}</i>{album_line}

{links}'''

MUSIC_LINKS_PREMIUM = '''<tg-emoji emoji-id="5929311796484642264">🔴</tg-emoji> <a href="{ytmusic_link}"> YT Music </a>
<tg-emoji emoji-id="5927186874299847675">🟢</tg-emoji> <a href="{spoti_link}"> Spotify </a>
<tg-emoji emoji-id="5929414544987264351">🟣</tg-emoji> <a href="{deezer_link}"> Deezer </a>
<tg-emoji emoji-id="5933567194246943241">🟠</tg-emoji> <a href="{soundcloud_link}"> Soundcloud </a>
'''

MUSIC_LINKS = '''🔴 [YT Music]({ytmusic_link})\n🟢 [Spotify]({spoti_link})\n🟣 [Deezer]({deezer_link})\n🟠 [Soundcloud]({soundcloud_link})'''

async def last_fm():
    Timer(60, timer_callback) # API request counter
    global richieste_a_last_fm
    
    last_track = None
    playing = True
    while True:
        await asyncio.sleep(10)
        
        # API request
        try:
            track = UTENTE_LASTFM.get_now_playing()
            richieste_a_last_fm += 1
        except Exception as e:
            await logEnqueue(traceback.format_exc(chain=False, limit=1), log_type='ERROR')
            await asyncio.sleep(10) # failed API request timeout
            continue
        
        
        if track:
            playing = True
        elif last_track:
            # If no track is being listened now, change text to "was"
            await try_editing(text=last_text.replace("Now playing", "Was playing"))
            last_track = None # reset so next iterations are skipped
            playing = False
        
        # Skip
        if not playing or not track:
            continue

        album = track.info['album']
        edited_message: Message = None
        
        # Se la track è la stessa di prima evita di fare tutte le richieste a Last.FM
        # La seconda parte dell'OR serve per capire se è cambiato l'album.
        if not (track != last_track or (last_track.info and track.info != last_track.info)):
            continue
        
        is_loved = False
        listen_count = None
        try:
            is_loved = track.get_userloved()
            listen_count = track.get_userplaycount()
            richieste_a_last_fm += 1
        except Exception as ex:
            await logEnqueue(traceback.format_exc(chain=False, limit=1), log_type='ERROR')

        title = str(track.title)
        artist = str(track.artist)
        query = quote_plus(f"{title} {artist}")
        
        link_data = {
            "spoti_link": html.escape(f"https://open.spotify.com/search/{query}"),
            "ytmusic_link": html.escape(f"https://music.youtube.com/search?q={query}"),
            "deezer_link": html.escape(f"https://www.deezer.com/search/{query}"),
            "soundcloud_link": html.escape(f"https://soundcloud.com/search?q={query}")
        }
        
        display_data = {
            "track_icon": "❤️" if is_loved else "🎵",
            "titolo": html.escape(str(track.title)),
            "artista": html.escape(str(track.artist)),
            "album_cover": track.get_cover_image(),
            "album_line": f'\n💿 {html.escape(str(album))}' if album else '',
            "times": f"(x{listen_count})" if listen_count else '', 
            "links": MUSIC_LINKS_PREMIUM.format(
                spoti_link=f"https://open.spotify.com/search/{query}",
                ytmusic_link=f"https://music.youtube.com/search?q={query}",
                deezer_link=f"https://www.deezer.com/search/{query}",
                soundcloud_link=f"https://soundcloud.com/search?q={query}"
            )
        }
        
        edited_message = await try_editing(
            text=MESSAGE_TEMPLATE.format(**display_data)
        )
        
        last_track = track
        if edited_message:
            last_text = edited_message.text_html

#endregion

import re
def escape(c):
    text = re.sub(r'[_*[\]()~>#\+\-=|{}.!]', lambda x: '\\' + x.group(), str(c))
    return text

async def try_editing(text):
    try:
        return await application.bot.edit_message_text(chat_id=CANALE_BIO, 
                                                message_id=MSG, 
                                                text=text,
                                                parse_mode=ParseMode.HTML)
    except BadRequest as ex:
        if ("Message is not modified" in str(ex)):
            print("Messaggio non modificato. Forse hai appena avviato il bot?")
        else:
            print(traceback.format_exc(chain=False, limit=1))
    except Exception as ex:
        await logEnqueue(traceback.format_exc(chain=False, limit=1), log_type='ERROR')

asyncio.run(last_fm())