from django.conf.urls import patterns, url
from alert_center import views


urlpatterns = patterns('',
                       # common page for both customer and network
                       url(r'^((?P<page_type>\w+))_alert/(?P<data_source>\w+)/$',
                           views.AlertCenterListing.as_view(),
                           name='init_alert_listing'
                       ),

                       url(r'^networklistingtable/',
                           views.AlertListingTable.as_view(),
                           name='AlertListingTable'
                       ),
                       # common page for both customer and network

                       url(r'^(?P<page_type>\w+)_alert/(?P<data_source>\w+)/(?P<device_id>\w+)/$',
                           views.SingleDeviceAlertsInit.as_view(),
                           name='SingleDeviceAlertsInit'
                       ),

                       url(r'^(?P<page_type>\w+)_alert/(?P<data_source>\w+)/(?P<device_id>\w+)/listing/$',
                           views.SingleDeviceAlertsListing.as_view(),
                           name='SingleDeviceAlertsListing_clone'
                       ),

                       url(r'^network_detail/$',
                           views.NetworkAlertDetailHeaders.as_view(),
                           name='network_alert_details'
                       ),

                       url(r'^network_detail_listing_table$',
                           views.GetNetworkAlertDetail.as_view(),
                           name='NetworkAlertDetails'),

                       url(r'^(?P<page_type>\w+)_detail/$',
                           views.AlertCenterListing.as_view(),
                           name='customer_alert_details'
                       ),

                       url(r'^customer_detail_listing_table/',
                           views.AlertListingTable.as_view(),
                           name='CustomerAlertDetails'
                       )
)