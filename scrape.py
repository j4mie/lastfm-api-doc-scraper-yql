"""
Screen-scrape the Last.fm API documentation to autogenerate Yahoo! Query
Language (YQL) Open Data Tables for each public API method.

As with any screen-scraper, this is fragile and ugly. Blame Last.fm for
having such a rubbish, hard-to-use, badly documented API that something 
like this is necessary.

This only returns infomation about the public API methods, ie those that just
require an API key to use. You could probably use YQL's ability to execute 
server-side JavaScript (http://developer.yahoo.com/yql/guide/yql-execute-chapter.html) 
to create tables which could authenticate with Last.fm to call the private
methods, but I personally had no need for this so didn't bother.

To use this, you'll need to create a directory with the name defined in OUTPUT_DIR. 
Your XML and environment files will end up in here.

The BASE_ENV_URL variable is used to generate an Environment file
containing table definition for all the XML files that have been generated.
You should put in here the URL at which you'll be serving the files.

    See:
        http://developer.yahoo.com/yql/
        http://www.datatables.org/
        http://www.last.fm/api

    Dependencies:
        html5lib - http://code.google.com/p/html5lib/
        django - http://www.djangoproject.com/

"""
import html5lib
import urllib
from django.template import Template, Context
from django.conf import settings

# Initialise Django's settings
settings.configure()

BASE_API_URL = 'http://www.last.fm'
TEMPLATE_FILE = 'template.xml'
OUTPUT_DIR = 'tables'
AUTHOR = 'Jamie Matthews'

BASE_ENV_URL = 'http://www.your-server.com'
ENV_FILENAME = 'lastfm.env'

env_file = open("%s/%s" % (OUTPUT_DIR, ENV_FILENAME), 'w')
xml_template = Template(open(TEMPLATE_FILE).read())

def get_soup(url):
    """
    Get a BeautifulSoup object representing the given URL
    """
    html = urllib.urlopen(url)
    parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder('beautifulsoup'))
    return parser.parse(html)

def get_method_list():
    """
    Get list of methods from the Last.fm API documentation

    Returns a list of dictionaries containing the keys "name" and "url"
    """
    soup = get_soup(BASE_API_URL + '/api')
    methodlinks = soup.find(id="methods").findAll("a")
    methods = []

    for method in methodlinks:
        name, url = method.renderContents(), BASE_API_URL + method['href']

        method = {
            'name' : name,
            'url' : url,
        }

        methods.append(method)

    return methods

def get_method_details(name, url):
    """
    Get information about a particular API method from an API documentation URL.

    Also gets passed the name of the method, which we have anyway from the
    get_method_list function. This saves re-parsing the name from the HTML.

    Returns a dictionary containing the keys:
        name - the name of the method
        url - the url for the method's information page
        requires_auth - a boolean representing whether the method requires authentication
        params - a list of dictionaries containing information about each parameter:
            name - the name of the parameter
            description - description of the parameter
            required - boolean representing whether the param is required
    """
    soup = get_soup(url)

    # Get the description of the method 
    description = soup.find("div", "wsdescription").renderContents().strip().replace("\n", " ")
    
    # Get the HTML elements representing the method parameters
    param_elems = soup.findAll("span", "param")

    params = []
    requires_auth = False

    for param in param_elems:
        param_name, details = param.renderContents(), param.nextSibling

        # Get round odd malformed HTML problem - empty params
        if len(param_name.strip()) == 0 or len(details.strip()) == 0:
                continue

        # Some of the items with class "param" are actually error codes,
        # and so we want to disregard them. These all have numeric "names", 
        # so if we can successfully convert the name to an int, we can safely
        # throw it away.
        try: 
            int(param_name)
        except:
            param_info = {'name' : param_name}
            required, desc = details.split(":", 1)
            param_info['required'] = required.strip() == '(Required)'
            param_info['description'] = desc.strip()
            params.append(param_info)
            
            if param_name == 'api_sig': requires_auth = True

    details = {
        'params': params,
        'name': name,
        'description': description,
        'url': url,
        'requires_auth': requires_auth,
    }

    return details

def render_to_xml(method_details):
    """
    Convert the dictionary representing a method into XML.
    Uses Django's templating system.
    """
    method_details['author'] = AUTHOR
    return xml_template.render(Context(method_details))

def write_file(name, xml):
    """
    Put the xml in a file. Returns the base name of the file.
    """
    basename = "lastfm.%s.xml" % name.lower()
    filename = "%s/%s" % (OUTPUT_DIR, basename)
    file = open(filename, 'w')
    file.write(xml)
    file.close()
    print "\tWrote xml to %s" % filename
    return basename

def add_to_env(filename, methodname):
    """
    Add the supplied filename and method name to the env file defined in ENV_FILENAME
    """
    line = "USE '%s/%s' AS lastfm.%s;\n" % (BASE_ENV_URL, filename, methodname.lower())
    env_file.write(line)

if __name__ == '__main__':
    methods = get_method_list()

    for method in methods:
        print "\n----- Processing method: %s -----" % method['name']
        method_details = get_method_details(method['name'], method['url'])

        if not method_details['requires_auth']: # check if public
            xml = render_to_xml(method_details)
            filename = write_file(method_details['name'], xml)
            add_to_env(filename, method_details['name'])
        else:
            print "\tMethod is not public, skipping"
