"""
Django settings for nocout project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

import os
from django.conf import global_settings
from collections import namedtuple

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROJECT_DIR = os.path.dirname(__file__)

DEBUG = False
TEMPLATE_DEBUG = DEBUG
PROFILE = DEBUG
PROFILE_TYPE = 'line'

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',  # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'nocout_dev',  # Or path to database file if using sqlite3.
        # The following settings are not used with sqlite3:
        'USER': 'root',
        'PASSWORD': 'mydesk',
        'HOST': 'localhost',  # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '3306',  # Set to empty string for default.
    }
}

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['*']

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'Asia/Calcutta'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

LOGIN_URL = '/login/'
LOGIN_EXEMPT_URLS = (r'auth/', 'login/', 'admin/', 'sm/dialog_for_page_refresh/', 'sm/dialog_expired_logout_user/', 'reset-cache/')

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static/")

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    os.path.join(PROJECT_DIR, "static/"),
)


# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'dajaxice.finders.DajaxiceFinder',
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'q+(_ijqc+^&#_51_duhnl+u-$&63tzgdo2b0_gaw!*%swxkc!&'

TEMPLATE_DIRS = ( os.path.join(PROJECT_DIR, "templates"), )
# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'django.template.loaders.eggs.Loader',
)
# Template context processors

TEMPLATE_CONTEXT_PROCESSORS = global_settings.TEMPLATE_CONTEXT_PROCESSORS + (
    'django.core.context_processors.request',
    'nocout.context_processors_profile.user_profile_atts.user_dept_org',
)

MIDDLEWARE_CLASSES = (
    #caching
    # 'django.middleware.cache.UpdateCacheMiddleware',
    #caching
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'nocout.middleware.UserProfileAuditMiddleware',
    'session_security.middleware.SessionSecurityMiddleware',
    'nocout.middlewares.LoginRequiredMiddleware.LoginRequiredMiddleware',
    #'audit_log.middleware.UserLoggingMiddleware',
    #'audit_log.middleware.AuditlogMiddleware',
    # Uncomment the next line for simple clickjacking protection
    #required for GISS SCAN
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    #caching
    # 'django.middleware.cache.FetchFromCacheMiddleware',
    #caching
)

#cookies settings
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True

#session cookie
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True

ROOT_URLCONF = 'nocout.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'nocout.wsgi.application'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'session_security',
    'south',
    'nocout.signals', # Load before nocout apps
    'user_profile',
    'user_group',
    'device',
    'device_group',
    'inventory',
    'organization',
    'department',
    'service',
    'service_group',
    'command',
    'site_instance',
    'machine',
    'home',
    'devicevisualization',
    'sitesearch',
    'alert_center',
    'capacity_management',
    'download_center',
    'performance',
    'dashboard',
    'scheduling_management',
    'dajaxice',
    'dajax',
    'django.contrib.admin',
    'session_management',
    'corsheaders',
    'activity_stream',
    'jsonify',
    'djcelery',
    'rest_framework',
    'alarm_escalation',
)

##TODO: dynamically populate cache
#
# def get_cache():
#     import os
#
#     try:
#         os.environ['MEMCACHE_SERVERS'] = os.environ['MEMCACHIER_SERVERS'].replace(',', ';')
#         os.environ['MEMCACHE_USERNAME'] = os.environ['MEMCACHIER_USERNAME']
#         os.environ['MEMCACHE_PASSWORD'] = os.environ['MEMCACHIER_PASSWORD']
#         return {
#             'default': {
#                 'BACKEND': 'django_pylibmc.memcached.PyLibMCCache',
#                 'TIMEOUT': 500,
#                 'BINARY': True,
#                 'OPTIONS': {'tcp_nodelay': True}
#             }
#         }
#     except:
#         return {
#             'default': {
#                 'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
#                 'LOCATION': 'nocout-gis-rf-critical'
#             }
#         }
#
# CACHES = get_cache()


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'nocout-gis-rf-critical',
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}

ALLOWED_APPS_TO_CLEAR_CACHE = [
    'inventory',
]

'''
# RabbitMQ configuration for django-celery
BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "priyesh"
BROKER_PASSWORD = "pass"
BROKER_VHOST = "/nocout_dev"
'''

# MongoDB configuration for django-celery
CELERY_RESULT_BACKEND = "mongodb"
CELERY_MONGODB_BACKEND_SETTINGS = {
    "host": "127.0.0.1",
    "port": 27017,
    "database": "nocout_celery_db",             # mongodb database for django-celery
    "taskmeta_collection": "c_queue"            # collection name to use for task output
}
BROKER_URL = 'mongodb://localhost:27017/nocout_celery_db'

#=time zone for celery periodic tasks
CELERY_TIMEZONE = 'Asia/Calcutta'


import djcelery
djcelery.setup_loader()

CORS_ORIGIN_ALLOW_ALL = True

SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s:%(lineno)s %(process)d %(thread)d %(message)s',
            'datefmt' : "%d/%b/%Y %H:%M:%S"
        },
    },
    'handlers': {
        'sentry': {
            'level': 'DEBUG',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'logfile': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join( '/tmp/nocout_main.log' ),
            'maxBytes': 1000000000,
            'backupCount':10,
            'formatter': 'verbose',
        },

    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
        'raven': {
            'level': 'DEBUG',
            'handlers': ['console', 'sentry'],
            'propagate': False,
        },
        'sentry.errors': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
        '':{
            'handlers': ['console','logfile','sentry'],
            'level': 'DEBUG',
        },
    },
}

##FOR MULTI PROC data analysis
MULTI_PROCESSING_ENABLED = False
##FOR MULTI PROC data analysis

SESSION_SECURITY_WARN_AFTER = 540
SESSION_SECURITY_EXPIRE_AFTER = 600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SECURITY_PASSIVE_URLS = ['dialog_for_page_refresh', 'dialog_expired_logout_user']

MAX_USER_LOGIN_LIMIT=100

DEFAULT_USERS= namedtuple('DEFAULT_USERS', 'USERNAME ID')
NOCOUT_USER= DEFAULT_USERS( USERNAME='nocout', ID=1)
GISADMIN= DEFAULT_USERS( USERNAME='gisadmin', ID=2)
GISOPERATOR_ID= DEFAULT_USERS( USERNAME='gisoperator', ID=3)
GISVIEWER_ID= DEFAULT_USERS( USERNAME='gisviewer', ID=3)


DEVICE_TECHNOLOGY = namedtuple('DEVICE_TECHNOLOGY','NAME ID' )
P2P = DEVICE_TECHNOLOGY('P2P', '2')
WiMAX = DEVICE_TECHNOLOGY('WiMAX', '3')
PMP = DEVICE_TECHNOLOGY('PMP', '4')
Switch = DEVICE_TECHNOLOGY('Switch', '7')
TCLPTPPOP = DEVICE_TECHNOLOGY('TCLPTPPOP', '9')



MPTT_TREE= namedtuple('MPTT_TREE', 'lft rght level')

ISOLATED_NODE= MPTT_TREE(lft=1, rght=2, level=0)

# Default PING parameters
PING_PACKETS = 60
PING_TIMEOUT = 20
PING_NORMAL_CHECK_INTERVAL = 5
PING_RTA_WARNING = 1500
PING_RTA_CRITICAL = 3000
PING_PL_WARNING = 80
PING_PL_CRITICAL = 100

######################list of private IPs

PRIVATE_IPS_PREFIX = ('10.', '172.', '192.', )
GIS_MAP_MAX_DEVICE_LIMIT=1000

##############################################
EXCEPTIONAL_SERVICES = ['wimax_dl_cinr', 'wimax_ul_cinr', 'wimax_dl_rssi',
                        'wimax_ul_rssi', 'wimax_ul_intrf', 'wimax_dl_intrf',
                        'wimax_modulation_dl_fec', 'wimax_modulation_ul_fec',
                        'cambium_ul_rssi', 'cambium_ul_jitter', 'cambium_reg_count',
                        'cambium_rereg_count']

###################################################################################################################

DEVICE_APPLICATION = {
    'default': {
        'NAME': 'master_UA',  # Or path to database file if using sqlite3.
    }
}

###Services & SErvice Datasoruces settings
SERVICE_DATA_SOURCE = {
    "rta": {
        "display_name": "Latency",
        "type": "line",
        "valuesuffix": " ms",
        "valuetext": "ms",
        "formula": "rta_null",
        "show_min": 0,
        "show_max": 0,
        "show_gis": 1,
        "show_performance_center": 1,
        "is_inverted": 0,
        "chart_color": "#70AFC4",
        "service_name": 'ping',
        "service_alias": 'Ping',
    },
    "pl": {
        "display_name": "Packet Drop",
        "type": "column",
        "valuesuffix": " %",
        "valuetext": "Percentage (%)",
        "formula": None,
        "show_min": 0,
        "show_max": 0,
        "show_gis": 1,
        "show_performance_center": 1,
        "is_inverted": 0,
        "chart_color": "#70AFC4",
        "service_name": 'ping',
        "service_alias": 'Ping',
    },
    "availability": {
        "display_name": "Availability",
        "type": "column",
        "valuesuffix": " %",
        "valuetext": "Percentage (%)",
        "formula": None,
        "show_min": 0,
        "show_max": 0,
        "show_gis": 1,
        "show_performance_center": 1,
        "is_inverted": 0,
        "chart_color": "#70AFC4",
        "service_name": 'availability',
        "service_alias": 'Availability',
    },
    "rf": {
        "display_name": "RF Latency",
        "type": "spline",
        "valuesuffix": " ms",
        "valuetext": "ms",
        "formula": None,
        "show_min": 0,
        "show_max": 0,
        "show_gis": 0,
        "show_ss": 1,
        "show_bs": 1,
        "show_performance_center": 1,
        "is_inverted": 0,
        "chart_color": "#70AFC4",
        "service_name": 'rf',
        "service_alias": 'RF Latency',
    },

}

SERVICES = {

}

#Date Format to be used throughout the application
DATE_TIME_FORMAT = "%m/%d/%y (%b) %H:%M:%S (%I:%M %p)"

###################REPORT_PATH

REPORT_PATH = '/opt/nocout/nocout_gis/nocout/media/download_center/reports'
REPORT_RELATIVE_PATH = '/opt/nocout/nocout_gis/nocout'


# ********************** django password options **********************
PASSWORD_MIN_LENGTH = 6 # Defaults to 6
PASSWORD_MAX_LENGTH = 120 # Defaults to None

PASSWORD_DICTIONARY = "/usr/share/dict/words" # Defaults to None
# PASSWORD_DICTIONARY = "/usr/share/dict/american-english" # Defaults to None

PASSWORD_MATCH_THRESHOLD = 0.9 # Defaults to 0.9, should be 0.0 - 1.0 where 1.0 means exactly the same
PASSWORD_COMMON_SEQUENCES = [] # Should be a list of strings, see passwords/validators.py for default
PASSWORD_COMPLEXITY = { # You can ommit any or all of these for no limit for that particular set
    "UPPER": 1,       # Uppercase
    "LOWER": 1,       # Lowercase
    "DIGITS": 1,      # Digits
    "PUNCTUATION": 0, # Punctuation (string.punctuation)
    "NON ASCII": 0,   # Non Ascii (ord() >= 128)
    "WORDS": 0        # Words (substrings seperates by a whitespace)
}


# Import the local_settings.py file to override global settings

try:
    from local_settings import *
except ImportError:
    pass

