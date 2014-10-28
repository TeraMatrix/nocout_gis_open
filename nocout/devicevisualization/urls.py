from django.conf import settings
from django.conf.urls import patterns, url, include
from devicevisualization import views


urlpatterns = patterns('',
    url(r'^$', views.locate_devices),
	url(r'^gis/$', views.locate_devices),
	url(r'^google_earth/$', views.load_google_earth),
	url(r'^googleEarth/$', views.load_earth),
	url(r'^white_background/$', views.load_white_background),
	url(r'^gis/(?P<device_name>\w+)/$', views.locate_devices),
	url(r'^performance_data/$', views.Gis_Map_Performance_Data.as_view(), name='gis_map_performance_data'),
	url(r'^tools/point/$', views.PointToolClass.as_view(), name='point_tool_class'),
	url(r'^get_tools_data/$', views.GetToolsData.as_view(), name='get_tools_data')
)
