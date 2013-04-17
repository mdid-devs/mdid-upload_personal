from django.conf.urls.defaults import *
from views import import_personal_files

#main_urls = ()
urlpatterns = patterns('',
                       url(r'^$', import_personal_files, name='upload_personal'),
)