"""
wimax_topology_discovery.py
=======================

This file contains the code for extracting and collecting the data for wimax topology and storing this data into embeded mongodb database.

"""

from nocout_site_name import *
import socket,json
import time
import imp
#from handlers.db_ops import *

utility_module = imp.load_source('utility_functions', '/omd/sites/%s/nocout/utils/utility_functions.py' % nocout_site_name)
mongo_module = imp.load_source('mongo_functions', '/omd/sites/%s/nocout/utils/mongo_functions.py' % nocout_site_name)
config_module = imp.load_source('configparser', '/omd/sites/%s/nocout/configparser.py' % nocout_site_name)
db_ops_module = imp.load_source('db_ops', '/omd/sites/%s/lib/python/handlers/db_ops.py' % nocout_site_name)


class MKGeneralException(Exception):
    """
    Class defination for the Exception Class.
    Args: Exception object
    Kwargs: None
    Return: message
    Exception :None

    """
    def __init__(self, reason):
        self.reason = reason
    def __str__(self):
        return self.reason

def topology_discovery_data(site,mongo_host,mongo_port,mongo_db_name):
	"""
	inventory_perf_data : Function for collecting the data for inventory serviecs.Service state is also retunred for those services
	Args: site (site on poller on which devices are monitored)
	Kwargs: hostlist (all host on that site)

	Return : None
	Raises: No Exception
	"""

	invent_check_list = []
	ss_sec_id = []
	invent_service_dict = {}
	matching_criteria = {}
	topology_list=[]
	#db = mongo_module.mongo_conn(host = mongo_host,port = mongo_port,db_name =mongo_db_name)
	service = "wimax_topology"

	query = "GET services\nColumns: host_name host_address host_state service_description service_state plugin_output\n" + \
                "Filter: service_description = wimax_topology\nOutputFormat: json\n" 


	device_down_query = "GET services\nColumns: host_name\nFilter: service_description ~ Check_MK\nFilter: service_state = 3\n"+\
                                "And: 2\nOutputFormat: python\n"
	query_output = json.loads(utility_module.get_from_socket(site,query).strip())
	query_output1 = eval(utility_module.get_from_socket(site,device_down_query).strip())
	device_down_list =[str(item) for sublist in query_output1 for item in sublist]
	for entry in query_output:
		try:
			if str(entry[0]) in device_down_list:
                        	continue
			service_state = entry[4]
                	host = entry[0]
                	if service_state == 0:
                        	service_state = "OK"
                	elif service_state == 1:
                       	 	service_state = "WARNING"
                	elif service_state == 2:
                        	service_state = "CRITICAL"
               	 	elif service_state == 3:
                        	service_state = "UNKNOWN"
               	 	host_ip = entry[1]
                	service = entry[3]
			perf_data_output = entry[5]
			if perf_data_output:
				plugin_output = (perf_data_output.split('- ')[1])
				plugin_output =	[mac for mac in plugin_output.split(' ')]
				ss_mac  = map(lambda x: x.split('=')[0],plugin_output)
				ss_ip  = map(lambda x: x.split('=')[1].split(',')[9],plugin_output)
				ss_sec_id  = map(lambda x: x.split('=')[1].split(',')[8],plugin_output)
				ds="topology"
			else:
				continue
		except Exception,e:
			print e
			continue
		current_time = int(time.time())
		topology_dict = dict (sys_timestamp=current_time,check_timestamp=current_time,device_name=str(host),
				service_name=service,sector_id=ss_sec_id,
				connected_device_ip=ss_ip,
				connected_device_mac=ss_mac,data_source=ds,site_name=site,ip_address=host_ip)
		matching_criteria.update({'device_name':str(host),'service_name':service})
		topology_list.append(topology_dict)
		#mongo_module.mongo_db_update(db,matching_criteria,topology_dict,"wimax_topology")
		#mongo_module.mongo_db_insert(db,topology_dict,"inventory_services")
		matching_criteria ={}
		ss_sec_id= []
		ss_ip = []
		ss_mac = []
	
	key = nocout_site_name + "_topology" 
	doc_len_key = key + "_len" 
	memc_obj=db_ops_module.MemcacheInterface()
	exp_time =240 # 4 min
	memc_obj.store(key,topology_list,doc_len_key,exp_time,chunksize=1000)

def topology_discovery_data_main():
	"""
	inventory_perf_data_main : Main Function for data extraction for inventory services.Function get all configuration from config.ini
	Args: None
	Kwargs: None

	Return : None
	Raises: No Exception
	"""
	try:
		configs = config_module.parse_config_obj()
		desired_site = filter(lambda x: x == nocout_site_name, configs.keys())[0]
		desired_config = configs.get(desired_site)
		site = desired_config.get('site')
		mongo_host = desired_config.get('host')
                mongo_port = desired_config.get('port')
                mongo_db_name = desired_config.get('nosql_db')
		topology_discovery_data(site,mongo_host,int(mongo_port),mongo_db_name)
	except SyntaxError, e:
		raise MKGeneralException(("Can not get performance data: %s") % (e))
	except socket.error, msg:
		raise MKGeneralException(("Failed to create socket. Error code %s Error Message %s:") % (str(msg[0]), msg[1]))
if __name__ == '__main__':
	topology_discovery_data_main()	
		
				
