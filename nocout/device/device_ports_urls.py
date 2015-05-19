"""
====================================================================================
Module contains url configuration specific to 'device ports' module in 'device' app.
====================================================================================

Location:
* /nocout_gis/nocout/device/device_ports_urls.py
"""

from django.conf.urls import patterns, url
from device import views

urlpatterns = patterns('',
                       url(r'^$', views.DevicePortList.as_view(), name='device_ports_list'),
                       url(r'^(?P<pk>\d+)/$', views.DevicePortDetail.as_view(), name='device_port_detail'),
                       url(r'^new/$', views.DevicePortCreate.as_view(), name='device_port_new'),
                       url(r'^(?P<pk>\d+)/edit/$', views.DevicePortUpdate.as_view(), name='device_port_edit'),
                       url(r'^(?P<pk>\d+)/delete/$', views.DevicePortDelete.as_view(), name='device_port_delete'),
                       url(r'^deviceportlistingtable/', views.DevicePortListingTable.as_view(),
                           name='DevicePortListingTable'),
                       )