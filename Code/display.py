"""
A somewhat hacky version of the Pirate Audio player
Drew Batchelor 
V 0.2 It's a stable usable beta 
22/12/2021 

To try it, If you already have the working Python 3 version of Pirate audio:
SSH into your Pi and navigate to ( /data/plugins/miscellanea/pirateaudio/ )
Back up by renaming the existing "display.py" to something like "display_old.py" 
Copy this "display.py" to the pi
copy "images>aurora_s.jpg" to the pi images folder ( /data/plugins/miscellanea/pirateaudio/images/ )
Restart the pirate audio plug n (either restart the Pi, or go in volumio to plug ins setting and reset the plugin).
That's all. Screen should go black and come back with the new graphics.


The original version is by Ax-LED this is the Volumio 3 Version With Python 3, which is still development and has not been merged back into 
Volumio plugins master at this time:
https://github.com/Ax-LED/volumio-plugins-sources/tree/master/pirateaudio

Changes in Drew's version 0.2:
Add delays to the menu and volume to debounce on the Pi Zero 2
Change the appearance 
Colours are moved into variables declared near the top, to make this easier to skin 
Colours changed to closer match the colours in Volumio, light text on black bars.
Graphic layout lots of little tweeks, still a work in progress.
Volume bar got a tick on the top like Volumio. 
Volume bar no longer goes negative.
font sizes - reduced a little bit.
Added a thumbnail version of Aurora called aurora_s.jpg as a Background image  (from Volumio) 
    when there is text - eg menus, so that the Volumio logo doesnt crash the text.


"""
#!/usr/bin/env python3

import time
from PIL import ImageFont, Image, ImageDraw, ImageStat, ImageFilter
from PIL import ImageFilter  # v0.0.4
import os
import os.path
#import ST7789 as ST7789
import ST7789 #v0.0.6
from socketIO_client import SocketIO
import requests
from io import BytesIO
from numpy import mean
import sys
import signal
import RPi.GPIO as GPIO
import math
import json
from signal import *
from time import strftime, gmtime  # v.0.0.4
import time  # v.0.0.4
# import logging
# logging.getLogger('socketIO-client').setLevel(logging.DEBUG)
# logging.basicConfig()

# get the path of the script
script_path = os.path.dirname(os.path.abspath(__file__))
# set script path as current directory
os.chdir(script_path)

# socketIO = SocketIO('localhost', 3000)

# Create ST7789 LCD display class.
disp = ST7789.ST7789(
    height=240, #v0.0.6
    width=240, #v0.0.6
    rotation=90,  # Needed to display the right way up on Pirate Audio
    port=0,       # SPI port
    cs=1,         # SPI port Chip-select channel
    dc=9,         # BCM pin used for data/command
    backlight=13,
    spi_speed_hz=80 * 1000 * 1000,
    offset_left=0, #v0.0.6
    offset_top=0 #v0.0.6
)

# read json file (plugin values)
with open('/data/configuration/miscellanea/pirateaudio/config.json', 'r') as myfile:
    data = myfile.read()
obj = json.loads(data)  # parse file

# read json file (volumio language)
with open('/data/configuration/miscellanea/appearance/config.json', 'r') as mylangfile:
    data_lang = mylangfile.read()
obj_lang = json.loads(data_lang)  # parse file
langcode = obj_lang['language_code']['value']
langpath = '/data/plugins/miscellanea/pirateaudio/i18n/strings_' + langcode + '.json'
if os.path.exists(langpath) is False:  # change to en as default language
    langpath = '/data/plugins/miscellanea/pirateaudio/i18n/strings_en.json'

# read json file (language file for translation)
with open(langpath, 'r') as mytransfile:
    data_trans = mytransfile.read()
obj_trans = json.loads(data_trans)  # parse file

# Set up Sizes & Fonts 
WIDTH = 240
HEIGHT = 240
font_s = ImageFont.truetype(script_path + '/fonts/Roboto-Medium.ttf', 20)
font_m = ImageFont.truetype(script_path + '/fonts/Roboto-Medium.ttf', 24)
font_l = ImageFont.truetype(script_path + '/fonts/Roboto-Medium.ttf', 28)
font_fas = ImageFont.truetype(script_path + '/fonts/FontAwesome5-Free-Solid.otf', 26)
bg_start = Image.open('images/default.jpg').resize((WIDTH, HEIGHT))
bg_default = Image.open('images/aurora_s.jpg').resize((WIDTH, HEIGHT))

#Set up colours
col1 = (255, 255, 255) #white
col2 = (128, 128, 128) # mid grey
col3 = (100, 100, 100) #mig grey
col6 = (55, 55, 55) 
col4 = (15, 15, 15) # very dark grey
col5 = (0, 0, 0)  #black
teal = (84, 198, 136) #teal = (102, 204, 153)

# Play pause menu volume symbol positions
symb_l = 0
symb_t = 33 # was 50
symb_r = 214
symb_b = 208 #was 170

albumart, artist, album, title, img_check = '', '', '', '', ''
mode = 'player'
title_queue, len_queue = [], 0  # v.0.0.4
position = ''  # v.0.0.4
nav_array_name, nav_array_uri, nav_array_type, nav_array_service = [], [], [], []
marker, listmax, liststart, listresult = 0, int(obj['listmax']['value']), 0, 0


BUTTONS = [5, 6, 16, obj['gpio_ybutton']['value']]
# LABELS = ['A', 'B', 'X', 'Y']
GPIO.setmode(GPIO.BCM)  # Set up RPi.GPIO with the "BCM" numbering scheme


# exit function (even is service is stopped)
def clean(*args):
    
    disp.set_backlight(False)
    GPIO.cleanup(BUTTONS)  # v0.0.4
    sys.exit(0)

for sig in (SIGABRT, SIGILL, SIGINT, SIGSEGV, SIGTERM):
    signal(sig, clean)
# exit function (even is service is stopped)

def on_connect():
    # print('connect')
    start_time = time.time()  # debug, time of code execution
    socketIO.on('pushState', on_push_state)
    socketIO.emit('getState', '', on_push_state)
    socketIO.on('pushBrowseSources', on_push_browsesources)
    socketIO.on('pushBrowseLibrary', on_push_browselibrary)
    socketIO.on('pushQueue', on_push_queue)
    socketIO.emit('getQueue', on_push_queue)
    # print("on_connect--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def on_disconnect():
    display_stuff('bg_start', obj_trans['DISPLAY']['LOSTCONNECTION'], 0, 0, 'info') # was bg_default

def navigation_handler():
    # start_time = time.time()  # debug, time of code execution
    global mode, nav_array_name, nav_array_uri, nav_array_type, marker, liststart, listresult
    if mode == 'player':
        mode = 'menu'
        emit_action = ['setSleep', {'enabled': 'true', 'time': strftime("%H:%M", gmtime(obj['sleeptimer']['value']*60))}]
        nav_array_name = [obj_trans['DISPLAY']['MUSICSELECTION'], obj_trans['DISPLAY']['SEEK'], obj_trans['DISPLAY']['PREVNEXT'], 'Sleeptimer ' + str(obj['sleeptimer']['value']) + 'M', obj_trans['DISPLAY']['SHUTDOWN'], obj_trans['DISPLAY']['REBOOT']]
        nav_array_uri = ['', 'seek', 'prevnext', emit_action, 'shutdown', 'reboot']
        nav_array_type = ['', 'seek', 'prevnext', 'emit', 'emit', 'emit']
        listresult = 6
        display_stuff('bg_default', nav_array_name, marker, liststart)
    else:
        print('else navigation_handler() eingetreten')
    # print("navigation_handler--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def on_push_browsesources(*args):
    # start_time = time.time()  # debug, time of code execution
    global listresult  # v.0.0.4 removed some globals, as thex not needed here
    if mode == 'navigation':  # v.0.0.4 added, to make sure this getting not displayed on_connect
        listresult = len(args[0])
        i = 0
        append_n = nav_array_name.append  # to avoid dots in for loop
        append_u = nav_array_uri.append
        for i in range(listresult):
            append_n(args[0][i]['name'])
            append_u(args[0][i]['uri'])
        display_stuff('bg_default', nav_array_name, marker, 0)
    # print("on_push_browsesources--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def on_push_browselibrary(*args):
    # start_time = time.time()  # debug, time of code execution
    global listresult  # v.0.0.4 removed some globals, as thex not needed here
    reset_variable('navigation')
    listresult = len(args[0]['navigation']['lists'][0]['items'])  # v.0.0.4 code cleaning
    i = 0
    if listresult > 0:  # we have item entries
        append_s = nav_array_service.append  # to avoid dots in for loop
        append_t = nav_array_type.append
        append_n = nav_array_name.append
        append_u = nav_array_uri.append
        for i in range(listresult):
            if 'service' in args[0]['navigation']['lists'][0]['items'][i]:  # v.0.0.4
                append_s(args[0]['navigation']['lists'][0]['items'][i]['service'])  # v.0.0.4
            if 'title' in args[0]['navigation']['lists'][0]['items'][i]:  # v.0.0.4
                append_n(args[0]['navigation']['lists'][0]['items'][i]['title'])
            append_t(args[0]['navigation']['lists'][0]['items'][i]['type'])
            if 'uri' in args[0]['navigation']['lists'][0]['items'][i]:  # v.0.0.4 spotify check
                append_u(args[0]['navigation']['lists'][0]['items'][i]['uri'])  # v.0.04
        display_stuff('bg_default', nav_array_name, marker, liststart)
    elif listresult == 0:  # we have no item entries
        display_stuff('bg_default', obj_trans['DISPLAY']['EMPTY'], marker, liststart)
    # print("on_push_browselibrary--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def reset_variable(varmode):
    # start_time = time.time()  # debug, time of code execution
    global mode, nav_array_service, nav_array_name, nav_array_uri, nav_array_type, marker, liststart, img_check, albumart
    mode = varmode
    del nav_array_name[:]  # v.0.0.4 del is cleaner than = []
    del nav_array_uri[:]
    del nav_array_type[:]
    del nav_array_service[:]
    marker, liststart = 0, 0
    img_check, albumart = '', ''  # reset albumart so display gets refreshed
    # print("reset_variable--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def sendtodisplay(img):
    # start_time = time.time()  # debug, time of code execution
    disp.display(img)
    #time.sleep(0.1)  # ohne sleep 82% CPU, sleep: 0.5 = 40%, 0.25 = 53%, 0.1 = 70%
    # print("sendtodisplay--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def display_stuff(picture, text, marked, start, icons='nav'):  # v.0.0.4 test for better performance
    # start_time = time.time()  # debug, time of code execution
    global img3, listmax  # v.0.0.4
    i = 0
    if picture == 'bg_default':
        img3 = bg_default.copy()
    else:
        img3 = Image.open(picture).convert('RGBA')  # v.0.0.4
    draw3 = ImageDraw.Draw(img3, 'RGBA')

    if isinstance(text, list):  # check if text is array
        result = len(text)  # count items of list/array
        totaltextheight = 0
        # Loop for finding out the sum of textheight for positioning, only text to display
        listbis = start + listmax
        if listbis > result:
            listbis = result
        for i in range(start, listbis):  # v.0.0.4 range max werteliste
            len1, hei1 = draw3.textsize(text[0+i], font=font_m)
            totaltextheight += hei1
        i = 0
        y = (HEIGHT // 2) - (totaltextheight // 2)

        # Loop for creating text to display
        for i in range(start, listbis):  # v.0.0.4
            len1, hei1 = draw3.textsize(text[0+i], font=font_m)
            x2 = (WIDTH - len1)//2
            if x2 < 0:  # v.0.0.4 dont center text if to long
                x2 = 0
            if i == marked:
                draw3.rectangle((x2, y + 2, x2 + len1, y + hei1), col1)
                draw3.text((x2, y), text[0+i], font=font_m, fill=col5)
            else:
                # draw3.text((x2 + 3, y + 3), text[0+i], font=font_m, fill=col4)  # shadow v.0.0.4
                draw3.text((x2, y), text[0+i], font=font_m, fill=col1)
            y += hei1
    else:
        result = 1  # needed for right pageindex
        len1, hei1 = draw3.textsize(text, font=font_m)
        x2 = (WIDTH - len1)//2
        y2 = (HEIGHT - hei1)//2
        draw3.rectangle((x2, y2, x2 + len1, y2 + hei1), col1)
        draw3.text((x2, y2), text, font=font_m, fill=col5)

    # draw symbols
    if icons == 'nav':  # v.0.0.4
        draw3.text((symb_l, symb_t), u"\uf14a", font=font_fas, fill=col1)  # Fontawesome symbols ok
        draw3.text((symb_r, symb_t), u"\uf151", font=font_fas, fill=col1)  # Fontawesome symbols up
        draw3.text((symb_l, symb_b), u"\uf0e2", font=font_fas, fill=col1)  # Fontawesome symbols back
        draw3.text((symb_r, symb_b), u"\uf150", font=font_fas, fill=col1)  # Fontawesome symbols down
    elif icons == 'info':
        draw3.text((10, 10), u"\uf05a", font=font_fas, fill=col1)  # Fontawesome symbols info
    elif icons == 'seek':
        draw3.text((symb_r, symb_t), u"\uf04e", font=font_fas, fill=col1)  # Fontawesome symbols forward
        draw3.text((symb_l, symb_b), u"\uf0e2", font=font_fas, fill=col1)  # Fontawesome symbols back
        draw3.text((symb_r, symb_b), u"\uf04a", font=font_fas, fill=col1)  # Fontawesome symbols backward

    page = int(math.ceil((float(marked) + 1)/float(listmax)))
    pages = int(math.ceil(float(result)/float(listmax)))
    if pages != 1:  # only show index if more than one site
        pagestring = str(page) + '/' + str(pages)
        len1, hei1 = draw3.textsize(pagestring, font=font_m)
        x2 = (WIDTH - len1)//2
        draw3.text((x2, HEIGHT - hei1), pagestring, font=font_m, fill=col1)
    sendtodisplay(img3)
    # print("displaystuff--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


# position in code is important, so display_stuff works v.0.0.4
display_stuff('bg_default', obj_trans['DISPLAY']['WAIT'], 0, 0, 'info')
socketIO = SocketIO('localhost', 3000)


def seeking(direction):
    # start_time = time.time()  # debug, time of code execution
    global seek, duration
    step = 60000  # 60 seconds
    if direction == '+':
        if int(float((seek + step)/1000)) < duration:
            seek += step
            socketIO.emit('seek', int(float(seek/1000)))
            display_stuff('bg_default', [obj_trans['DISPLAY']['SEEK'], strftime("%M:%S", gmtime(int(float(seek/1000)))) + ' / ' + strftime("%M:%S", gmtime(duration))], 0, 0, 'seek')
    else:
        if int(float((seek - step)/1000)) > 0:
            seek -= step
            socketIO.emit('seek', int(float(seek/1000)))
            display_stuff('bg_default', [obj_trans['DISPLAY']['SEEK'], strftime("%M:%S", gmtime(int(float(seek/1000)))) + ' / ' + strftime("%M:%S", gmtime(duration))], 0, 0, 'seek')
    # print("seeking--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def prevnext(direction):
    # start_time = time.time()  # debug, time of code execution
    global position
    if direction == 'prev':
        position -= 1
    else:
        position += 1
    if position > len_queue - 1:  # set position to first entry to loop through playlist infinite
        position = 0
    elif position < 0:  # set position to last entry to loop through playlist infinite
        position = len_queue - 1
    display_stuff('bg_default', [str(position + 1) + '/' + str(len_queue), obj_trans['DISPLAY']['PREVNEXT'], title_queue[position]], 1, 0, 'seek')
    socketIO.emit('stop')
    socketIO.emit('play', {"value": position})
    # print("prevnext--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def on_push_queue(*args):
    global title_queue, len_queue
    # reset variables first
    del title_queue[:]
    len_queue = 0
    if len(args[0]) != 0:
        len_queue = len(args[0])
        append_t = title_queue.append  # to avoid dots in for loop
        for i in range(len_queue):
            append_t(args[0][i]['name'])


def on_push_state(*args):
    # start_time = time.time()  # debug, time of code execution
    global img, img2, txt_col, str_col, bar_bgcol, bar_col, status, service, volume, albumart, img_check, mode, seek, duration, position

    def f_textsize(text, fontsize):
        w1, y1 = draw.textsize(text, fontsize)
        return w1

    def f_drawtext(x, y, text, fontstring, fillstring):
        draw.text((x, y), text, font=fontstring, fill=fillstring)

    def f_x1(textwidth):
        if textwidth <= WIDTH:
            x1 = (WIDTH - textwidth)//2
        else:
            x1 = 4 # was 0
        return x1

    def f_content(field, fontsize, top):
        if field in args[0]:
            if args[0][field]: # is not None:
                w1 = f_textsize(args[0][field], fontsize)
                x1 = f_x1(w1)
                draw.rectangle((x1-2, top+1, WIDTH-x1+2, top + blok_h-4), fill=(0,0,0,128)) #Artist block 
                f_drawtext(x1, top, args[0][field], fontsize, txt_col)

    volume = int(args[0]['volume'])
    position = args[0]['position']  # v.0.0.4
    if mode == 'player':
        status = args[0]['status'] # v0.0.6
        service = args[0]['service'] # v0.0.6

        if args[0]['albumart'].encode('ascii', 'ignore').decode('utf-8') != albumart:  #v0.0.6 # Load albumcover or radio cover (and only if changes)
            # albumart = args[0]['albumart'].encode('ascii', 'ignore')
            albumart = args[0]['albumart'].encode('ascii', 'ignore').decode('utf-8')  #v0.0.6
            print('Albumart', albumart) #v0.0.6

            albumart2 = albumart
            if len(albumart2) == 0:  # to catch a empty field on start
                albumart2 = 'http://localhost:3000/albumart'
            if 'http' not in albumart2:
                albumart2 = 'http://localhost:3000'+args[0]['albumart']

            response = requests.get(albumart2)
            img = Image.open(BytesIO(response.content)).convert('RGBA') 
            img = img.resize((WIDTH, HEIGHT))
            # img = img.filter(ImageFilter.BLUR)  # Blur
            draw = ImageDraw.Draw(img, 'RGBA')
            img2 = img.copy()

            # Symbols and bars, depending on background
            # im_stat = ImageStat.Stat(img)
            # im_mean = im_stat.mean
            # mn = mean(im_mean)

            txt_col = teal
            str_col = col4  # v0.0.4 needed for shadow
            bar_bgcol = col2
            bar_col = teal
        else:  # if albumart didnt change, copy the last unpasted version
            img = img2.copy()
            draw = ImageDraw.Draw(img, 'RGBA')

        # paste button symbol overlay
        blok_h = 32
        draw.rectangle((0, symb_t-3, symb_l + blok_h, symb_t - 3 + blok_h), col5)  # Play Block
        draw.rectangle((symb_r -5, symb_t -3, WIDTH, symb_t -3 + blok_h), col5)   # Menu Block
        draw.rectangle((symb_r -5, symb_b -3, WIDTH, symb_b -3 + blok_h), col5)   # Vol Block -9 for big speaker
        if status == 'play':
            f_drawtext(symb_l + 5, symb_t, u"\uf04C", font_fas, col1)  # Fontawesome symbol pause
        else:
            f_drawtext(symb_l + 5, symb_t, u"\uf04b", font_fas, col1) # Fontawesome symbol play
        f_drawtext(symb_r, symb_t+1, u"\uf0c9", font_fas, col1) # Fontawesome symbol menu
        f_drawtext(symb_r +4, symb_b, u"\uf026", font_fas, col1) # Fontawesome symbol speaker "\uf028" position -4

        f_content('artist', font_m, 4)  
        f_content('album', font_m, 32)
        f_content('title', font_m, 165)  # Wrong Top value

        # volume bar
        vol_x = int((float(args[0]['volume'])/100)*(WIDTH - 41))
        vol_t = symb_b + 9                                         # top of volume bar
        draw.rectangle((4, vol_t, WIDTH-37, vol_t + 8), bar_bgcol)  # background
        draw.rectangle((vol_x-1, vol_t-6, vol_x+6, vol_t), bar_col)  # Volumio indicator
        draw.rectangle((4, vol_t, vol_x+6, vol_t + 8), bar_col)  #tweaked numbers so doesn't go negative

        # time bar
        if 'duration' in args[0]:
            duration = args[0]['duration']  # seconds
            if duration != 0:
                # if 'seek' in args[0]:
                if 'seek' in args[0] and args[0]['seek'] is not None:  # v0.0.4 sometime seek = null or None
                    seek = args[0]['seek']  # time elapsed seconds
                    # if seek != 0:  # v0.0.4 seek=0 is ok to show
                    el_time = int(float(args[0]['seek'])/1000)
                    du_time = int(float(args[0]['duration']))
                    dur_x = int((float(el_time)/float(du_time))*(WIDTH-41))
                    if dur_x > (WIDTH - 41):
                        dur_x = WIDTH - 41
                    if dur_x < 0:
                        dur_x = 0
                    time_bt = 230 # top of time bar
                    draw.rectangle((4, time_bt, WIDTH-37, time_bt + 7), bar_bgcol)  # background
                    draw.rectangle((4, time_bt, dur_x+4, time_bt + 7), bar_col)

                    # v0.0.4 show remaining time of track
                    remaining = '-' + strftime("%M:%S", gmtime(duration - int(float(seek)/1000)))
                    w4 = f_textsize(remaining, font_m)
                    time_t = 194 # top of remaining time
                    f_drawtext(4, time_t, remaining, font_s, bar_col)  # shadow, fill by mean WIDTH - w4
                    # f_drawtext(WIDTH - w4 - 2, time_t - 2, remaining, font_s, txt_col)  # fill by mean

        # display only if img changed
        if img_check != img:
            img_check = img
            sendtodisplay(img)
    # print("on_push_state--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


img = Image.new('RGBA', (WIDTH, HEIGHT), color=(0, 0, 0, 255))  # prev A = 25
draw = ImageDraw.Draw(img, 'RGBA')
socketIO.once('connect', on_connect)
socketIO.on('disconnect', on_disconnect)


def handle_button(pin):
    # start_time = time.time()  # debug, time of code execution
    global mode, marker, liststart  # v.0.0.4
    browselibrary = False

    if pin == 5:  # Button A, only needs single press function
        print("Button 5 service:", service)
        if mode == 'player':
            if (status == 'play') and (service == 'webradio'):
                socketIO.emit('stop')
            elif (status == 'play'):
                socketIO.emit('pause')
            else:
                socketIO.emit('play')
        elif mode == 'navigation':
            if len(nav_array_uri) != 0:
                if len(nav_array_type) == 0:
                    browselibrary = True
                else:
                    if nav_array_type[marker] == 'song' or nav_array_type[marker] == 'webradio' or nav_array_type[marker] == 'mywebradio':  # v.0.0.4 fix for mywebradio
                        socketIO.emit('replaceAndPlay', {"service": nav_array_service[marker], "type": nav_array_type[marker], "title": nav_array_name[marker], "uri": nav_array_uri[marker]})
                        reset_variable('player')
                    elif nav_array_type[marker] == 'playlist' and nav_array_service[marker] == 'mpd':  # v.0.0.4 modified because of spotifiy
                        socketIO.emit('playPlaylist', {'name': nav_array_name[marker]})
                        reset_variable('player')
                    elif nav_array_type[marker] == 'playlist' and nav_array_service[marker] == 'spop':  # v.0.0.4 condition added because of spotifiy
                        socketIO.emit('stop')  # v.0.0.4 fix otherwise change from any playing source to spotify dont work
                        time.sleep(2)  # v.0.0.4 fix otherwise change from any playing source to spotify dont work
                        socketIO.emit('replaceAndPlay', {"service": nav_array_service[marker], "type": nav_array_type[marker], "title": nav_array_name[marker], "uri": nav_array_uri[marker]})
                        reset_variable('player')
                    elif 'folder' in nav_array_type[marker]:
                        if nav_array_service[marker] == 'podcast':
                            display_stuff('bg_default', obj_trans['DISPLAY']['WAIT'], marker, liststart)  # note, please wait
                        browselibrary = True
                    elif 'radio-' in nav_array_type[marker]:  # the minus (-) is important, otherwise i cant decide between 'radiofolder' and 'webradiostream'
                        browselibrary = True
                    elif 'streaming-' in nav_array_type[marker]:
                        browselibrary = True
                    else:
                        display_stuff('bg_default', obj_trans['DISPLAY']['NOTSUPPORTED'], marker, liststart)

                if browselibrary is True:
                    # replace "mnt/" in uri through "music-library/", otherwise calling them dont work (at least in favourites)
                    uri = nav_array_uri[marker]
                    uri = uri.replace('mnt/', 'music-library/')
                    socketIO.emit('browseLibrary', {'uri': uri})
                    browselibrary = False
            else:
                reset_variable('player')
                socketIO.emit('getState', '', on_push_state)
        elif mode == 'menu':
            # socketIO.emit('getQueue', on_push_queue)  # refresh variables of queue
            if nav_array_type[marker] == 'emit':
                if 'setSleep' in nav_array_uri[marker][0]:
                    socketIO.emit(nav_array_uri[marker][0], nav_array_uri[marker][1])
                    display_stuff('bg_default', obj_trans['DISPLAY']['SETSLEEPTIMER'], 0, 0, 'info')
                    disp.set_backlight(False)
                else:
                    socketIO.emit(nav_array_uri[marker])
                    display_stuff('bg_default', ['executing:', nav_array_uri[marker]], 0, 0, 'info')
            elif nav_array_type[marker] == 'seek': 
                mode = 'seek'
                display_stuff('bg_default', obj_trans['DISPLAY']['SEEK'], 0, 0, 'seek')
            elif nav_array_type[marker] == 'prevnext': 
                socketIO.emit('getQueue', on_push_queue)  # refresh variables of queue
                mode = 'prevnext'
                display_stuff('bg_default', [str(position + 1) + '/' + str(len_queue), obj_trans['DISPLAY']['PREVNEXT'], title_queue[position]], 1, 0, 'seek')
            else:  # browsesource
                reset_variable('navigation')
                socketIO.emit('getBrowseSources', '', on_push_browsesources)
        else:
            reset_variable('player')
            socketIO.emit('getState', '', on_push_state)

    if pin == 6:  # Button B, needs a pressed function in player mode
        if mode == 'player':
            while not GPIO.input(6) and volume > 0:  # limit/exit at volume 0 so amixer dont go crazy
                socketIO.emit('volume', '-')
                time.sleep(0.3) # Debounce volume
        elif mode == 'navigation' or mode == 'menu' or mode == 'seek' or mode == 'prevnext':
            reset_variable('player')
            socketIO.emit('getState', '', on_push_state)

    if pin == 16:  # Button X, needs a pressed function in navigation and menu mode
        if mode == 'player':
            navigation_handler()
            disp.set_backlight(True)  # v.0.0.4
        elif mode == 'navigation' or mode == 'menu':
            while not GPIO.input(16):
                marker -= 1  # count minus 1
                if marker < 0:  # blaettere nach oben durch
                    marker = listresult - 1
                    if listresult > listmax - 1:  # dann aendere auch noch den liststart
                        liststart = int(liststart + (math.floor(listresult/listmax)*listmax))
                liststart = int(math.floor(marker/listmax)*listmax)  # definiert das blaettern zur naechsten Seite
                time.sleep(0.1) #debounce on the menu
                display_stuff('bg_default', nav_array_name, marker, liststart)
        elif mode == 'seek':  
            seeking('+')
        elif mode == 'prevnext':  
            prevnext('next')
            time.sleep(0.1) #debound on the menu

    if pin == BUTTONS[3]:  # Button Y, needs a pressed function in  all modes
        if mode == 'seek':
            seeking('-')
        elif mode == 'prevnext':
            prevnext('prev')
            time.sleep(0.1) #debound on the menu
        else:
            while not GPIO.input(BUTTONS[3]):
                if mode == 'player' and volume < 100:  # limit/exit at volume 100 so amixer dont go crazy:
                    socketIO.emit('volume', '+')
                    time.sleep(0.3) #debound on the Volume
                elif mode == 'navigation' or mode == 'menu':
                    marker += 1  # count plus 1
                    liststart = int(math.floor(marker/listmax)*listmax)  # definiert das blaettern zur naechsten Seite
                    if marker > listresult - 1:  # blaettere nach unten durch
                        marker = 0
                        liststart = 0
                    time.sleep(0.1) #debound on the menu
                    display_stuff('bg_default', nav_array_name, marker, liststart)
    # print("handle_button--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


def setup_channel(channel):
    # start_time = time.time()  # debug, time of code execution
    try:
        #print('register %d') % channel
        print('register %d' % channel) #v0.0.6
        GPIO.setup(channel, GPIO.IN, GPIO.PUD_UP)
        GPIO.add_event_detect(channel, GPIO.FALLING, handle_button, bouncetime=100)
        print('success')
    except (ValueError, RuntimeError) as e:
        print('ERROR:', e)
    # print("setup_channel--- %s seconds ---" % (time.time() - start_time))  # debug, time of code execution


for x in BUTTONS:
    setup_channel(x)


def main():
    socketIO.wait()
    time.sleep(0.5)


try:
    main()
except KeyboardInterrupt:
    clean()
    pass
