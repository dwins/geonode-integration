import os
import urllib, urllib2, cookielib
import contextlib
from geonode.maps.models import Layer
from tempfile import mkstemp
from owslib.wcs import WebCoverageService
from owslib.wfs import WebFeatureService

def get_web_page(url, username=None, password=None, login_url=None):
    """Get url page possible with username and password.
    """

    if login_url:
        # Login via a form
        cookies = urllib2.HTTPCookieProcessor()
        opener = urllib2.build_opener(cookies)
        urllib2.install_opener(opener)

        opener.open(login_url)

        try:
            token = [x.value for x in cookies.cookiejar if x.name == 'csrftoken'][0]
        except IndexError:
            return False, "no csrftoken"

        params = dict(username=username, password=password, \
            this_is_the_login_form=True,
            csrfmiddlewaretoken=token,
            )
        encoded_params = urllib.urlencode(params)

        with contextlib.closing(opener.open(login_url, encoded_params)) as f:
            html = f.read()

    elif username is not None:
        # Login using basic auth

        # Create password manager
        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, url, username, password)

        # create the handler
        authhandler = urllib2.HTTPBasicAuthHandler(passman)
        opener = urllib2.build_opener(authhandler)
        urllib2.install_opener(opener)

    try:
        pagehandle = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        msg = ('The server couldn\'t fulfill the request. '
                'Error code: %s' % e.code)
        e.args = (msg,)
        raise
    except urllib2.URLError, e:
        msg = 'Could not open URL "%s": %s' % (url, e)
        e.args = (msg,)
        raise
    else:
        page = pagehandle.read()

    return page

def check_layer(uploaded):
    """Verify if an object is a valid Layer.
    """
    msg = ('Was expecting layer object, got %s' % (type(uploaded)))
    assert type(uploaded) is Layer, msg
    msg = ('The layer does not have a valid name: %s' % uploaded.name)
    assert len(uploaded.name) > 0, msg

# Miscellaneous auxiliary functions
def unique_filename(**kwargs):
    """Create new filename guarenteed not to exist previoously

    Use mkstemp to create the file, then remove it and return the name

    See http://docs.python.org/library/tempfile.html for details.
    """

    _, filename = mkstemp(**kwargs)

    try:
        os.remove(filename)
    except:
        pass

    return filename

def get_ows_metadata(server_url, layer_name):
    """Uses OWSLib to get the metadata for a given layer

    Input
        server_url: e.g. http://localhost:8001/geoserver-geonode-dev/ows
        layer_name: must follow the convention workspace:name

    Output
        metadata: Dictionary of metadata fields common to both
                  raster and vector layers
    """

    wcs = WebCoverageService(server_url, version='1.0.0')
    wfs = WebFeatureService(server_url, version='1.0.0')

    metadata = {}
    if layer_name in wcs.contents:
        layer = wcs.contents[layer_name]
        metadata['layer_type'] = 'raster'
    elif layer_name in wfs.contents:
        layer = wfs.contents[layer_name]
        metadata['layer_type'] = 'vector'
    else:
        msg = ('Layer %s was not found in WxS contents on server %s.\n'
               'WCS contents: %s\n'
               'WFS contents: %s\n' % (layer_name, server_url,
                                       wcs.contents, wfs.contents))
        raise Exception(msg)

    # Metadata common to both raster and vector data
    metadata['bounding_box'] = layer.boundingBoxWGS84
    metadata['title'] = layer.title
    metadata['id'] = layer.id

    # Extract keywords
    if not hasattr(layer, 'keywords'):
        msg = 'No keywords in %s. Submit patch to OWSLib maintainers' % layer
        # FIXME (Ole): Uncomment when OWSLib patch has been submitted
        #Raise Exception(msg)
    else:
        keyword_dict = {}
        for keyword in layer.keywords:
            if keyword is not None:
                # FIXME (Ole): Why would this be None sometimes?

                for keyword_string in keyword.split(','):

                    if ':' in keyword_string:
                        key, value = keyword_string.strip().split(':')
                        keyword_dict[key] = value
                    else:
                        keyword_dict[keyword_string] = None

        metadata['keywords'] = keyword_dict

    return metadata
