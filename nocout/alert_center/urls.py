from django.conf.urls import patterns, url
from alert_center import views


urlpatterns = patterns('',
                       # common page for both customer and network
                       url(r'^((?!detail)(?P<page_type>\w+))/(?P<data_source>\w+)/$',
                           views.AlertCenterListing.as_view()
                       ),

                       url(r'^((?!detail)(?P<page_type>\w+))/(?P<data_source>\w+)/(?P<data_tab>\w+)/$',
                           views.AlertCenterListing.as_view()
                       ),

                       url(r'^networklistingtable/',
                           views.AlertListingTable.as_view(),
                           name='AlertListingTable'
                       ),
                       # common page for both customer and network

                       url(r'^(?P<page_type>\w+)/device/(?P<device_id>\w+)/service_tab/(?P<service_name>\w+)/$',
                           views.SingleDeviceAlertsInit.as_view(),
                           name='SingleDeviceAlertsInit'
                       ),

                       url(r'^listing/(?P<page_type>\w+)/device/(?P<device_id>\w+)/service_tab/$',
                           views.SingleDeviceAlertsListing.as_view(),
                           name='SingleDeviceAlertsListing_clone'
                       ),

                       url(r'^detail/network_detail/$',
                           views.getNetworkAlertDetail,
                           name='NetworkAlertDetailsHeader'
                       ),

                       url(r'^detail/network_detail_listing_table$', views.GetNetworkAlertDetail.as_view(),
                           name='NetworkAlertDetails'),

                       url(r'^detail/customer_detail/$',
                           views.getCustomerAlertDetail,
                           name='CustomerAlertDetailsHeader'
                       ),

                       url(r'^detail/customer_detail_listing_table/',
                           views.GetCustomerAlertDetail.as_view(),
                           name='CustomerAlertDetails'
                       ),

)