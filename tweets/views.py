# -*- coding: utf-8 -*-
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext, Context, loader
from datetime import datetime
import settings
import urllib2
import json

API_JSON_ENCODING = 'ISO-8859-1'
parse_json = lambda s: json.loads(s.decode(API_JSON_ENCODING))

def index(request):
    photos = search_photos('1')
    return render_to_response('index.html', {
        'photos': photos,
    }, context_instance=RequestContext(request))

# if user click the button "もっと見る", the browser send
# ajax request to server, and return next page's photos
# to the client
def get_page(request, page_id):
    photos = search_photos(str(page_id))
    t = loader.get_template('photolist.html')
    c = Context({
        'photos': photos,
        'pageid': page_id,
    })
    result = {
        'html': t.render(c),
    }
    data = json.dumps(result)
    return json_response(data)

# search photos that has hashtag #桜2012
def search_photos(page_id):
    photos = []
    END_POINT = 'http://search.twitter.com/search.json'
    search_key_uni = u'#桜2012'
    search_key = urllib2.quote(search_key_uni.encode('utf-8'))
    address = '%s?q=%s&include_entities=1&rpp=100&page=%s' % (
        END_POINT, search_key, page_id)
    results = httpget(address)['results']
    url_histories = {}
    # TODO make blacklist automate
    url_blacklist = {
        'http://p.twimg.com/ApJqZr7CMAAT9cu.jpg': True,
    }

    for result in results:
        entities = result['entities']
        text = get_urlize_text(result)
        entities_urls = entities['urls']
        media = entities.get('media', '')
        date = datetime.strptime(result['created_at'], '%a, %d %b %Y %H:%M:%S +%f')
        geo = result['geo']
        username = '@%s' % (result['from_user'])
        if geo:
            addr = get_location(geo['coordinates'])
            geo['addr'] = addr
        if media:
            for m in media:
                url = m['media_url']
                if url and not url_histories.get(url, False) and not url_blacklist.get(url, False):
                    photos.append({
                        'text': text,
                        'url': m['expanded_url'],
                        'imgsrc': url,
                        'date': date.strftime('%Y/%m/%d %H:%M:%S'),
                        'geo': geo,
                        'username': username,
                    })
                    url_histories[url] = 'true'
        elif entities_urls:
            for entities_url in entities_urls:
                url = entities_url['expanded_url']
                if url and not url_histories.get(url, False) and not url_blacklist.get(url, False):
                    imgsrc = get_imgsrc(url)
                    if imgsrc is not None:
                        photos.append({
                            'text': text,
                            'url': url,
                            'imgsrc': imgsrc,
                            'date': date.strftime('%Y/%m/%d %H:%M:%S'),
                            'geo': geo,
                            'username': username,
                        })
                        url_histories[url] = 'true'
    return photos


# For ajax(json) response, wrapper json data to convert HttpResponse
def json_response(data, code=200, mimetype='application/json'):
    resp = HttpResponse(data, mimetype)
    resp.code = code
    return resp

# send GET request to the endpoint and get the information in JSON
# TODO need handlings of errors, such as urllib2.HTTPError(404, etc)
def httpget(address, user_agent='myagent'):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', user_agent)]
    result = opener.open(address).read()
    return parse_json(result)


# get the location info (City, Prefecture) from lat and lng
# TODO supports only in Japan, need to support more!
def get_location(coordinates):
    END_POINT = 'http://geoapi.heartrails.com/api/json?method=searchByGeoLocation'
    lat = coordinates[0]
    lng = coordinates[1]
    address = END_POINT + '&y=' + str(lat) + '&x=' + str(lng)
    results = httpget(address)['response']
    locations = results.get('location', None)
    if not locations:
        return 'Unknown place'
    # pick 1st location
    loc = locations[0]
    return loc['city'] + ', ' + loc['prefecture']


# converts URLs, hashtags in text into clickable links
def get_urlize_text(result):
    text = result['text']
    entities = result['entities']
    urls = result.get('urls', '')
    entities_urls = entities.get('urls', '')
    if urls:
        for url in urls:
            urlize = '<a href="%s">%s</a>' % (url['url'], url['display_url'])
            text = text.replace(url['url'], urlize)
    if entities_urls:
        for e_url in entities_urls:
            urlize = '<a href="%s">%s</a>' % (e_url['url'], e_url['display_url'])
            text = text.replace(e_url['url'], urlize)

    hash_tags = entities.get('hashtags', '')
    if hash_tags:
        for h_tag in hash_tags:
            href = 'https://twitter.com/#!/search/%23' + h_tag['text']
            tag = '#' + h_tag['text']
            urlize = u'<a href="%s">%s</a>' % (href, tag)
            text = text.replace(tag, urlize)
            # for zenkaku hash tag
            tag = u'＃' + h_tag['text']
            urlize = u'<a href="%s">%s</a>' % (href, tag)
            text = text.replace(tag, urlize)
 
    medias = entities.get('media', '')
    if medias:
        for media in medias:
            urlize = '<a href="%s">%s</a>' % (media['url'], media['display_url'])
            text = text.replace(media['url'], urlize)

    return text


# get image src from url
# now, this app supports following third party photo upload:
#  - yfrog
#  - twipple
#  - instagram
#  - photozou
#  - twitpic
#  - flickr
#  - movapic
#  - f.hatena
#  - lockerz
#  - ow.ly
#
def get_imgsrc(url):
    if url.startswith('http://yfrog.com/'):
        return url + ':iphone'
    if url.startswith('http://p.twipple.jp/'):
        tmp = url.split('/')
        return 'http://p.twipple.jp/show/large/' + tmp[-1]
    if url.startswith('http://instagr.am/p/'):
        return url + 'media/?size=m'
    if url.startswith('http://photozou.jp/'):
        tmp = url.split('/')
        return 'http://photozou.jp/p/img/' + tmp[-1]
    if url.startswith('http://twitpic.com/'):
        tmp = url.split('/')
        return 'http://twitpic.com/show/large/' + tmp[-1]
    if url.startswith('http://flic.kr/') or url.startswith('http://www.flickr.com/'):
        return get_flickr_src(url)
    if url.startswith('http://movapic.com/'):
        tmp = url.split('/')
        return 'http://image.movapic.com/pic/s_%s.jpeg' % (tmp[-1])
    if url.startswith('http://f.hatena.ne.jp/'):
        tmp = url.split('/')
        u_id = tmp[3]
        ymd = tmp[4][:8]
        p_id = tmp[4][8:]
        return 'http://img.f.hatena.ne.jp/images/fotolife/%s/%s/%s/%s%s.jpg' % (
            u_id[0], u_id, ymd, ymd, p_id)
    if url.startswith('http://lockerz.com/'):
        return 'http://api.plixi.com/api/tpapi.svc/imagefromurl?url=%s&size=mobile' % (url)
    if url.startswith('http://ow.ly/i/'):
        tmp = url.split('/')
        return 'http://static.ow.ly/photos/normal/%s.jpg' % (tmp[-1])
    return None

# get image src from flickr API
def get_flickr_src(url):
    API_KEY = settings.FLICKR_API_KEY
    END_POINT = 'http://api.flickr.com/services/rest/'
    if url.startswith('http://flic.kr/'):
        tmp = url.split('/')
        id = decode(tmp[-1])
    else:
        tmp = url.split('/')
        id = tmp[-2]

    address = '%s?method=flickr.photos.getSizes&api_key=%s&photo_id=%s&format=json&nojsoncallback=1' % (
        END_POINT, API_KEY, str(id))
    results = httpget(address)
    sizes = results['sizes']
    size = sizes['size']
    for s in size:
        if s['label'] == 'Medium':
            return s['source']
    return url


# from https://gist.github.com/865912
def decode(s):
    alphabet = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
    base_count = len(alphabet)

    """ Decodes the base58-encoded string s into an integer """
    decoded = 0
    multi = 1
    s = s[::-1]
    for char in s:
        decoded += multi * alphabet.index(char)
        multi = multi * base_count

    return decoded

