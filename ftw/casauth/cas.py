from logging import getLogger
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import parse_qsl
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit
from urllib.request import urlopen
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError

import ssl


CAS_NS = "http://www.yale.edu/tp/cas"

logger = getLogger('ftw.casauth')


def validate_ticket(ticket, cas_server_url, service_url):
    """Validates a CAS service ticket and returns the authenticated userid.
    """
    validate_url = '%s/serviceValidate?service=%s&ticket=%s' % (
        cas_server_url,
        quote(service_url),
        ticket,
    )

    try:
        resp = urlopen(validate_url)
    except HTTPError as e:
        logger.warning("Ticket validation failed. Could not open url %s. "
                       "Staus code: %s, reason: %s", validate_url, e.code,
                       e.reason)
        return False
    except URLError as e:
        logger.warning("Ticket validation failed. Could not open url %s. "
                       "Reason: %s", validate_url, e.reason)
        return False
    except ssl.CertificateError as e:
        logger.warning("Ticket validation failed. Could not open url %s. "
                       "CertificateError: %s", validate_url, str(e))
        return False
    except ssl.SSLError as e:
        logger.warning("Ticket validation failed. Could not open url %s. "
                       "SSL Error: %s", validate_url, e.reason)
        return False

    try:
        resp_data = resp.read()
    except IOError:
        logger.warning("Ticket validation failed. Could not read from url %s.",
                       validate_url)
        return False

    try:
        doc = parseString(resp_data)
    except ExpatError:
        return False
    auth_success = doc.getElementsByTagNameNS(CAS_NS,
                                              'authenticationSuccess')
    if not auth_success:
        auth_fail = doc.getElementsByTagNameNS(CAS_NS,
                                               'authenticationFailure')
        if auth_fail:
            logger.info(
                "Authentication failed: Service ticket validation returned"
                " '%s'." % auth_fail[0].getAttribute('code'))
        else:
            logger.info("Authentication failed: Could not validate service"
                        " ticket.")
        return False

    userid = auth_success[0].getElementsByTagNameNS(CAS_NS, 'user')
    if not userid:
        return False
    userid = userid[0].firstChild.data

    return userid


def service_url(request):
    url = request['ACTUAL_URL']
    if request['QUERY_STRING']:
        url = '%s?%s' % (url, request['QUERY_STRING'])
        url = strip_ticket(url)
    return url


def strip_ticket(url):
    """Drop the `ticket` query string parameter from a given URL,
    but preserve everything else.
    """
    scheme, netloc, path, query, fragment = urlsplit(url)
    # Using parse_qsl here to preserve order
    qs_params = list(filter(lambda kv: kv[0] != 'ticket', parse_qsl(query)))
    query = urlencode(qs_params)
    new_url = urlunsplit((scheme, netloc, path, query, fragment))
    return new_url
